"""
Video Preview Widget - Displays video with scrubbing timeline
"""
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap

from ..core.video_analyzer import VideoAnalyzer, VideoInfo


class VideoPreviewWidget(QWidget):
    """Widget for video preview with timeline scrubbing."""

    frame_selected = pyqtSignal(int)  # Emitted when user wants to add current frame
    position_changed = pyqtSignal(int, float)  # frame_number, timestamp

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_analyzer = VideoAnalyzer()
        self.current_frame_number = 0
        self.lut_preview_enabled = False
        self.lut_processor = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video container card
        self.video_card = QFrame()
        self.video_card.setProperty("class", "card")
        self.video_card.setStyleSheet("""
            QFrame[class="card"] {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
        """)
        video_card_layout = QVBoxLayout(self.video_card)
        video_card_layout.setContentsMargins(12, 12, 12, 12)
        video_card_layout.setSpacing(12)

        # Video display label
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 300)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 6px;")
        video_card_layout.addWidget(self.video_label)

        # Timeline controls - inside video card
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(12)

        self.time_label = QLabel("00:00.00")
        self.time_label.setMinimumWidth(70)
        self.time_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.time_label)

        # Custom styled slider for better visibility
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(100)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setMinimumHeight(30)
        self.timeline_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeline_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background-color: #3a3a3a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background-color: #ffffff;
                border: none;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #007AFF;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background-color: #007AFF;
                border-radius: 3px;
            }
        """)
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        timeline_layout.addWidget(self.timeline_slider, stretch=1)

        self.duration_label = QLabel("00:00.00")
        self.duration_label.setMinimumWidth(70)
        self.duration_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500;")
        timeline_layout.addWidget(self.duration_label)

        video_card_layout.addLayout(timeline_layout)

        # Playback controls - inside video card
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Frame navigation buttons
        nav_button_style = """
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                min-width: 36px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #5a5a5a;
            }
        """

        self.prev_frame_btn = QPushButton("\u25c0")
        self.prev_frame_btn.setStyleSheet(nav_button_style)
        self.prev_frame_btn.setToolTip("Vorheriges Frame (Pfeiltaste links)")
        self.prev_frame_btn.clicked.connect(self._prev_frame)
        controls_layout.addWidget(self.prev_frame_btn)

        self.next_frame_btn = QPushButton("\u25b6")
        self.next_frame_btn.setStyleSheet(nav_button_style)
        self.next_frame_btn.setToolTip("Nächstes Frame (Pfeiltaste rechts)")
        self.next_frame_btn.clicked.connect(self._next_frame)
        controls_layout.addWidget(self.next_frame_btn)

        controls_layout.addStretch()

        self.add_frame_btn = QPushButton("+ Frame hinzufügen")
        self.add_frame_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-weight: 600;
                padding: 8px 16px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #5a5a5a;
            }
        """)
        self.add_frame_btn.setToolTip("Aktuelles Frame zur Auswahl hinzufügen (Leertaste)")
        self.add_frame_btn.clicked.connect(self._add_current_frame)
        controls_layout.addWidget(self.add_frame_btn)

        controls_layout.addStretch()

        self.frame_info_label = QLabel("Frame: 0 / 0")
        self.frame_info_label.setStyleSheet("color: #888888; font-size: 12px;")
        controls_layout.addWidget(self.frame_info_label)

        video_card_layout.addLayout(controls_layout)

        layout.addWidget(self.video_card, stretch=1)

        # Initially disable controls
        self._set_controls_enabled(False)

    def load_video(self, filepath: str) -> bool:
        """Load a video file."""
        video_info = self.video_analyzer.load_video(filepath)
        if video_info is None:
            return False

        # Update timeline
        self.timeline_slider.setMaximum(video_info.frame_count - 1)
        self.timeline_slider.setValue(0)
        self.duration_label.setText(
            VideoAnalyzer.format_timestamp(video_info.duration)
        )

        # Show first frame
        self._seek_to_frame(0)
        self._set_controls_enabled(True)

        return True

    def set_lut_processor(self, lut_processor):
        """Set the LUT processor for preview."""
        self.lut_processor = lut_processor

    def set_lut_preview(self, enabled: bool):
        """Enable/disable LUT preview."""
        self.lut_preview_enabled = enabled
        self._update_display()

    def get_current_frame_number(self) -> int:
        """Get the current frame number."""
        return self.current_frame_number

    def get_video_analyzer(self) -> VideoAnalyzer:
        """Get the video analyzer instance."""
        return self.video_analyzer

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable playback controls."""
        self.timeline_slider.setEnabled(enabled)
        self.prev_frame_btn.setEnabled(enabled)
        self.next_frame_btn.setEnabled(enabled)
        self.add_frame_btn.setEnabled(enabled)

    def _on_slider_changed(self, value: int):
        """Handle timeline slider changes."""
        self._seek_to_frame(value)

    def _seek_to_frame(self, frame_number: int):
        """Seek to a specific frame."""
        self.current_frame_number = frame_number
        self._update_display()

        # Update labels
        if self.video_analyzer.video_info:
            timestamp = frame_number / self.video_analyzer.video_info.fps
            self.time_label.setText(VideoAnalyzer.format_timestamp(timestamp))
            self.frame_info_label.setText(
                f"Frame: {frame_number} / {self.video_analyzer.video_info.frame_count - 1}"
            )
            self.position_changed.emit(frame_number, timestamp)

    def _update_display(self):
        """Update the video display with current frame."""
        frame = self.video_analyzer.get_frame_at_position(self.current_frame_number)
        if frame is None:
            return

        # Apply LUT if enabled
        if self.lut_preview_enabled and self.lut_processor and self.lut_processor.is_loaded():
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = self.lut_processor.apply_to_image(rgb)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Scale to fit label
        label_size = self.video_label.size()
        h, w = rgb.shape[:2]
        scale = min(label_size.width() / w, label_size.height() / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        scaled = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Convert to QPixmap
        qimage = QImage(
            scaled.data,
            new_w, new_h,
            new_w * 3,
            QImage.Format.Format_RGB888
        )
        pixmap = QPixmap.fromImage(qimage)
        self.video_label.setPixmap(pixmap)

    def _prev_frame(self):
        """Go to previous frame."""
        if self.current_frame_number > 0:
            self.timeline_slider.setValue(self.current_frame_number - 1)

    def _next_frame(self):
        """Go to next frame."""
        if self.video_analyzer.video_info:
            max_frame = self.video_analyzer.video_info.frame_count - 1
            if self.current_frame_number < max_frame:
                self.timeline_slider.setValue(self.current_frame_number + 1)

    def _add_current_frame(self):
        """Signal to add current frame to selection."""
        self.frame_selected.emit(self.current_frame_number)

    def resizeEvent(self, event):
        """Handle resize to update video display."""
        super().resizeEvent(event)
        if self.video_analyzer.video_info:
            self._update_display()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Space:
            self._add_current_frame()
        elif event.key() == Qt.Key.Key_Left:
            self._prev_frame()
        elif event.key() == Qt.Key.Key_Right:
            self._next_frame()
        else:
            super().keyPressEvent(event)

    def close_video(self):
        """Close the current video."""
        self.video_analyzer.close()
        self.video_label.clear()
        self.video_label.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self._set_controls_enabled(False)
        self.time_label.setText("00:00.00")
        self.duration_label.setText("00:00.00")
        self.frame_info_label.setText("Frame: 0 / 0")
