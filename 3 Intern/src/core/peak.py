class Peak:
    """Represents a single peak with adjustable In/Out points."""

    def __init__(self, index, position_ms, context_ms=15000, duration_ms=None):
        self.index = index
        self.position_ms = position_ms       # Immutable peak position
        self.in_offset_ms = -context_ms      # Negative = before peak
        self.out_offset_ms = +context_ms     # Positive = after peak
        self.ignored = False
        self._duration_ms = duration_ms      # Total audio duration (for bounds)

    @property
    def in_point_ms(self):
        return max(0, self.position_ms + self.in_offset_ms)

    @property
    def out_point_ms(self):
        out = self.position_ms + self.out_offset_ms
        if self._duration_ms is not None:
            return min(out, self._duration_ms)
        return out

    @property
    def clip_duration_ms(self):
        return self.out_point_ms - self.in_point_ms

    def set_in_point(self, abs_ms):
        self.in_offset_ms = min(0, abs_ms - self.position_ms)

    def set_out_point(self, abs_ms):
        self.out_offset_ms = max(0, abs_ms - self.position_ms)

    def reset_offsets(self, context_ms):
        self.in_offset_ms = -context_ms
        self.out_offset_ms = +context_ms
