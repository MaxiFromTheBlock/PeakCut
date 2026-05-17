import importlib.util
import os

_SPEC = importlib.util.spec_from_file_location(
    "analyze_premiere_xml",
    os.path.join(os.path.dirname(__file__), "..", "scripts",
                 "analyze_premiere_xml.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
analyze_premiere_xml = _mod.analyze_premiere_xml

_XMEML = """<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="5"><sequence><name>Folge</name>
<rate><timebase>25</timebase></rate>
<media><video><track>
  <clipitem><name>CAM_A</name><start>0</start><end>250</end></clipitem>
  <clipitem><name>CAM_B</name><start>250</start><end>1750</end></clipitem>
  <clipitem><name>CAM_A</name><start>1750</start><end>4000</end></clipitem>
</track></video></media></sequence></xmeml>"""


def test_analyze_premiere_xml_basic_stats(tmp_path):
    f = tmp_path / "folge.xml"
    f.write_text(_XMEML, encoding="utf-8")

    r = analyze_premiere_xml(str(f))

    assert r["fps"] == 25
    assert r["clip_count"] == 3
    # durations in seconds: 250/25=10, 1500/25=60, 2250/25=90
    assert r["shot_lengths_s"] == [10.0, 60.0, 90.0]
    assert r["median_s"] == 60.0
    assert r["p25_s"] == 35.0           # inclusive linear interpolation
    assert r["p75_s"] == 75.0
    assert r["min_s"] == 10.0 and r["max_s"] == 90.0
    assert round(r["duration_min"], 4) == round(160 / 60, 4)
    # Carl-Semantik: clips_per_min = n/min, cuts_per_min = (n-1)/min
    assert round(r["clips_per_min"], 3) == round(3 / (160 / 60), 3)
    assert round(r["cuts_per_min"], 3) == round(2 / (160 / 60), 3)
    assert r["camera_clip_counts"] == {"CAM_A": 2, "CAM_B": 1}
    assert r["cuts_per_min_buckets"][0]["clips"] == 3
    # Diagnostik: sauberes synthetisches XML -> alles 0, keine Warnung
    assert r["video_track_count"] == 1
    assert r["v1_clip_count"] == 3 and r["all_video_clip_count"] == 3
    assert r["transition_count"] == 0
    assert r["gap_count"] == 0 and r["gap_total_s"] == 0.0
    assert r["overlap_count"] == 0
    assert r["warnings"] == []


_MESSY = """<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="5"><sequence><name>Folge</name>
<rate><timebase>25</timebase></rate>
<media><video>
<track>
  <clipitem><name>CAM_A</name><start>0</start><end>250</end></clipitem>
  <transitionitem><start>240</start><end>260</end></transitionitem>
  <clipitem><name>CAM_B</name><start>500</start><end>1000</end></clipitem>
  <clipitem><name>CAM_A</name><start>950</start><end>1500</end></clipitem>
  <clipitem><name>NESTED</name><start>1500</start><end>1700</end>
    <sequence><name>inner</name></sequence></clipitem>
</track>
<track>
  <clipitem><name>LowerThird</name><start>100</start><end>300</end></clipitem>
</track>
</video></media></sequence></xmeml>"""


_GAPLESS_UGLY = """<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="5"><sequence><rate><timebase>25</timebase></rate>
<media><video><track>
  <clipitem><name>A</name><start>0</start><end>137</end></clipitem>
  <clipitem><name>B</name><start>137</start><end>401</end></clipitem>
  <clipitem><name>A</name><start>401</start><end>888</end></clipitem>
  <clipitem><name>B</name><start>888</start><end>1234</end></clipitem>
</track></video></media></sequence></xmeml>"""


def test_gapless_ugly_frames_no_false_gaps(tmp_path):
    # Frame-contiguous but not divisible by fps -> must NOT report
    # float-precision phantom gaps/overlaps.
    f = tmp_path / "g.xml"
    f.write_text(_GAPLESS_UGLY, encoding="utf-8")
    r = analyze_premiere_xml(str(f))
    assert r["gap_count"] == 0
    assert r["gap_total_s"] == 0.0
    assert r["overlap_count"] == 0


def test_analyze_premiere_xml_diagnostics(tmp_path):
    f = tmp_path / "messy.xml"
    f.write_text(_MESSY, encoding="utf-8")

    r = analyze_premiere_xml(str(f))

    assert r["video_track_count"] == 2
    assert r["v1_clip_count"] == 4          # V1 clipitems only
    assert r["all_video_clip_count"] == 5   # incl. the V2 lower third
    assert r["transition_count"] == 1
    assert r["gap_count"] == 1              # 250 -> 500 gap (10s)
    assert r["gap_total_s"] == 10.0 and r["max_gap_s"] == 10.0
    assert r["overlap_count"] == 1          # 1000 -> 950 overlap
    msgs = " ".join(r["warnings"])
    assert "V2" in msgs or "weitere Video" in msgs.lower() or "Hauptstatistik" in msgs
    assert "Nested" in msgs or "nested" in msgs
