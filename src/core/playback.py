import simpleaudio as sa

from utils import get_logger

_log = get_logger("peakcut.playback")
_PLAYBACK_SAMPLE_RATE = 44100
_PLAYBACK_SAMPLE_WIDTH = 2  # 16-bit audio (bytes per sample)
_PLAYBACK_CHANNELS = 1

_current_playback = None


def play_audio(segment):
    """Play an AudioSegment via simpleaudio."""
    global _current_playback
    audio_data = segment.set_channels(_PLAYBACK_CHANNELS).set_frame_rate(_PLAYBACK_SAMPLE_RATE).set_sample_width(_PLAYBACK_SAMPLE_WIDTH)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        _current_playback = sa.play_buffer(raw, _PLAYBACK_CHANNELS, _PLAYBACK_SAMPLE_WIDTH, _PLAYBACK_SAMPLE_RATE)
    except (sa.SimpleaudioError, OSError) as e:
        _log.error("Audio playback error: %s", e)


def is_playing():
    """Check if audio is currently playing."""
    if _current_playback is None:
        return False
    try:
        return _current_playback.is_playing()
    except (sa.SimpleaudioError, OSError):
        return False


def stop_playback():
    """Stop all audio playback."""
    global _current_playback
    try:
        sa.stop_all()
    except (sa.SimpleaudioError, OSError) as e:
        _log.error("Stop playback error: %s", e)
    _current_playback = None
