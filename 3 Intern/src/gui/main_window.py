# main_window.py - PeakCut Main Window (PyQt6)

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStatusBar, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .apple_style import get_stylesheet, COLORS


class MainWindow(QMainWindow):
    """PeakCut Main Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeakCut")
        self.setMinimumSize(1000, 600)
        self.resize(1200, 700)

        self._setup_ui()
        self._setup_statusbar()

    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header with title
        header = QLabel("PeakCut")
        header.setProperty("class", "title")
        header.setFont(QFont("-apple-system", 24, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(header)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # Load Video button
        self.load_btn = QPushButton("Video laden")
        self.load_btn.setProperty("class", "primary")
        self.load_btn.setMinimumWidth(120)
        self.load_btn.clicked.connect(self._on_load_video)
        button_layout.addWidget(self.load_btn)

        # Analyze button
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setMinimumWidth(100)
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.analyze_btn.setEnabled(False)
        button_layout.addWidget(self.analyze_btn)

        # Export button
        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumWidth(100)
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Video preview area (placeholder)
        self.preview_frame = QFrame()
        self.preview_frame.setProperty("class", "card")
        self.preview_frame.setMinimumHeight(400)
        self.preview_frame.setStyleSheet(f"""
            QFrame[class="card"] {{
                background-color: #1a1a1a;
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)

        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel("Kein Video geladen")
        self.preview_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)

        main_layout.addWidget(self.preview_frame, stretch=1)

        # Playback controls (placeholder)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.back_btn = QPushButton("Back")
        self.back_btn.setEnabled(False)
        controls_layout.addWidget(self.back_btn)

        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        controls_layout.addWidget(self.next_btn)

        controls_layout.addStretch()

        self.peak_label = QLabel("Peak: - / -")
        self.peak_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        controls_layout.addWidget(self.peak_label)

        main_layout.addLayout(controls_layout)

    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Bereit")

    def _on_load_video(self):
        """Handle load video button."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Video laden",
            "",
            "Video Files (*.mp4 *.mov *.avi);;All Files (*)"
        )
        if filepath:
            self.statusbar.showMessage(f"Geladen: {filepath}")
            self.preview_label.setText(f"Video: {filepath.split('/')[-1]}")
            self.analyze_btn.setEnabled(True)

    def _on_analyze(self):
        """Handle analyze button."""
        self.statusbar.showMessage("Analyzing...")
        # TODO: Implement peak analysis
        self.export_btn.setEnabled(True)
        self.back_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.peak_label.setText("Peak: 1 / 5")
        self.statusbar.showMessage("Analysis complete: 5 peaks found")

    def _on_export(self):
        """Handle export button."""
        self.statusbar.showMessage("Exporting...")
        # TODO: Implement export
        self.statusbar.showMessage("Export complete")
