# peak_timeline.py - Custom Timeline Widget with Peak Markers

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

from .apple_style import COLORS


class PeakTimeline(QWidget):
    """Custom timeline widget with peak markers."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms (from user interaction)
    peak_clicked = pyqtSignal(int)  # peak index

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration_ms = 0
        self._position_ms = 0
        self._peaks_ms = []
        self._current_peak_index = -1
        self._is_dragging = False

        # Colors
        self._bg_color = QColor("#3a3a3a")
        self._progress_color = QColor("#007AFF")
        self._handle_color = QColor("#ffffff")
        self._peak_color = QColor("#888888")
        self._current_peak_color = QColor("#FF9500")  # Orange for current peak

        # Dimensions
        self._track_height = 6
        self._handle_radius = 8
        self._peak_width = 2
        self._peak_height = 16

        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_duration(self, duration_ms: int):
        """Set total duration in milliseconds."""
        self._duration_ms = max(1, duration_ms)
        self.update()

    def set_position(self, position_ms: int):
        """Set current position in milliseconds."""
        if not self._is_dragging:
            self._position_ms = max(0, min(position_ms, self._duration_ms))
            self.update()

    def set_peaks(self, peaks_ms: list):
        """Set peak positions in milliseconds."""
        self._peaks_ms = peaks_ms
        self.update()

    def set_current_peak(self, index: int):
        """Set the currently highlighted peak."""
        self._current_peak_index = index
        self.update()

    def get_position(self) -> int:
        """Get current position in milliseconds."""
        return self._position_ms

    def _pos_to_ms(self, x: int) -> int:
        """Convert x position to milliseconds."""
        if self._duration_ms == 0:
            return 0
        track_rect = self._get_track_rect()
        ratio = (x - track_rect.left()) / track_rect.width()
        ratio = max(0, min(1, ratio))
        return int(ratio * self._duration_ms)

    def _ms_to_pos(self, ms: int) -> int:
        """Convert milliseconds to x position."""
        if self._duration_ms == 0:
            return 0
        track_rect = self._get_track_rect()
        ratio = ms / self._duration_ms
        return int(track_rect.left() + ratio * track_rect.width())

    def _get_track_rect(self) -> QRect:
        """Get the track rectangle (excluding handle margins)."""
        margin = self._handle_radius + 2
        return QRect(
            margin,
            (self.height() - self._track_height) // 2,
            self.width() - 2 * margin,
            self._track_height
        )

    def _find_peak_at_pos(self, x: int) -> int:
        """Find peak index at x position, or -1 if none."""
        click_tolerance = 10  # pixels
        for i, peak_ms in enumerate(self._peaks_ms):
            peak_x = self._ms_to_pos(peak_ms)
            if abs(x - peak_x) <= click_tolerance:
                return i
        return -1

    def paintEvent(self, event):
        """Draw the timeline with peaks."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_rect = self._get_track_rect()

        # Draw background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._bg_color))
        painter.drawRoundedRect(track_rect, 3, 3)

        # Draw progress
        if self._duration_ms > 0 and self._position_ms > 0:
            progress_width = int(track_rect.width() * self._position_ms / self._duration_ms)
            progress_rect = QRect(
                track_rect.left(),
                track_rect.top(),
                progress_width,
                track_rect.height()
            )
            painter.setBrush(QBrush(self._progress_color))
            painter.drawRoundedRect(progress_rect, 3, 3)

        # Draw peak markers
        center_y = self.height() // 2
        for i, peak_ms in enumerate(self._peaks_ms):
            peak_x = self._ms_to_pos(peak_ms)

            # Choose color based on whether this is the current peak
            if i == self._current_peak_index:
                color = self._current_peak_color
                width = self._peak_width + 1
                height = self._peak_height + 4
            else:
                color = self._peak_color
                width = self._peak_width
                height = self._peak_height

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(
                peak_x - width // 2,
                center_y - height // 2,
                width,
                height
            )

        # Draw handle
        handle_x = self._ms_to_pos(self._position_ms)
        handle_y = self.height() // 2

        # Handle shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
        painter.drawEllipse(
            handle_x - self._handle_radius,
            handle_y - self._handle_radius + 1,
            self._handle_radius * 2,
            self._handle_radius * 2
        )

        # Handle
        painter.setBrush(QBrush(self._handle_color))
        painter.drawEllipse(
            handle_x - self._handle_radius,
            handle_y - self._handle_radius,
            self._handle_radius * 2,
            self._handle_radius * 2
        )

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked on a peak
            peak_index = self._find_peak_at_pos(event.pos().x())
            if peak_index >= 0:
                self.peak_clicked.emit(peak_index)
                return

            # Otherwise, seek to position
            self._is_dragging = True
            self._update_position_from_mouse(event.pos().x())

    def mouseMoveEvent(self, event):
        """Handle mouse drag."""
        if self._is_dragging:
            self._update_position_from_mouse(event.pos().x())

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False

    def _update_position_from_mouse(self, x: int):
        """Update position from mouse x coordinate."""
        new_pos = self._pos_to_ms(x)
        self._position_ms = new_pos
        self.update()
        self.position_changed.emit(new_pos)
