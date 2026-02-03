# video_preview_peak.py - PeakCut Video Preview with Peak Timeline

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from .apple_style import COLORS
from .peak_timeline import PeakTimeline


class PeakVideoPreview(QWidget):
    """Video preview widget with peak timeline for PeakCut."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms
    video_changed = pyqtSignal(str)  # video filepath
    peak_clicked = pyqtSignal(int)  # peak index

    def __init__(self, parent=None):
        super().__init__(parent)

        self._video_files = []
        self._current_video = None
        self._duration_ms = 0
        self._peaks = []  # List of peak positions in ms
        self._current_peak_index = -1
        self._is_seeking = False

        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video container card
        self.video_card = QFrame()
        self.video_card.setProperty("class", "card")
        self.video_card.setStyleSheet(f"""
            QFrame[class="card"] {{
                background-color: #1a1a1a;
                border: 1px solid {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)

        card_layout = QVBoxLayout(self.video_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)

        # Video switcher row
        switcher_layout = QHBoxLayout()
        switcher_layout.setSpacing(8)

        switcher_label = QLabel("Kamera:")
        switcher_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        switcher_layout.addWidget(switcher_label)

        self.video_combo = QComboBox()
        self.video_combo.setMinimumWidth(200)
        self.video_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: #4a4a4a;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888888;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #ffffff;
                selection-background-color: #007AFF;
            }}
        """)
        self.video_combo.currentIndexChanged.connect(self._on_video_selected)
        switcher_layout.addWidget(self.video_combo)

        switcher_layout.addStretch()
        card_layout.addLayout(switcher_layout)

        # Video display
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(300)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        card_layout.addWidget(self.video_widget, stretch=1)

        # Timeline row
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(12)

        self.time_label = QLabel("00:00")
        self.time_label.setMinimumWidth(50)
        self.time_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.time_label)

        # Custom timeline with peak markers
        self.timeline = PeakTimeline()
        self.timeline.position_changed.connect(self._on_timeline_position_changed)
        self.timeline.peak_clicked.connect(self._on_timeline_peak_clicked)
        timeline_layout.addWidget(self.timeline, stretch=1)

        self.duration_label = QLabel("00:00")
        self.duration_label.setMinimumWidth(50)
        self.duration_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.duration_label)

        card_layout.addLayout(timeline_layout)

        layout.addWidget(self.video_card, stretch=1)

    def _setup_player(self):
        """Setup QMediaPlayer."""
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        # Connect signals
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.errorOccurred.connect(self._on_error)

    def set_videos(self, video_files: list):
        """Set the list of video files."""
        self._video_files = video_files
        self.video_combo.clear()

        for i, filepath in enumerate(video_files):
            filename = os.path.basename(filepath)
            self.video_combo.addItem(f"Kamera {i + 1}: {filename}", filepath)

        if video_files:
            self._load_video(video_files[0])

    def set_peaks(self, peaks_ms: list, current_index: int = 0):
        """Set peak positions in milliseconds."""
        self._peaks = peaks_ms
        self._current_peak_index = current_index
        self.timeline.set_peaks(peaks_ms)
        self.timeline.set_current_peak(current_index)

    def set_current_peak(self, index: int):
        """Highlight the current peak."""
        self._current_peak_index = index
        self.timeline.set_current_peak(index)

    def seek_to_peak(self, index: int):
        """Seek video to a specific peak."""
        if 0 <= index < len(self._peaks):
            self._current_peak_index = index
            position_ms = self._peaks[index]
            self.player.setPosition(position_ms)

    def _load_video(self, filepath: str):
        """Load a video file."""
        self._current_video = filepath
        self.player.setSource(QUrl.fromLocalFile(filepath))

        # Show first frame by briefly playing then pausing
        self.player.play()
        QTimer.singleShot(50, self._show_first_frame)

        self.video_changed.emit(filepath)

    def _show_first_frame(self):
        """Pause to show first frame after brief play."""
        self.player.pause()
        self.player.setPosition(0)

    def _on_video_selected(self, index: int):
        """Handle video selection from combo box."""
        if index >= 0 and index < len(self._video_files):
            self._load_video(self._video_files[index])

    def _on_duration_changed(self, duration: int):
        """Handle duration change."""
        self._duration_ms = duration
        self.timeline.set_duration(duration)
        self.duration_label.setText(self._format_time(duration))

    def _on_position_changed(self, position: int):
        """Handle position change during playback."""
        if not self._is_seeking:
            self.timeline.set_position(position)
            self.time_label.setText(self._format_time(position))
            self.position_changed.emit(position)

    def _on_timeline_position_changed(self, position: int):
        """Handle timeline seek from user interaction."""
        self._is_seeking = True
        self.player.setPosition(position)
        self.time_label.setText(self._format_time(position))
        self._is_seeking = False

    def _on_timeline_peak_clicked(self, peak_index: int):
        """Handle click on peak marker."""
        self._current_peak_index = peak_index
        self.timeline.set_current_peak(peak_index)
        if 0 <= peak_index < len(self._peaks):
            self.player.setPosition(self._peaks[peak_index])
        self.peak_clicked.emit(peak_index)

    def _on_error(self, error):
        """Handle player errors."""
        print(f"Video error: {error}, {self.player.errorString()}")

    def _format_time(self, ms: int) -> str:
        """Format milliseconds as MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def play(self):
        """Start playback."""
        self.player.play()

    def pause(self):
        """Pause playback."""
        self.player.pause()

    def stop(self):
        """Stop playback."""
        self.player.stop()

    def is_playing(self) -> bool:
        """Check if video is playing."""
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def get_position(self) -> int:
        """Get current position in ms."""
        return self.player.position()

    def set_position(self, position_ms: int):
        """Set position in ms."""
        self.player.setPosition(position_ms)

    def get_duration(self) -> int:
        """Get video duration in ms."""
        return self._duration_ms
