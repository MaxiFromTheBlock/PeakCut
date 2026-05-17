"""The load-bearing bit of the HR recut verifier: 'unknown' in the
cached CSV must map back to None, or pause detection silently breaks."""

import importlib.util
import os

_p = os.path.join(os.path.dirname(__file__), "..", "scripts",
                  "verify_folgenschnitt_recut.py")
_s = importlib.util.spec_from_file_location("vfr", _p)
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)


def test_load_activity_maps_unknown_to_none(tmp_path):
    f = tmp_path / "speaker_activity.csv"
    f.write_text(
        "start_ms,end_ms,mic_1_db,mic_2_db,mic_1_noise_floor_db,"
        "mic_2_noise_floor_db,dominance_db,raw_speaker,smoothed_speaker,"
        "confidence\n"
        "0,200,-44.7,-27.1,-53.4,-50.8,9.2,mic_2,mic_2,1.0\n"
        "200,400,-30.0,-31.0,-53.0,-50.0,1.0,unknown,unknown,0.0\n"
    )
    frames = _m.load_activity(str(f))
    assert len(frames) == 2
    assert frames[0].smoothed_speaker == "mic_2"
    assert frames[1].smoothed_speaker is None
    assert frames[1].raw_speaker is None
    assert frames[0].levels_db == {"mic_1": -44.7, "mic_2": -27.1}
