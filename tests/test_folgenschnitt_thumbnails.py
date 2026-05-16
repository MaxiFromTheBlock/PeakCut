import os

from gui.thumbnail_worker import build_thumbnail_command, thumbnail_path_for_video
from utils import FFMPEG_BIN


def test_thumbnail_output_path_is_stable_for_video_path_and_mtime(tmp_path):
    video = tmp_path / "CAM_A.mp4"
    video.write_bytes(b"fake")
    temp_dir = tmp_path / "thumbs"

    first = thumbnail_path_for_video(str(video), str(temp_dir))
    second = thumbnail_path_for_video(str(video), str(temp_dir))
    assert first == second
    assert first.startswith(str(temp_dir))
    assert first.endswith(".jpg")

    os.utime(video, (1_000_000, 2_000_000))
    after_touch = thumbnail_path_for_video(str(video), str(temp_dir))
    assert after_touch != first


def test_thumbnail_command_uses_ffmpeg_fast_seek_and_small_scale(tmp_path):
    cmd = build_thumbnail_command("/material/CAM_A.mp4", str(tmp_path / "out.jpg"))

    assert cmd[0] == FFMPEG_BIN
    # fast seek: -ss must come before -i
    assert cmd.index("-ss") < cmd.index("-i")
    assert "scale=160:-1" in cmd
    assert "-frames:v" in cmd
    assert cmd[-1] == str(tmp_path / "out.jpg")
