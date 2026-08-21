# tests/test_candidate_integration.py
"""Task 4 — Gate-A-Nachweis: ein auto-Kandidat durch den ganzen Datenweg.

Fix-Runde 1 (Pruefer-Befund, Koordinator-Briefing 2026-08-20): die
urspruengliche Schritt-4-Zusicherung (`AUTO_ID not in ids`) war wertlos. Ein
Mutationstest (Origin-Pruefung `c.origin != ORIGIN_MARKER` in
candidate_view.marker_candidates_by_peak_id entfernt -- genau der Fehler, den
Task 3 beheben sollte) blieb gruen, weil in dieser Fixture BEIDE beteiligten
Werte aus voneinander unabhaengigen, vom Origin-Filter selbst UNABHAENGIGEN
Gruenden nie in active_smart_candidates() gelandet waeren:
  (a) AUTO_ID hat peak_id=None -> faellt aus jeder peak_id-basierten
      Zuordnung, ob mit oder ohne Herkunfts-Pruefung.
  (b) die beiden echten Marker-Kandidaten haben score=None (Bootstrap-
      Default, kein Smart-Lauf) -> werden von active_smart_candidates
      ohnehin separat herausgefiltert.
"x not in set()" war also immer wahr, unabhaengig vom Origin-Filter.

Zwei Schaerfungen, beide noetig, damit die Zusicherung wirklich am
Origin-Filter haengt (Gegenprobe unten dokumentiert):
1. Echte Scores auf die beiden Marker -> positive Mengen-Gleichheit statt
   Abwesenheits-Check (faengt fehlenden/kaputten Filter UND eine nur
   zufaellig leere Menge).
2. Ein ZWEITER Fremdkandidat mit KOLLIDIERENDER peak_id (0, wie in
   tests/test_candidate_collisions.py). Erst diese echte Kollision macht die
   Origin-Pruefung ueberhaupt beobachtbar: ohne sie gibt es in der Fixture
   keinen peak_id-Konflikt, an dem ein entfernter Origin-Filter je einen
   Unterschied machen koennte.

Gate B / A1+A3 (2026-08-21) -- was sich an Punkt 2 geaendert hat: der
Eindringling ist seit A3 nicht mehr regulaer baubar (origin != marker ⇒
peak_id is None) und wird seit A1 an der Archivgrenze abgelehnt (Schema 6 =
strikt). Der Test baut ihn deshalb absichtlich ungueltig (tests/
malformed_candidates.py) und prueft den Persistenz-Rundlauf jetzt SCHAERFER
statt schwaecher: eine Akte MIT ihm muss beim Laden kontrolliert scheitern
(Schritt 5a), der echte quellenunabhaengige auto-Kandidat muss den Rundlauf
durch Schema 6 + Neu-Analyse weiterhin exakt ueberleben (5b/6).
"""
import json
from dataclasses import replace

import pytest

from core.candidate_view import marker_candidate_for_peak
from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ORIGIN_AUTO, ORIGIN_MARKER, SELECTED,
    transition)
from core.project_archive import (
    ProjectArchiveError, load_project_archive, save_project_archive)
from core.xml_sequence_helpers import active_smart_candidates
from tests.malformed_candidates import malformed_candidate
from tests.test_candidate_baseline_lock import make_session_with_peaks

AUTO_ID = "auto:integration"
INTRUDER_ID = "auto:kollision-datenweg"
COLLIDING_PEAK_ID = 0


def test_auto_kandidat_kompletter_datenweg(tmp_path):
    # 1. erzeugen -- zwei Fremdkandidaten: AUTO_ID ohne peak_id (echt
    # quellenunabhaengig), INTRUDER_ID MIT peak_id=0 -- kollidiert absichtlich
    # mit dem echten Marker-Kandidaten fuer Peak 0 (marker:0).
    session = make_session_with_peaks([60_000, 180_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id=AUTO_ID, origin=ORIGIN_AUTO, anchor_ms=120_000,
        peak_id=None, boundary=ClipBoundary(110_000, 130_000),
        reason="starker Einstieg", score=0.77))
    # Gate B / A3 (2026-08-21): INTRUDER_ID verletzt die neue Wurzel-Invariante
    # (origin != marker ⇒ peak_id is None) und ist deshalb absichtlich am
    # Konstruktor vorbei gebaut -- zweite Verteidigungslinie, s.
    # tests/malformed_candidates.py. Genau so kann er nur noch von aussen
    # kommen (beschaedigte/handeditierte Akte), nicht mehr aus PeakCut selbst.
    session.clip_candidates.append(malformed_candidate(
        candidate_id=INTRUDER_ID, origin=ORIGIN_AUTO, anchor_ms=61_000,
        peak_id=COLLIDING_PEAK_ID, boundary=ClipBoundary(55_000, 65_000),
        score=0.99, reason="Eindringling"))
    session._reconcile_marker_candidates()

    # Echte Scores auf die beiden Marker -- sonst waere Schritt 4 unten
    # wertlos (Bootstrap-Default score=None wird von active_smart_candidates
    # unabhaengig vom Origin-Filter herausgefiltert; siehe Modul-Docstring).
    session.clip_candidates = [
        replace(c, score=0.5, reason="ok") if c.origin == ORIGIN_MARKER else c
        for c in session.clip_candidates]

    # 2. sortiert nach anchor_ms
    assert [c.anchor_ms for c in session.clip_candidates] == \
        [60_000, 61_000, 120_000, 180_000]

    # 3. Statusuebergang ueber candidate_id
    i = next(i for i, c in enumerate(session.clip_candidates)
             if c.candidate_id == AUTO_ID)
    new, dec = transition(session.clip_candidates[i], SELECTED,
                          now="2026-08-19T12:00:00")
    session.clip_candidates[i] = new
    session.candidate_decisions.append(dec)
    assert dec.candidate_id == AUTO_ID

    # 4. Origin-Filter: NUR die beiden echten Marker in der Smart-XML.
    # Positive Mengen-Gleichheit statt Abwesenheits-Check (Fix-Runde 1) --
    # faengt sowohl einen fehlenden/kaputten Origin-Filter als auch eine nur
    # zufaellig leere Menge ab. INTRUDER_ID hat dieselbe peak_id wie
    # marker:0 UND einen Score -- ohne den Origin-Filter waere sie hier ein
    # ernstzunehmender Konkurrent, nicht nur ein folgenloser Fremdling.
    ids = {c.candidate_id for _, c in active_smart_candidates(session)}
    assert ids == {"marker:0", "marker:1"}
    assert marker_candidate_for_peak(session, COLLIDING_PEAK_ID).candidate_id \
        == "marker:0"

    # 5. v6 speichern/laden exakt
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))
    payload = json.loads((root / ".peakcut" / "project.json").read_text())
    assert payload["schema_version"] == 6

    # 5a. Gate B / A1+A3: die Archivgrenze ist der Ort, an dem so ein
    # Eindringling gestoppt wird. Schema 6 heisst strikt -- ein Kandidat mit
    # origin=auto UND gesetzter peak_id ist keine gueltige v6-Akte mehr und
    # wird kontrolliert abgelehnt, statt als Kollision in die Session zu
    # gelangen. (Vorher lud genau diese Akte klaglos durch; die
    # Kollisionssicherheit hing danach allein an den Verbrauchern.)
    with pytest.raises(ProjectArchiveError):
        load_project_archive(str(root), {})

    # 5b. Ab hier der normale Datenweg OHNE den (nur noch von aussen
    # denkbaren) Eindringling: der echte quellenunabhaengige auto-Kandidat
    # muss den Rundlauf durch Schema 6 exakt ueberleben.
    session.clip_candidates = [c for c in session.clip_candidates
                               if c.candidate_id != INTRUDER_ID]
    save_project_archive(session, str(root))

    loaded = load_project_archive(str(root), {})
    back = next(c for c in loaded.clip_candidates if c.candidate_id == AUTO_ID)
    assert back.origin == ORIGIN_AUTO
    assert back.anchor_ms == 120_000
    assert back.status == SELECTED
    assert back.score == 0.77
    assert [d.candidate_id for d in loaded.candidate_decisions] == [AUTO_ID]

    # Kollisions-Sicherheit nach dem Rundlauf durch Schema 6: der Eindringling
    # ist gar nicht erst in der geladenen Session (5a hat gezeigt, dass eine
    # Akte MIT ihm abgelehnt wird), und die zentrale Sicht liefert weiterhin
    # den echten Marker fuer Peak 0.
    assert INTRUDER_ID not in {c.candidate_id for c in loaded.clip_candidates}
    assert marker_candidate_for_peak(loaded, COLLIDING_PEAK_ID).candidate_id \
        == "marker:0"

    # 6. Neu-Analyse ueberlebt er -- GRENZE: geprueft ist der UNVERAENDERTE
    # Markersatz (dieselben zwei Peaks). marker_candidate_id ist ueber
    # Analyselaeufe mit veraendertem Markersatz laut clip_candidates.py
    # ausdruecklich NICHT stabil -- das ist kein Test voller
    # Reanalyse-Robustheit, nur des Reconciliation-Pfads bei gleichbleibenden
    # Peaks.
    loaded.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
                   "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False},
                  {"index": 1, "position_ms": 180_000, "in_point_ms": 165_000,
                   "out_point_ms": 195_000, "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    assert AUTO_ID in {c.candidate_id for c in loaded.clip_candidates}
    assert marker_candidate_for_peak(loaded, COLLIDING_PEAK_ID).candidate_id \
        == "marker:0"
    assert len(loaded.candidate_decisions) == 1
