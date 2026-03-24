from core.peak import Peak


class TestPeak:

    def test_in_point_clamped_to_zero(self):
        peak = Peak(index=0, position_ms=5000, context_ms=15000)
        assert peak.in_point_ms == 0  # 5000 - 15000 = -10000, clamped to 0

    def test_out_point_clamped_to_duration(self):
        peak = Peak(index=0, position_ms=5000, context_ms=15000, duration_ms=10000)
        assert peak.out_point_ms == 10000  # 5000 + 15000 = 20000, clamped to 10000

    def test_out_point_unclamped_without_duration(self):
        peak = Peak(index=0, position_ms=5000, context_ms=15000)
        assert peak.out_point_ms == 20000  # No duration bound

    def test_clip_duration(self):
        peak = Peak(index=0, position_ms=30000, context_ms=15000)
        assert peak.clip_duration_ms == 30000  # 15000 to 45000

    def test_clip_duration_clamped(self):
        peak = Peak(index=0, position_ms=5000, context_ms=15000, duration_ms=10000)
        # in_point = 0 (clamped), out_point = 10000 (clamped)
        assert peak.clip_duration_ms == 10000

    def test_ignored_default_false(self):
        peak = Peak(index=0, position_ms=1000)
        assert peak.ignored is False

    def test_set_in_point(self):
        peak = Peak(index=0, position_ms=30000, context_ms=15000)
        peak.set_in_point(25000)
        assert peak.in_point_ms == 25000

    def test_set_out_point(self):
        peak = Peak(index=0, position_ms=30000, context_ms=15000)
        peak.set_out_point(40000)
        assert peak.out_point_ms == 40000

    def test_reset_offsets(self):
        peak = Peak(index=0, position_ms=30000, context_ms=5000)
        peak.set_in_point(28000)
        peak.set_out_point(35000)
        peak.reset_offsets(15000)
        assert peak.in_point_ms == 15000
        assert peak.out_point_ms == 45000
