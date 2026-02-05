# peak_timeline.py - ScrubTimeline (full-duration) + ClipTimeline (zoomed clip editor)

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class ScrubTimeline(QWidget):
    """Full-duration interactive timeline for scrubbing through the entire recording.

    Shows peak markers (faint), playhead, time labels. Click/drag to seek.
    """

    position_changed = pyqtSignal(int)  # seek position in ms

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration_ms = 0
        self._position_ms = 0
        self._peaks_ms = []
        self._current_peak_index = -1
        self._dragging = False

        # Colors
        self._track_color = QColor("#3a3a3a")
        self._peak_color = QColor("#555555")
        self._current_peak_color = QColor("#FF9500")
        self._playhead_color = QColor("#ffffff")
        self._tick_color = QColor("#666666")
        self._tick_label_color = QColor("#bbbbbb")

        self.setFixedHeight(44)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def set_duration(self, ms: int):
        self._duration_ms = max(1, ms)
        self.update()

    def set_position(self, ms: int):
        if not self._dragging:
            self._position_ms = max(0, min(ms, self._duration_ms))
            self.update()

    def set_peaks(self, peaks_ms: list):
        self._peaks_ms = peaks_ms
        self.update()

    def set_current_peak(self, index: int):
        self._current_peak_index = index
        self.update()

    def _ms_to_x(self, ms: int) -> int:
        if self._duration_ms <= 0:
            return 0
        margin = 8
        w = self.width() - 2 * margin
        return margin + int(w * ms / self._duration_ms)

    def _x_to_ms(self, x: int) -> int:
        if self._duration_ms <= 0:
            return 0
        margin = 8
        w = self.width() - 2 * margin
        if w <= 0:
            return 0
        ratio = max(0.0, min(1.0, (x - margin) / w))
        return int(ratio * self._duration_ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        margin = 8
        track_y = 4
        track_h = h - 8
        track_rect = QRect(margin, track_y, self.width() - 2 * margin, track_h)

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(track_rect, 4, 4)

        if self._duration_ms <= 0:
            painter.end()
            return

        # Time ticks
        tick_font = QFont()
        tick_font.setPixelSize(11)
        painter.setFont(tick_font)

        dur_s = self._duration_ms / 1000
        if dur_s > 3600:
            tick_interval = 300000   # 5 min
        elif dur_s > 600:
            tick_interval = 60000    # 1 min
        else:
            tick_interval = 30000    # 30s

        t = tick_interval
        while t < self._duration_ms:
            tx = self._ms_to_x(t)
            painter.setPen(QPen(self._tick_color, 1))
            painter.drawLine(tx, track_y, tx, track_y + 6)

            secs = t // 1000
            if dur_s > 3600:
                hh = secs // 3600
                mm = (secs % 3600) // 60
                label = f"{hh}:{mm:02d}"
            else:
                label = f"{secs // 60}:{secs % 60:02d}"
            painter.setPen(self._tick_label_color)
            painter.drawText(tx - 22, track_y + track_h + 1, 44, 14,
                             Qt.AlignmentFlag.AlignCenter, label)
            t += tick_interval

        # Peak markers
        for i, peak_ms in enumerate(self._peaks_ms):
            px = self._ms_to_x(peak_ms)
            if i == self._current_peak_index:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._current_peak_color))
                painter.drawRect(px - 1, track_y + 1, 3, track_h - 2)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._peak_color))
                painter.drawRect(px, track_y + 3, 2, track_h - 6)

        # Playhead
        ph_x = self._ms_to_x(self._position_ms)
        painter.setPen(QPen(self._playhead_color, 2))
        painter.drawLine(ph_x, track_y, ph_x, track_y + track_h)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setFocus()
            ms = self._x_to_ms(event.pos().x())
            self._position_ms = ms
            self.update()
            self.position_changed.emit(ms)

    def mouseMoveEvent(self, event):
        if self._dragging:
            ms = self._x_to_ms(event.pos().x())
            self._position_ms = ms
            self.update()
            self.position_changed.emit(ms)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False


class PeakStrip(QWidget):
    """Thin full-duration strip showing all peak markers and current position.

    Height: 20px. No clip editing — that's in ClipTimeline.
    """

    peak_clicked = pyqtSignal(int)  # peak index
    position_changed = pyqtSignal(int)  # position in ms (from click)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration_ms = 0
        self._position_ms = 0
        self._peaks_ms = []
        self._current_peak_index = -1

        # Colors
        self._bg_color = QColor("#2a2a2a")
        self._track_color = QColor("#3a3a3a")
        self._peak_color = QColor("#666666")
        self._current_peak_color = QColor("#FF9500")
        self._playhead_color = QColor("#ffffff")

        self.setFixedHeight(20)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_duration(self, duration_ms: int):
        self._duration_ms = max(1, duration_ms)
        self.update()

    def set_position(self, position_ms: int):
        self._position_ms = max(0, min(position_ms, self._duration_ms))
        self.update()

    def set_peaks(self, peaks_ms: list):
        self._peaks_ms = peaks_ms
        self.update()

    def set_current_peak(self, index: int):
        self._current_peak_index = index
        self.update()

    def _ms_to_x(self, ms: int) -> int:
        if self._duration_ms == 0:
            return 0
        margin = 4
        w = self.width() - 2 * margin
        return margin + int(w * ms / self._duration_ms)

    def _x_to_ms(self, x: int) -> int:
        if self._duration_ms == 0:
            return 0
        margin = 4
        w = self.width() - 2 * margin
        ratio = max(0, min(1, (x - margin) / w))
        return int(ratio * self._duration_ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        margin = 4
        track_rect = QRect(margin, 4, self.width() - 2 * margin, h - 8)

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(track_rect, 3, 3)

        center_y = h // 2

        # Peak markers
        for i, peak_ms in enumerate(self._peaks_ms):
            x = self._ms_to_x(peak_ms)
            if i == self._current_peak_index:
                color = self._current_peak_color
                w = 3
                mh = 14
            else:
                color = self._peak_color
                w = 2
                mh = 10
            painter.setBrush(QBrush(color))
            painter.drawRect(x - w // 2, center_y - mh // 2, w, mh)

        # Playhead (thin white line)
        if self._duration_ms > 0:
            px = self._ms_to_x(self._position_ms)
            painter.setPen(QPen(self._playhead_color, 1.5))
            painter.drawLine(px, 2, px, h - 2)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()
            # Check peaks first (10px tolerance)
            for i, peak_ms in enumerate(self._peaks_ms):
                peak_x = self._ms_to_x(peak_ms)
                if abs(x - peak_x) <= 10:
                    self.peak_clicked.emit(i)
                    return
            # Click on strip = seek
            ms = self._x_to_ms(x)
            self._position_ms = ms
            self.update()
            self.position_changed.emit(ms)


class ClipTimeline(QWidget):
    """Zoomed timeline showing ±30s around the current peak.

    Large draggable In/Out markers for precise clip editing.
    """

    position_changed = pyqtSignal(int)   # seek position in ms
    clip_in_changed = pyqtSignal(int)    # in point in ms
    clip_out_changed = pyqtSignal(int)   # out point in ms

    ZOOM_RANGE_MS = 30000  # ±30s = 60s total visible window

    def __init__(self, parent=None):
        super().__init__(parent)

        self._duration_ms = 0
        self._peak_ms = 0
        self._in_ms = 0
        self._out_ms = 0
        self._position_ms = 0

        # Visible window
        self._window_start_ms = 0
        self._window_end_ms = 0

        # Drag state
        self._dragging_in = False
        self._dragging_out = False
        self._dragging_seek = False

        # Colors
        self._bg_color = QColor("#2a2a2a")
        self._track_color = QColor("#3a3a3a")
        self._clip_color = QColor(0, 122, 255, 50)
        self._peak_color = QColor("#FF9500")
        self._in_color = QColor("#30D158")
        self._out_color = QColor("#FF453A")
        self._playhead_color = QColor("#ffffff")
        self._tick_color = QColor("#666666")
        self._tick_label_color = QColor("#bbbbbb")

        # Marker dimensions
        self._marker_w = 6
        self._marker_h = 30
        self._hit_tolerance = 12
        self._min_clip_ms = 1000

        self.setMinimumHeight(40)
        self.setFixedHeight(44)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def set_duration(self, ms: int):
        self._duration_ms = max(1, ms)
        self._recalc_window()
        self.update()

    def set_peak(self, position_ms: int, in_ms: int, out_ms: int):
        self._peak_ms = position_ms
        self._in_ms = in_ms
        self._out_ms = out_ms
        self._position_ms = position_ms
        self._recalc_window()
        self.update()

    def set_position(self, position_ms: int):
        self._position_ms = position_ms
        self.update()

    def _recalc_window(self):
        self._window_start_ms = max(0, self._peak_ms - self.ZOOM_RANGE_MS)
        self._window_end_ms = min(self._duration_ms, self._peak_ms + self.ZOOM_RANGE_MS)

    def _ms_to_x(self, ms: int) -> int:
        window_dur = self._window_end_ms - self._window_start_ms
        if window_dur <= 0:
            return 0
        margin = 8
        w = self.width() - 2 * margin
        ratio = (ms - self._window_start_ms) / window_dur
        return margin + int(ratio * w)

    def _x_to_ms(self, x: int) -> int:
        margin = 8
        w = self.width() - 2 * margin
        if w <= 0:
            return self._window_start_ms
        ratio = max(0.0, min(1.0, (x - margin) / w))
        window_dur = self._window_end_ms - self._window_start_ms
        return int(self._window_start_ms + ratio * window_dur)

    def _find_marker_at(self, x: int) -> str:
        in_x = self._ms_to_x(self._in_ms)
        out_x = self._ms_to_x(self._out_ms)
        # Out marker gets priority if they overlap (user likely wants to extend)
        if abs(x - out_x) <= self._hit_tolerance:
            return "out"
        if abs(x - in_x) <= self._hit_tolerance:
            return "in"
        return ""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        h = self.height()
        margin = 8
        track_y = 6
        track_h = h - 12
        track_rect = QRect(margin, track_y, self.width() - 2 * margin, track_h)

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(track_rect, 4, 4)

        window_dur = self._window_end_ms - self._window_start_ms
        if window_dur <= 0:
            painter.end()
            return

        center_y = h // 2

        # Time scale ticks (every 5s)
        tick_font = QFont()
        tick_font.setPixelSize(11)
        painter.setFont(tick_font)
        tick_interval = 5000  # 5s
        first_tick = ((self._window_start_ms // tick_interval) + 1) * tick_interval
        t = first_tick
        while t < self._window_end_ms:
            tx = self._ms_to_x(t)
            painter.setPen(QPen(self._tick_color, 1))
            painter.drawLine(tx, track_y, tx, track_y + 6)
            # Label every 10s
            if t % 10000 == 0:
                secs = t // 1000
                m = secs // 60
                s = secs % 60
                label = f"{m}:{s:02d}"
                painter.setPen(self._tick_label_color)
                painter.drawText(tx - 22, track_y + track_h + 1, 44, 14,
                                 Qt.AlignmentFlag.AlignCenter, label)
            t += tick_interval

        # Clip region (highlighted blue between In and Out)
        in_x = self._ms_to_x(self._in_ms)
        out_x = self._ms_to_x(self._out_ms)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._clip_color))
        clip_rect = QRect(in_x, track_y, out_x - in_x, track_h)
        painter.drawRect(clip_rect)

        # Peak center (orange vertical line)
        peak_x = self._ms_to_x(self._peak_ms)
        painter.setPen(QPen(self._peak_color, 2))
        painter.drawLine(peak_x, track_y + 2, peak_x, track_y + track_h - 2)

        # In marker (green)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._in_color))
        painter.drawRoundedRect(
            in_x - self._marker_w // 2,
            center_y - self._marker_h // 2,
            self._marker_w, self._marker_h, 2, 2)

        # Out marker (red)
        painter.setBrush(QBrush(self._out_color))
        painter.drawRoundedRect(
            out_x - self._marker_w // 2,
            center_y - self._marker_h // 2,
            self._marker_w, self._marker_h, 2, 2)

        # Playhead (white line, 2px)
        if (self._window_start_ms <= self._position_ms <= self._window_end_ms):
            ph_x = self._ms_to_x(self._position_ms)
            painter.setPen(QPen(self._playhead_color, 2))
            painter.drawLine(ph_x, track_y, ph_x, track_y + track_h)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()
            marker = self._find_marker_at(x)
            if marker == "in":
                self._dragging_in = True
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
            if marker == "out":
                self._dragging_out = True
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
            # Click = seek
            self._dragging_seek = True
            ms = self._x_to_ms(x)
            self._position_ms = ms
            self.update()
            self.position_changed.emit(ms)

    def mouseMoveEvent(self, event):
        x = event.pos().x()

        if self._dragging_in:
            new_ms = self._x_to_ms(x)
            new_ms = max(0, min(new_ms, self._out_ms - self._min_clip_ms))
            self._in_ms = new_ms
            self.update()
            self.clip_in_changed.emit(new_ms)
            return

        if self._dragging_out:
            new_ms = self._x_to_ms(x)
            new_ms = max(self._in_ms + self._min_clip_ms, min(new_ms, self._duration_ms))
            self._out_ms = new_ms
            self.update()
            self.clip_out_changed.emit(new_ms)
            return

        if self._dragging_seek:
            ms = self._x_to_ms(x)
            self._position_ms = ms
            self.update()
            self.position_changed.emit(ms)
            return

        # Hover cursor
        if self._find_marker_at(x):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_in = False
            self._dragging_out = False
            self._dragging_seek = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
