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
    assert round(r["cuts_per_min"], 3) == round(3 / (160 / 60), 3)
    assert r["camera_clip_counts"] == {"CAM_A": 2, "CAM_B": 1}
    # 5-min buckets: whole episode (2.67 min) is in bucket 0
    assert r["cuts_per_min_buckets"][0]["clips"] == 3
