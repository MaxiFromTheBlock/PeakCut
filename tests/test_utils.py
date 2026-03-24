from utils import parse_timecode_to_ms, ms_to_timecode, ms_to_frames, ms_to_mmss


class TestTimecodeConversions:

    def test_ms_to_timecode_basic(self):
        assert ms_to_timecode(0, 25) == "00:00:00:00"

    def test_ms_to_timecode_one_second(self):
        assert ms_to_timecode(1000, 25) == "00:00:01:00"

    def test_ms_to_timecode_with_frames(self):
        # 1040ms at 25fps = 1s + 1 frame
        assert ms_to_timecode(1040, 25) == "00:00:01:01"

    def test_ms_to_timecode_complex(self):
        # 1 hour, 23 minutes, 45 seconds
        ms = (1 * 3600 + 23 * 60 + 45) * 1000
        assert ms_to_timecode(ms, 25) == "01:23:45:00"

    def test_parse_timecode_roundtrip(self):
        original_ms = 5678000
        fps = 25
        tc = ms_to_timecode(original_ms, fps)
        parsed = parse_timecode_to_ms(tc, fps)
        # Allow 1 frame tolerance due to integer math
        assert abs(parsed - original_ms) < (1000 / fps + 1)

    def test_parse_timecode_negative(self):
        result = parse_timecode_to_ms("-00:00:01:00", 25)
        assert result == -1000

    def test_parse_timecode_invalid(self):
        assert parse_timecode_to_ms("invalid", 25) == 0

    def test_ms_to_frames(self):
        assert ms_to_frames(1000, 25) == 25
        assert ms_to_frames(2000, 30) == 60
        assert ms_to_frames(0, 25) == 0

    def test_ms_to_mmss(self):
        assert ms_to_mmss(0) == "0:00"
        assert ms_to_mmss(61000) == "1:01"
        assert ms_to_mmss(3600000) == "60:00"

    def test_ms_to_mmss_negative_clamped(self):
        assert ms_to_mmss(-1000) == "0:00"
