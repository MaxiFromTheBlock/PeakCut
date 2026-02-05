# peak_timeline.py - Custom Timeline Widget with Peak Markers and Clip In/Out

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

from .apple_style import COLORS


class PeakTimeline(QWidget):
    """Custom timeline widget with peak markers and clip In/Out markers."""

    # Signals
    position_changed = pyqtSignal(int)  # position in ms (from user interaction)
    peak_clicked = pyqtSignal(int)  # peak index
    clip_in_changed = pyqtSignal(int)  # in point in ms
    clip_out_changed = pyqtSignal(int)  # out point in ms

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration_ms = 0
        self._position_ms = 0
        self._peaks_ms = []
        self._current_peak_index = -1
        self._is_dragging = False

        # Clip region state
        self._clip_in_ms = 0
        self._clip_out_ms = 0
        self._has_clip_region = False
        self._dragging_in = False
        self._dragging_out = False

        # Colors
        self._bg_color = QColor("#3a3a3a")
        self._progress_color = QColor("#007AFF")
        self._handle_color = QColor("#ffffff")
        self._peak_color = QColor("#888888")
        self._current_peak_color = QColor("#FF9500")  # Orange for current peak
        self._clip_region_color = QColor(0, 122, 255, 40)  # Semi-transparent blue
        self._clip_in_color = QColor("#30D158")  # Green
        self._clip_out_color = QColor("#FF453A")  # Red

        # Dimensions
        self._track_height = 6
        self._handle_radius = 8
        self._peak_width = 2
        self._peak_height = 16
        self._marker_width = 3
        self._marker_height = 24
        self._marker_hit_tolerance = 8

        self.setMinimumHeight(40)
        self.setMouseTracking(True)
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

    def set_clip_region(self, in_ms: int, out_ms: int):
        """Set clip In/Out region."""
        self._clip_in_ms = in_ms
        self._clip_out_ms = out_ms
        self._has_clip_region = True
        self.update()

    def clear_clip_region(self):
        """Remove clip region display."""
        self._has_clip_region = False
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

    def _find_marker_at_pos(self, x: int) -> str:
        """Find which clip marker is at x position. Returns 'in', 'out', or ''."""
        if not self._has_clip_region:
            return ""
        in_x = self._ms_to_pos(self._clip_in_ms)
        out_x = self._ms_to_pos(self._clip_out_ms)
        if abs(x - in_x) <= self._marker_hit_tolerance:
            return "in"
        if abs(x - out_x) <= self._marker_hit_tolerance:
            return "out"
        return ""

    def paintEvent(self, event):
        """Draw the timeline with peaks and clip region."""
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

        center_y = self.height() // 2

        # Draw clip region (after progress, before peak markers)
        if self._has_clip_region and self._duration_ms > 0:
            in_x = self._ms_to_pos(self._clip_in_ms)
            out_x = self._ms_to_pos(self._clip_out_ms)

            # Semi-transparent blue region
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._clip_region_color))
            region_rect = QRect(
                in_x,
                center_y - self._marker_height // 2,
                out_x - in_x,
                self._marker_height
            )
            painter.drawRect(region_rect)

            # In marker (green)
            painter.setBrush(QBrush(self._clip_in_color))
            painter.drawRect(
                in_x - self._marker_width // 2,
                center_y - self._marker_height // 2,
                self._marker_width,
                self._marker_height
            )

            # Out marker (red)
            painter.setBrush(QBrush(self._clip_out_color))
            painter.drawRect(
                out_x - self._marker_width // 2,
                center_y - self._marker_height // 2,
                self._marker_width,
                self._marker_height
            )

        # Draw peak markers
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
        """Handle mouse press — priority: In/Out marker > Peak > Position."""
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()

            # Check In/Out markers first
            marker = self._find_marker_at_pos(x)
            if marker == "in":
                self._dragging_in = True
                return
            if marker == "out":
                self._dragging_out = True
                return

            # Check if clicked on a peak
            peak_index = self._find_peak_at_pos(x)
            if peak_index >= 0:
                self.peak_clicked.emit(peak_index)
                return

            # Otherwise, seek to position
            self._is_dragging = True
            self._update_position_from_mouse(x)

    def mouseMoveEvent(self, event):
        """Handle mouse drag and cursor changes."""
        x = event.pos().x()

        if self._dragging_in:
            new_ms = self._pos_to_ms(x)
            # Clamp: min 0, max out_point - 1s
            new_ms = max(0, min(new_ms, self._clip_out_ms - 1000))
            self._clip_in_ms = new_ms
            self.update()
            self.clip_in_changed.emit(new_ms)
            return

        if self._dragging_out:
            new_ms = self._pos_to_ms(x)
            # Clamp: min in_point + 1s, max duration
            new_ms = max(self._clip_in_ms + 1000, min(new_ms, self._duration_ms))
            self._clip_out_ms = new_ms
            self.update()
            self.clip_out_changed.emit(new_ms)
            return

        if self._is_dragging:
            self._update_position_from_mouse(x)
            return

        # Hover cursor
        if self._find_marker_at_pos(x):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._dragging_in = False
            self._dragging_out = False

    def _update_position_from_mouse(self, x: int):
        """Update position from mouse x coordinate."""
        new_pos = self._pos_to_ms(x)
        self._position_ms = new_pos
        self.update()
        self.position_changed.emit(new_pos)
