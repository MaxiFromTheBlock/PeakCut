# main_window.py - PeakCut Main Window (Welcome → Analysis → Review)

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QFileDialog,
    QStackedWidget, QInputDialog,
)
from PyQt6.QtCore import Qt

from .apple_style import COLORS, get_stylesheet
from .workers import AnalysisWorker, TranscriptWorker
from .assignment_page import AssignmentPage
from .review_page import ReviewPage

import config
from utils import get_logger, validate_media_file
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.playback import stop_playback
from core.project_archive import (
    find_project_archive_for_files, load_project_archive,
    save_project_archive, ProjectArchiveError,
)

_log = get_logger("peakcut.gui")
_WORKER_SHUTDOWN_WAIT_MS = 3000


def _on_transcript_finished(ref, *, autosave, review):
    """#3-Rev Task 6 + Pin 2: TranscriptWorker.finished-Vertrag.

    {} (oder ref ohne path/audio_fingerprint) = kontrollierter Skip
    (kein Mix/Timeout/Fehler/Stop) -> autosave kümmert sich um den
    Stand (z. B. transcript_error), aber Job B NICHT anstoßen.
    Echter Ref mit `path` UND `audio_fingerprint` -> Review
    benachrichtigen, Job B im Hintergrund starten lassen.
    Fortschritt/Fehler laufen über `progress`, nicht über Fake-Refs.
    """
    autosave()
    if not isinstance(ref, dict):
        return
    if not ref.get("path") or not ref.get("audio_fingerprint"):
        return
    if review is not None:
        review._maybe_start_smart_worker()


def default_import_folder() -> str:
    """Import dialog always starts at the Desktop. Each episode is its own
    folder, so remembering the last one was unhelpful (it stuck deep in the
    P8 mic subfolder); Desktop is predictable and fast."""
    return os.path.expanduser("~/Desktop")


class MainWindow(QMainWindow):
    """PeakCut Main Window — Welcome → Analysis → Review"""

    def __init__(self, cli_guest: str = None, cli_export_dir: str = None):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        self.session = None
        self._worker = None
        self._transcript_worker = None  # Roadmap #3 Stufe A (entkoppelt)

        # CLI arguments from CheckIn
        self._cli_guest = cli_guest
        self._cli_export_dir = cli_export_dir

        # File state
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []
        self._guest_name = cli_guest  # Pre-fill from CLI if provided

        self._setup_ui()
        self.setStyleSheet(get_stylesheet())

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self._setup_welcome_page()    # 0
        self._setup_analysis_page()   # 1

        # Assignment step (own encapsulated widget)
        self.assignment_page = AssignmentPage()
        self.assignment_page.continue_clicked.connect(self._on_assignment_continue)
        self.stack.addWidget(self.assignment_page)  # 2

        # Review page (own widget)
        self.review_page = ReviewPage()
        self.review_page.status_message.connect(self._on_status_message)
        self.review_page.session_changed.connect(self._autosave)
        self.stack.addWidget(self.review_page)  # 3

        self.stack.setCurrentIndex(0)

        # Status bar
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

    # ══════════════════════════════════════════════════════════════
    # PAGE 0: Welcome
    # ══════════════════════════════════════════════════════════════

    def _setup_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("PeakCut")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 48px; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(40)

        btn = QPushButton("Import Files")
        btn.setProperty("class", "primary")
        btn.setMinimumWidth(180)
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._on_import)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════
    # PAGE 1: Analysis (wait screen)
    # ══════════════════════════════════════════════════════════════

    def _setup_analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.analysis_label = QLabel("Analyse läuft...")
        self.analysis_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px;")
        self.analysis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.analysis_label)

        layout.addSpacing(20)

        self.analysis_status = QLabel("Starte...")
        self.analysis_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        self.analysis_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.analysis_status)

        self.stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════
    # Import & Analysis
    # ══════════════════════════════════════════════════════════════

    def _on_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Dateien auswählen", default_import_folder(),
            "Media Files (*.wav *.mp3 *.mp4 *.mov);;All Files (*)"
        )
        if not files:
            return

        _log.info("Import: %d files selected", len(files))
        self._categorize_files(files)

        if not self._keyboard_file:
            audio_files = [f for f in files if f.lower().endswith(('.wav', '.mp3'))]
            if not audio_files:
                self.statusbar.showMessage("Keine Audio-Dateien gefunden")
                return
            items = [os.path.basename(f) for f in audio_files]
            item, ok = QInputDialog.getItem(
                self, "Keyboard-Spur wählen",
                "Welche Datei ist die Keyboard-Spur?",
                items, 0, False
            )
            if not ok:
                return
            idx = items.index(item)
            self._keyboard_file = audio_files[idx]
            self._mic_files = [f for f in audio_files if f != self._keyboard_file]

        # Validate all files before starting analysis
        all_files = [self._keyboard_file] + self._mic_files + self._video_files
        for f in all_files:
            error = validate_media_file(f)
            if error:
                _log.error("File validation failed: %s", error)
                self.statusbar.showMessage(error)
                return

        # HC-4: vorhandene Projektakte? Dann Analyse überspringen.
        archive = find_project_archive_for_files(all_files)
        if archive and self._load_from_archive(archive):
            return

        # Auto-detect guest name, let user confirm/edit
        from core.guest_name import extract_guest_name
        detected_name = extract_guest_name(all_files)
        guest_name, ok = QInputDialog.getText(
            self, "Gastname",
            "Gastname für Exports:",
            text=detected_name,
        )
        if not ok:
            return
        self._guest_name = guest_name.strip() or detected_name

        self._start_analysis()

    def _categorize_files(self, files):
        self._keyboard_file = None
        self._mic_files = []
        self._video_files = []

        audio_files = []
        for filepath in files:
            filename = os.path.basename(filepath).lower()
            if filename.endswith(('.mp4', '.mov')):
                self._video_files.append(filepath)
            elif filename.endswith(('.wav', '.mp3')):
                audio_files.append(filepath)
                if any(kw in filename for kw in ["keyboard", "keys", "klavier"]):
                    self._keyboard_file = filepath

        for f in audio_files:
            if f != self._keyboard_file:
                self._mic_files.append(f)

    def _start_analysis(self):
        _log.info("Analysis starting: keyboard=%s, %d mics, %d videos",
                  self._keyboard_file, len(self._mic_files), len(self._video_files))
        self.stack.setCurrentIndex(1)  # Show analysis page
        self.analysis_status.setText("Starte Analyse...")

        project = PeakCutProject()
        project.set_files(self._keyboard_file, self._mic_files, self._video_files)
        if self._guest_name:
            project.guest_name = self._guest_name
        if self._cli_export_dir:
            project.export_dir = self._cli_export_dir

        self.session = PeakCutSession(project, config.load())

        self._worker = AnalysisWorker(self.session)
        self._worker.finished.connect(self._on_analysis_done)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.start()

        # Roadmap #3 Stufe A: Transkription früh & parallel anstoßen —
        # NACH AnalysisWorker.start(), eigener entkoppelter Job,
        # bremst den Analyse-/Keyboardstellen-Weg nie. Notbremse:
        # smart_boundary_enabled=False -> läuft gar nicht. Kein Mix ->
        # Worker skippt selbst kontrolliert.
        if config.get("smart_boundary_enabled"):
            self._transcript_worker = TranscriptWorker(self.session)
            self._transcript_worker.progress.connect(
                self._on_analysis_progress)
            # #3-Rev Task 6 + Pin 2: bei echtem Ref Autosave anstoßen
            # UND Review benachrichtigen, damit Job B im Hintergrund
            # startet. {}/Stub-Ref -> nur Autosave, kein Job B.
            self._transcript_worker.finished.connect(
                lambda ref: _on_transcript_finished(
                    ref, autosave=self._autosave, review=self.review_page))
            self._transcript_worker.start()

    def _load_from_archive(self, archive) -> bool:
        """HC-4: Projektakte laden, Analyse überspringen. Bei Fehler
        kontrollierter Hinweis + Rückfall auf den normalen Flow (False)."""
        try:
            self.session = load_project_archive(archive, config.load())
        except ProjectArchiveError as e:
            _log.error("Projektakte nicht ladbar: %s", e)
            self.statusbar.showMessage(f"Projektakte nicht ladbar: {e}")
            return False
        self._video_files = list(self.session.project.videos)
        if self._cli_export_dir:
            self.session.project.export_dir = self._cli_export_dir
        if self.session.folgenschnitt_assignment_applied:
            self.review_page.set_session(self.session, self._video_files)
            self.stack.setCurrentIndex(3)
            self.review_page.navigate_to_peak(0)
            self.statusbar.showMessage(
                "Projektakte geladen — Analyse übersprungen")
        else:
            self.assignment_page.set_session(self.session, self._video_files)
            self.stack.setCurrentIndex(2)
            self.statusbar.showMessage(
                "Projektakte geladen — Zuordnung prüfen")
        return True

    def _autosave(self):
        """Projektakte sichern. Darf NIE Export/Leitplanke/Flow blocken."""
        session = getattr(self, "session", None)
        if session is None:
            return
        try:
            save_project_archive(session)
        except Exception as e:  # bewusst breit: Autosave ist Beiwerk
            _log.warning("Autosave Projektakte fehlgeschlagen: %s", e)
            self.statusbar.showMessage(
                "Hinweis: Projektakte konnte nicht gespeichert werden")

    def _on_analysis_progress(self, msg):
        self.analysis_status.setText(msg)

    def _on_analysis_done(self, results):
        self.session.load_analysis_results(results)

        num_peaks = len(self.session.peaks)
        _log.info("Analysis done: %d peaks, %d video offsets",
                  num_peaks, len(results.get("video_offsets", [])))
        if num_peaks == 0:
            self.analysis_label.setText("Keine Peaks gefunden")
            self.analysis_status.setText("Bitte andere Dateien importieren")
            return

        # Hand off to the encapsulated assignment step (not directly Review)
        self.assignment_page.set_session(self.session, self._video_files)
        self.stack.setCurrentIndex(2)
        self.statusbar.showMessage("Zuordnung prüfen")
        self._autosave()  # HC-4: nach erfolgreicher Analyse sichern

    def _on_assignment_continue(self):
        self.assignment_page.apply_to_session()
        self.review_page.set_session(self.session, self._video_files)
        self.stack.setCurrentIndex(3)
        self.review_page.navigate_to_peak(0)
        self.statusbar.showMessage(f"{len(self.session.peaks)} Peaks gefunden")
        self._autosave()  # HC-4: nach Zuordnung sichern

    def _on_analysis_error(self, msg):
        _log.error("Analysis error: %s", msg)
        self.analysis_label.setText("Fehler")
        self.analysis_status.setText(msg)

    def _on_status_message(self, msg):
        self.statusbar.showMessage(msg)

    # ══════════════════════════════════════════════════════════════
    # Keyboard Shortcuts
    # ══════════════════════════════════════════════════════════════

    def keyPressEvent(self, event):
        if self.stack.currentIndex() != 3:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key.Key_Right:
            self.review_page.on_next()
        elif key == Qt.Key.Key_Left:
            self.review_page.on_back()
        elif key == Qt.Key.Key_Space:
            self.review_page.on_play()
        elif key == Qt.Key.Key_I or event.text() == 'i':
            self.review_page.on_ignore()
        elif key == Qt.Key.Key_S or event.text() == 's':
            self.review_page.on_screenshot()
        else:
            super().keyPressEvent(event)

    # ══════════════════════════════════════════════════════════════
    # Cleanup
    # ══════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        self._autosave()  # HC-4: letzter Sicherungsanker (guarded)
        self.assignment_page.cleanup()
        self.review_page.cleanup()

        if self._worker:
            # Nur noch über die öffentliche Lifecycle-API — kein Zugriff
            # mehr auf Prozess-Interna (beendet Dev- UND Frozen-Pfad).
            self._worker.request_stop()
            if self._worker.isRunning():
                self._worker.wait(_WORKER_SHUTDOWN_WAIT_MS)

        if self._transcript_worker:
            # Roadmap #3: langer Job — sauber abbrechbar (HC-2-Stil),
            # kein blindes wait(). App-Schließen weder hängen noch
            # unkontrolliert abreißen.
            self._transcript_worker.request_stop()
            if self._transcript_worker.isRunning():
                self._transcript_worker.wait(_WORKER_SHUTDOWN_WAIT_MS)

        stop_playback()
        event.accept()
