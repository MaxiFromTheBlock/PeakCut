# assignment_page.py - Folgenschnitt assignment step (between Analysis and Review)

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QScrollArea, QFrame,
    QRadioButton, QButtonGroup, QListView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from utils import TEMP_DIR
from .apple_style import COLORS
from .thumbnail_worker import ThumbnailWorker
from .mic_preview_worker import MicPreviewWorker
from core.folgenschnitt_models import PERSONLESS_SHOT_TYPES
from core.folgenschnitt_multitrack_layout import (
    UNUSED_CLIPS_DISABLE,
    UNUSED_CLIPS_REMOVE,
)
# Qt-freie Datenschicht liegt jetzt im Kern (core/folgenschnitt_assignment.py),
# damit PeakCut-web sie AUFRUFEN kann. Hier nur zurück-importiert (eine Wahrheit,
# kein Nachbau) — bestehende Aufrufer/Tests bleiben unverändert gültig.
from core.folgenschnitt_assignment import (
    AssignmentState,
    CameraRow,
    MicRow,
    NEUTRAL_SHOT_LABEL,
    SHOT_CHOICES,
    build_assignment_state,
    preview_start_s_for_mic,
)


SHOT_COMBO_STYLESHEET = f"""
QComboBox {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_primary']};
}}
QComboBox QAbstractItemView {{
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_primary']};
    selection-background-color: {COLORS['accent_blue']};
    selection-color: white;
}}
"""

# Popup-Stylesheet mit ::item-Regeln: erzwingt Qts eigenes Item-Rendering und
# überschreibt damit den nativen macOS-Highlight. Nur selection-background-color
# (auf der Combo) wird auf macOS ignoriert -> markierte Zeile blieb hellgrau mit
# weißer Schrift = unlesbar. ::item:selected/:hover macht sie blau + weiß = lesbar.
_POPUP_STYLESHEET = f"""
QListView {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    outline: 0;
}}
QListView::item {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    padding: 6px 10px;
}}
QListView::item:selected, QListView::item:hover {{
    background-color: {COLORS['accent_blue']};
    color: white;
}}
"""


def _apply_readable_popup(combo: QComboBox) -> None:
    """macOS-Fix: nicht-natives Popup mit ::item-Regeln, damit die markierte
    Zeile lesbar bleibt (blau + weiß statt weiß-auf-hellgrau)."""
    view = QListView()
    view.setStyleSheet(_POPUP_STYLESHEET)
    combo.setView(view)


def make_shot_combo() -> QComboBox:
    """Shot-Auswahl-Dropdown mit lesbarem (nicht-nativem) Popup."""
    combo = QComboBox()
    combo.setStyleSheet(SHOT_COMBO_STYLESHEET)
    _apply_readable_popup(combo)
    combo.setEditable(True)
    for label, const in SHOT_CHOICES:
        combo.addItem(label, const)
    return combo


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
        # Shared, growing name list: a name typed once becomes selectable
        # everywhere. Nothing is pre-filled.
        self._person_combos: list[QComboBox] = []
        self._person_pool: list[str] = []
        self._build_ui()

    def _register_person_combo(self, combo: QComboBox):
        for name in self._person_pool:
            if combo.findText(name) < 0:
                combo.addItem(name)
        self._person_combos.append(combo)
        combo.lineEdit().editingFinished.connect(
            lambda c=combo: self._commit_person_name(c)
        )

    def _commit_person_name(self, combo: QComboBox):
        name = combo.currentText().strip()
        if not name or name in self._person_pool:
            return
        self._person_pool.append(name)
        for other in self._person_combos:
            if other.findText(name) >= 0:
                continue
            current = other.currentText()
            was_blocked = other.blockSignals(True)
            other.addItem(name)
            other.setCurrentText(current)
            other.blockSignals(was_blocked)

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
            "Der automatische Folgenschnitt nutzt jede sinnvolle Kamera-"
            "Kombination (auch Close/Totale als Fallback) – je vollständiger "
            "die Zuordnung, desto besser das Ergebnis. Ohne vollständige "
            "Zuordnung werden trotzdem die Keyboardstellen exportiert."
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

        # Slice B Task 7 (Carl-Plan 2026-06-03): Export-Options-Block.
        # Multi-Track-Toggle Disable vs. Remove. Liegt bewusst ueber
        # dem Weiter-Button, NICHT im Kamera-Scroll — der Toggle ist
        # eine Export-Einstellung, keine Kamera-Zeile.
        layout.addWidget(self._build_export_options_block())

        bottom = QHBoxLayout()
        bottom.addStretch()
        self._continue_btn = QPushButton("Weiter ▶")
        self._continue_btn.setProperty("class", "primary")
        self._continue_btn.setMinimumWidth(140)
        self._continue_btn.setMinimumHeight(40)
        self._continue_btn.clicked.connect(self._on_continue)
        bottom.addWidget(self._continue_btn)
        layout.addLayout(bottom)

    def _build_export_options_block(self) -> QFrame:
        """Slice B Task 7: Multi-Track-Layout-Toggle als eigener
        Export-Options-Block. Radio-Buttons Disable / Remove."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border_light']}; "
            f"border-radius: 8px; padding: 8px; }}"
        )
        block_layout = QVBoxLayout(frame)
        block_layout.setContentsMargins(12, 8, 12, 8)
        block_layout.setSpacing(4)

        title = QLabel("Export-Einstellungen")
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; "
            f"font-size: 13px; font-weight: 600;"
        )
        block_layout.addWidget(title)

        sub = QLabel("Layout für nicht-aktive Kameras")
        sub.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 12px;"
        )
        block_layout.addWidget(sub)

        radios = QHBoxLayout()
        radios.setSpacing(16)
        self._unused_clips_disable_radio = QRadioButton(
            "Disable (deaktivierte Clips)"
        )
        self._unused_clips_remove_radio = QRadioButton(
            "Remove (Lücken)"
        )
        self._unused_clips_disable_radio.setToolTip(
            "Alle Kameras haben Clips, aber nur die aktive ist sichtbar. "
            "Andere liegen daneben und können per Klick aktiviert werden."
        )
        self._unused_clips_remove_radio.setToolTip(
            "Nur die ausgewählte Kamera-Spur hat Clips, andere sind Lücken. "
            "Sauberer Schnitt-Look."
        )

        # ButtonGroup macht die beiden exklusiv (sonst koennten beide
        # gleichzeitig aktiv sein, wenn sie nicht im selben Parent stehen).
        self._unused_clips_group = QButtonGroup(self)
        self._unused_clips_group.addButton(self._unused_clips_disable_radio)
        self._unused_clips_group.addButton(self._unused_clips_remove_radio)
        # Default-Selection. Wird in set_session ggf. ueberschrieben.
        self._unused_clips_disable_radio.setChecked(True)

        self._unused_clips_disable_radio.toggled.connect(
            self._on_unused_clips_toggle
        )
        self._unused_clips_remove_radio.toggled.connect(
            self._on_unused_clips_toggle
        )

        radios.addWidget(self._unused_clips_disable_radio)
        radios.addWidget(self._unused_clips_remove_radio)
        radios.addStretch()
        block_layout.addLayout(radios)
        return frame

    def _on_unused_clips_toggle(self, checked: bool):
        """Schreibt den aktuellen Radio-Stand in den State."""
        if not checked:
            # Beide Radios feuern 'toggled' — uns interessiert nur das
            # "neu eingeschaltete".
            return
        if self._state is None:
            return
        if self._unused_clips_remove_radio.isChecked():
            self._state.unused_clips_mode = UNUSED_CLIPS_REMOVE
        else:
            self._state.unused_clips_mode = UNUSED_CLIPS_DISABLE

    def _sync_unused_clips_toggle_from_state(self):
        """Setzt die Radio-Selection nach State (z.B. nach set_session)."""
        if self._state is None:
            return
        if self._state.unused_clips_mode == UNUSED_CLIPS_REMOVE:
            self._unused_clips_remove_radio.setChecked(True)
        else:
            self._unused_clips_disable_radio.setChecked(True)

    def set_session(self, session, video_files):
        self.session = session
        self._state = build_assignment_state(session, video_files)
        self._render_rows()
        self._sync_unused_clips_toggle_from_state()
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
        self._person_combos = []
        self._person_pool = []
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render_rows(self):
        self._clear_rows()
        if self._state is None:
            return

        cam_header = QLabel("Kameras")
        cam_header.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: 600;"
        )
        self._rows_layout.addWidget(cam_header)

        for row in self._state.camera_rows:
            self._rows_layout.addWidget(self._build_camera_row(row))

        mic_header = QLabel("Mikrofone")
        mic_header.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-weight: 600; margin-top: 8px;"
        )
        self._rows_layout.addWidget(mic_header)

        for row in self._state.mic_rows:
            self._rows_layout.addWidget(self._build_mic_row(row))

        self._rows_layout.addStretch()
        self._refresh_status()

    def _build_camera_row(self, row: CameraRow) -> QWidget:
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

        shot_combo = make_shot_combo()
        self._select_shot(shot_combo, row.shot_type)
        grid.addWidget(shot_combo, 1, 1)

        person_combo = QComboBox()
        person_combo.setEditable(True)
        _apply_readable_popup(person_combo)
        person_combo.setCurrentText(row.person or "")
        self._register_person_combo(person_combo)
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

    def _build_mic_row(self, row: MicRow) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)

        name = QLabel(row.filename)
        name.setStyleSheet(f"color: {COLORS['text_primary']};")
        name.setMinimumWidth(220)
        h.addWidget(name)

        person_combo = QComboBox()
        person_combo.setEditable(True)
        _apply_readable_popup(person_combo)
        person_combo.setCurrentText(row.person or "")
        self._register_person_combo(person_combo)
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
        # Slice B Task 7: Toggle-Wert ueberlebt Apply + Persistenz (Task 6).
        self.session.folgenschnitt_unused_clips_mode = self._state.unused_clips_mode
        # User has been through the assignment step: an empty result is now
        # a deliberate "incomplete", not a cue to fall back to defaults.
        self.session.folgenschnitt_assignment_applied = True

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
