from gui.mic_preview_worker import build_mic_preview_command
from utils import FFMPEG_BIN


def test_mic_preview_command_uses_fast_seek_and_short_duration():
    cmd = build_mic_preview_command("/material/MIC1.wav", duration_s=5.0, start_s=12.5)

    assert cmd[0] == FFMPEG_BIN
    assert "-ss" in cmd
    assert "12.5" in cmd
    assert "-t" in cmd
    assert "5" in cmd or "5.0" in cmd
    # fast seek: -ss before -i
    assert cmd.index("-ss") < cmd.index("-i")
    assert cmd[-2:] == ["wav", "-"]
