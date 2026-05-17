"""Carl-Spec: confidence-gated FCPXML composition estimator.
NOT authoritative — provisional Stage-2 tuning only."""

import importlib.util
import os

_p = os.path.join(os.path.dirname(__file__), "..", "scripts", "analyze_fcpxml.py")
_s = importlib.util.spec_from_file_location("analyze_fcpxml", _p)
_m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_m)
analyze_fcpxml = _m.analyze_fcpxml
camera_key_from_src = _m.camera_key_from_src


def _w(tmp, body):
    f = tmp / "t.fcpxml"
    f.write_text(
        '<?xml version="1.0"?><!DOCTYPE fcpxml><fcpxml version="1.8">'
        '<resources>'
        '<format id="r0" frameDuration="1/25s"/>'
        '<asset id="a1" src="file:///V/HM/Cam%20Matze/MV_1.mp4"/>'
        '<asset id="a2" src="file:///V/HM/Cam%20Schirach/MV_2.mp4"/>'
        '<asset id="a3"><media-rep src="file:///V/P/A_Cam/Card%20001/C0.MP4"/></asset>'
        '<asset id="a4"><media-rep src="file:///V/P/B_Cam/Card%20001/C0.MP4"/></asset>'
        '<asset id="g1" src="file:///V/HM/Logo.png"/>'
        '</resources>'
        '<library><event><project><sequence format="r0" tcStart="0/1s" '
        'duration="2500/25s"><spine>' + body + '</spine></sequence>'
        '</project></event></library></fcpxml>'
    )
    return str(f)


def test_camera_key_path_folder_and_filename(tmp_path):
    assert camera_key_from_src("file:///V/HM/Cam%20Matze/MV_7816.MP4") == "Cam Matze"
    assert camera_key_from_src("file:///V/P/A_Cam/Card%20001/C014.MP4") == "A_Cam"
    assert camera_key_from_src(
        "file:///V/x/Video%20ISO%20Files/HM CAM 3 01.mp4") == "CAM 3"
    # same basename, different folders -> distinguishable
    assert camera_key_from_src("file:///V/B_Cam/Card%20001/C0.MP4") == "B_Cam"
    assert camera_key_from_src("file:///V/C_Cam/Card%20001/C0.MP4") == "C_Cam"


def test_disabled_top_clip_enabled_nested_wins(tmp_path):
    body = (
        '<clip offset="0/25s" duration="500/25s" name="top" enabled="0">'
        '  <video ref="a1"/>'
        '  <clip lane="2" offset="0/25s" duration="500/25s" enabled="1">'
        '    <video ref="a2"/></clip>'
        '</clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    # visible camera is the enabled nested one (Cam Schirach), not disabled top
    shares = dict(r["camera_share_by_duration"])
    assert "Cam Schirach" in shares and "Cam Matze" not in shares


def test_enabled_zero_candidate_ignored(tmp_path):
    body = (
        '<clip offset="0/25s" duration="500/25s" name="top" enabled="1">'
        '  <video ref="a1"/>'
        '  <clip lane="2" offset="0/25s" duration="500/25s" enabled="0">'
        '    <video ref="a2"/></clip>'
        '</clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    shares = dict(r["camera_share_by_duration"])
    assert "Cam Matze" in shares and "Cam Schirach" not in shares


def test_media_rep_src_used_as_asset_source(tmp_path):
    body = (
        '<clip offset="0/25s" duration="500/25s" enabled="1">'
        '  <video ref="a3"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert "A_Cam" in dict(r["camera_share_by_duration"])


def test_adjacent_same_camera_merged_into_run(tmp_path):
    body = (
        '<clip offset="0/25s" duration="250/25s" enabled="1"><video ref="a1"/></clip>'
        '<clip offset="250/25s" duration="250/25s" enabled="1"><video ref="a1"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["run_count"] == 1  # merged, same camera, contiguous


def test_gap_counted_not_shot(tmp_path):
    body = (
        '<clip offset="0/25s" duration="250/25s" enabled="1"><video ref="a1"/></clip>'
        '<gap offset="250/25s" duration="100/25s"/>'
        '<clip offset="350/25s" duration="250/25s" enabled="1"><video ref="a2"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["gap_count"] == 1
    assert round(r["gap_total_s"], 2) == 4.0
    assert r["run_count"] == 2  # gap prevents the merge / two cameras anyway


def test_two_winners_same_lane_ambiguous_excluded(tmp_path):
    body = (
        '<clip offset="0/25s" duration="500/25s" name="top" enabled="1">'
        '  <clip lane="2" offset="0/25s" duration="500/25s" enabled="1">'
        '    <video ref="a1"/></clip>'
        '  <clip lane="2" offset="0/25s" duration="500/25s" enabled="1">'
        '    <video ref="a2"/></clip>'
        '</clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["ambiguous_segment_count"] >= 1


def test_plausibility_brake_dominant_camera(tmp_path):
    # one camera covers 90% -> LOW despite 2 keys & 0% ambiguous
    body = (
        '<clip offset="0/25s" duration="9000/25s" enabled="1">'
        '<video ref="a1"/></clip>'
        '<clip offset="9000/25s" duration="1000/25s" enabled="1">'
        '<video ref="a2"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["confidence"] == "LOW"
    assert any("Dominant camera" in w for w in r["warnings"])
    assert any("base assembly" in w.lower() for w in r["warnings"])


def test_plausibility_brake_long_run(tmp_path):
    # a single run >= 20 min -> LOW (dominant share kept < 0.80)
    body = (
        '<clip offset="0/25s" duration="9000/25s" enabled="1">'
        '<video ref="a1"/></clip>'
        '<clip offset="9000/25s" duration="32500/25s" enabled="1">'
        '<video ref="a2"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["confidence"] == "LOW"
    assert any("Longest run" in w for w in r["warnings"])
    assert any("base assembly" in w.lower() for w in r["warnings"])


def test_confidence_low_when_single_camera(tmp_path):
    body = (
        '<clip offset="0/25s" duration="1000/25s" enabled="1"><video ref="a1"/></clip>'
    )
    r = analyze_fcpxml(_w(tmp_path, body))
    assert r["confidence"] == "LOW"  # only 1 camera key
    assert "not authoritative" in r["disclaimer"].lower()
