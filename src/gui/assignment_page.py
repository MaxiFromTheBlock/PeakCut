# assignment_page.py - Folgenschnitt assignment step (between Analysis and Review)

import os
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from utils import TEMP_DIR
from .apple_style import COLORS
from .thumbnail_worker import ThumbnailWorker
from .mic_preview_worker import MicPreviewWorker
from core.folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_TOTAL,
    SHOT_UNUSED,
    SHOT_WIDE,
    PERSONLESS_SHOT_TYPES,
    CameraAssignment,
    MicAssignment,
)
from core.folgenschnitt_pipeline import (
    build_default_folgenschnitt_mic_assignments,
    has_minimum_folgenschnitt_assignment,
)

NEUTRAL_SHOT_LABEL = "— bitte zuordnen —"

SHOT_CHOICES = [
    (NEUTRAL_SHOT_LABEL, None),
    ("Weit", SHOT_WIDE),
    ("Nah/Close", SHOT_CLOSE),
    ("Halbnah", SHOT_MEDIUM),
    ("Totale", SHOT_TOTAL),
    ("— nicht nutzen", SHOT_UNUSED),
]


def preview_start_s_for_mic(session, speaker_key: str) -> float:
    """Start of the first window where this mic is the active speaker
    (~0.5 s before, so the voice is actually audible). Fallback 0.0."""
    for frame in getattr(session, "speaker_activity", []) or []:
        if frame.smoothed_speaker == speaker_key and frame.confidence > 0:
            return max(0.0, frame.start_ms / 1000 - 0.5)
    return 0.0


# ══════════════════════════════════════════════════════════════
# Pure data layer (unit-tested without Qt)
# ══════════════════════════════════════════════════════════════

@dataclass
class CameraRow:
    path: str
    filename: str
    shot_type: str | None
    person: str | None


@dataclass
class MicRow:
    track_index: int
    path: str
    filename: str
    person: str
    speaker_key: str


@dataclass
class AssignmentState:
    camera_rows: list[CameraRow]
    mic_rows: list[MicRow]
    people: list[str] = field(default_factory=list)

    def to_mic_assignments(self) -> list[MicAssignment]:
        return [
            MicAssignment(
                track_index=r.track_index,
                path=r.path,
                person=r.person,
                speaker_key=r.speaker_key,
            )
            for r in self.mic_rows
            if (r.person or "").strip()
        ]

    def to_camera_assignments(self) -> list[CameraAssignment]:
        # Neutral (unassigned) rows have shot_type None and are skipped —
        # they produce no CameraAssignment. CameraAssignment normalizes
        # person to None for personless shots.
        return [
            CameraAssignment(path=r.path, shot_type=r.shot_type, person=r.person)
            for r in self.camera_rows
            if r.shot_type
        ]

    def is_complete(self) -> bool:
        ok, _ = has_minimum_folgenschnitt_assignment(
            self.to_mic_assignments(), self.to_camera_assignments()
        )
        return ok


def build_assignment_state(session, video_files) -> AssignmentState:
    project = getattr(session, "project", None)
    analysis_mics = list(
        getattr(session, "speaker_activity_mic_assignments", []) or []
    )

    if analysis_mics:
        people: list[str] = []
        for m in analysis_mics:
            if m.person and m.person not in people:
                people.append(m.person)
        mic_rows = [
            MicRow(m.track_index, m.path, os.path.basename(m.path), m.person, m.speaker_key)
            for m in analysis_mics
        ]
    else:
        guest = (getattr(project, "guest_name", "") or "").strip()
        guest_person = guest if guest and guest.lower() != "unknown" else "Gast"
        people = ["Matze", guest_person]
        defaults = build_default_folgenschnitt_mic_assignments(project)
        mic_rows = [
            MicRow(m.track_index, m.path, os.path.basename(m.path), m.person, m.speaker_key)
            for m in defaults
        ]

    while len(people) < 2:
        people.append("Gast")

    # Cameras start neutral on purpose: a guessed-but-wrong default that
    # looks filled-in is worse than an explicit "not yet assigned".
    camera_rows = [
        CameraRow(path, os.path.basename(path), None, None)
        for path in video_files
    ]

    return AssignmentState(camera_rows, mic_rows, people)


# ══════════════════════════════════════════════════════════════
# Qt widget (manual QA: Task 9)
# ══════════════════════════════════════════════════════════════

class AssignmentPage(QWidget):
    """Encapsulated assignment step. Kept loosely coupled from ReviewPage so a
    later UX redesign can move it. Never blocks the Keyboardstellen export."""

    continue_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = None
        self._state: AssignmentState | None = None
        self._camera_widgets = []
        self._mic_widgets = []
        self._thumb_labels: dict[str, QLabel] = {}
        self._thumb_worker: ThumbnailWorker | None = None
        self._preview_workers: list[MicPreviewWorker] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Kamera- & Mikrofon-Zuordnung")
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 600;"
        )
        layout.addWidget(title)

        hint = QLabel(
            "Ordne jede Kamera einem Aufnahme-Typ (und ggf. einer Person) zu. "
            "Für den automatischen Folgenschnitt brauchst du zwei personenbezogene "
            "Weit-Kameras. Ohne vollständige Zuordnung werden trotzdem die "
            "Keyboardstellen exportiert."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        scroll.setWidget(self._rows_container)
        layout.addWidget(scroll, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 12px;"
        )
        layout.addWidget(self._status_label)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self._continue_btn = QPushButton("Weiter ▶")
        self._continue_btn.setProperty("class", "primary")
        self._continue_btn.setMinimumWidth(140)
        self._continue_btn.setMinimumHeight(40)
        self._continue_btn.clicked.connect(self._on_continue)
        bottom.addWidget(self._continue_btn)
        layout.addLayout(bottom)

    def set_session(self, session, video_files):
        self.session = session
        self._state = build_assignment_state(session, video_files)
        self._render_rows()
        self._start_thumbnails(list(video_files))

    def _start_thumbnails(self, video_paths):
        self._stop_thumbnail_worker()
        if not video_paths:
            return
        thumb_dir = os.path.join(TEMP_DIR, "assignment_thumbs")
        self._thumb_worker = ThumbnailWorker(video_paths, thumb_dir)
        self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_worker.start()

    def _on_thumbnail_ready(self, video_path, thumb_path):
        label = self._thumb_labels.get(video_path)
        if label is None:
            return
        pixmap = QPixmap(thumb_path)
        if pixmap.isNull():
            return
        label.setText("")
        label.setPixmap(
            pixmap.scaled(
                label.width(),
                label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _stop_thumbnail_worker(self):
        if self._thumb_worker is not None:
            if self._thumb_worker.isRunning():
                self._thumb_worker.wait(3000)
            self._thumb_worker = None

    def _clear_rows(self):
        self._camera_widgets = []
        self._mic_widgets = []
        self._thumb_labels = {}
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_rows(self):
        self._clear_rows()
        if self._state is None:
            return

        people = list(self._state.people)

        cam_header = QLabel("Kameras")
        cam_header.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: 600;"
        )
        self._rows_layout.addWidget(cam_header)

        for row in self._state.camera_rows:
            self._rows_layout.addWidget(self._build_camera_row(row, people))

        mic_header = QLabel("Mikrofone")
        mic_header.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: 600; margin-top: 8px;"
        )
        self._rows_layout.addWidget(mic_header)

        for row in self._state.mic_rows:
            self._rows_layout.addWidget(self._build_mic_row(row, people))

        self._rows_layout.addStretch()
        self._refresh_status()

    def _build_camera_row(self, row: CameraRow, people: list[str]) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)

        thumb = QLabel("…")
        thumb.setFixedSize(120, 68)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            "background:#2a2a2a; color:#888; border-radius:4px;"
        )
        self._thumb_labels[row.path] = thumb
        grid.addWidget(thumb, 0, 0, 2, 1)

        name = QLabel(row.filename)
        name.setStyleSheet(f"color: {COLORS['text_primary']};")
        grid.addWidget(name, 0, 1, 1, 3)

        shot_combo = QComboBox()
        shot_combo.setEditable(True)
        for label, const in SHOT_CHOICES:
            shot_combo.addItem(label, const)
        self._select_shot(shot_combo, row.shot_type)
        grid.addWidget(shot_combo, 1, 1)

        person_combo = QComboBox()
        person_combo.setEditable(True)
        person_combo.addItems(people)
        if row.person:
            person_combo.setCurrentText(row.person)
        grid.addWidget(person_combo, 1, 2)

        def _sync_person_enabled():
            const = self._shot_value(shot_combo)
            person_combo.setEnabled(
                const is not None and const not in PERSONLESS_SHOT_TYPES
            )

        shot_combo.currentTextChanged.connect(lambda _=None: _sync_person_enabled())
        _sync_person_enabled()

        self._camera_widgets.append((row, shot_combo, person_combo))
        return container

    def _build_mic_row(self, row: MicRow, people: list[str]) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)

        name = QLabel(row.filename)
        name.setStyleSheet(f"color: {COLORS['text_primary']};")
        name.setMinimumWidth(220)
        h.addWidget(name)

        person_combo = QComboBox()
        person_combo.setEditable(True)
        person_combo.addItems(people)
        person_combo.setCurrentText(row.person)
        h.addWidget(person_combo)

        preview_btn = QPushButton("▶ Hörprobe")
        preview_btn.clicked.connect(lambda _=None, r=row: self._play_mic_preview(r))
        h.addWidget(preview_btn)
        h.addStretch()

        self._mic_widgets.append((row, person_combo))
        return container

    def _play_mic_preview(self, row: MicRow):
        start_s = preview_start_s_for_mic(self.session, row.speaker_key)
        worker = MicPreviewWorker(row.path, start_s=start_s)
        worker.finished.connect(lambda w=worker: self._preview_workers.remove(w)
                                if w in self._preview_workers else None)
        self._preview_workers.append(worker)
        worker.start()

    def _select_shot(self, combo: QComboBox, value: str | None):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        if value:
            combo.setCurrentText(value)

    def _shot_value(self, combo: QComboBox) -> str | None:
        idx = combo.currentIndex()
        text = combo.currentText().strip()
        if idx >= 0 and combo.itemText(idx) == text:
            return combo.itemData(idx)
        return text

    def _collect_into_state(self):
        if self._state is None:
            return
        for row, shot_combo, person_combo in self._camera_widgets:
            row.shot_type = self._shot_value(shot_combo)
            person = person_combo.currentText().strip()
            row.person = person or None
        for row, person_combo in self._mic_widgets:
            row.person = person_combo.currentText().strip()

    def _refresh_status(self):
        if self._state is None:
            return
        if self._state.is_complete():
            self._status_label.setText("Zuordnung vollständig — Folgenschnitt-XML wird erzeugt.")
        else:
            self._status_label.setText(
                "Folgenschnitt-Zuordnung unvollständig — Keyboardstellen werden "
                "trotzdem exportiert."
            )

    def apply_to_session(self):
        if self.session is None or self._state is None:
            return
        self._collect_into_state()
        self.session.folgenschnitt_mic_assignments = self._state.to_mic_assignments()
        self.session.folgenschnitt_camera_assignments = self._state.to_camera_assignments()

    def _on_continue(self):
        self.apply_to_session()
        self._refresh_status()
        self.continue_clicked.emit()

    def cleanup(self):
        """Stop background workers. Called from MainWindow.closeEvent."""
        self._stop_thumbnail_worker()
        for worker in list(self._preview_workers):
            if worker.isRunning():
                worker.wait(3000)
        self._preview_workers = []
