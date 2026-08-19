# tests/test_candidate_integration.py
"""Task 4 — Gate-A-Nachweis: ein auto-Kandidat durch den ganzen Datenweg."""
import json

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ORIGIN_AUTO, PROPOSED, SELECTED, transition)
from core.project_archive import load_project_archive, save_project_archive
from core.xml_sequence_helpers import active_smart_candidates
from tests.test_candidate_baseline_lock import make_session_with_peaks

AUTO_ID = "auto:integration"


def test_auto_kandidat_kompletter_datenweg(tmp_path):
    # 1. erzeugen
    session = make_session_with_peaks([60_000, 180_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id=AUTO_ID, origin=ORIGIN_AUTO, anchor_ms=120_000,
        peak_id=None, boundary=ClipBoundary(110_000, 130_000),
        reason="starker Einstieg", score=0.77))
    session._reconcile_marker_candidates()

    # 2. sortiert nach anchor_ms
    assert [c.anchor_ms for c in session.clip_candidates] == [60_000, 120_000, 180_000]

    # 3. Statusuebergang ueber candidate_id
    i = next(i for i, c in enumerate(session.clip_candidates)
             if c.candidate_id == AUTO_ID)
    new, dec = transition(session.clip_candidates[i], SELECTED,
                          now="2026-08-19T12:00:00")
    session.clip_candidates[i] = new
    session.peak_decisions.append(dec)
    assert dec.candidate_id == AUTO_ID

    # 4. Origin-Filter: kein Leck in die Smart-XML
    assert AUTO_ID not in {c.candidate_id for _, c in active_smart_candidates(session)}

    # 5. v6 speichern/laden exakt
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))
    payload = json.loads((root / ".peakcut" / "project.json").read_text())
    assert payload["schema_version"] == 6

    loaded = load_project_archive(str(root), {})
    back = next(c for c in loaded.clip_candidates if c.candidate_id == AUTO_ID)
    assert back.origin == ORIGIN_AUTO
    assert back.anchor_ms == 120_000
    assert back.status == SELECTED
    assert back.score == 0.77
    assert [d.candidate_id for d in loaded.peak_decisions] == [AUTO_ID]

    # 6. Neu-Analyse ueberlebt er
    loaded.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
                   "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False},
                  {"index": 1, "position_ms": 180_000, "in_point_ms": 165_000,
                   "out_point_ms": 195_000, "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    assert AUTO_ID in {c.candidate_id for c in loaded.clip_candidates}
    assert len(loaded.peak_decisions) == 1
