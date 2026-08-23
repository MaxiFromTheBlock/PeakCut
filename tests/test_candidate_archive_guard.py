"""Gate B / Block A — die Archivgrenze als Waechter (Carl 2026-08-21).

Zwei Befunde, beide von Carl selbst reproduziert:

A1  Die v6-Strenge hing am falschen Kriterium. `project_archive.py` entschied
    pro Kandidat ueber `if "candidate_id" in d`, ob v6 oder Legacy vorliegt.
    Eine Schema-6-Akte OHNE candidate_id, aber MIT altem peak_id, wurde
    dadurch still migriert und lud als `marker:0` — eine beschaedigte v6-Akte
    tarnte sich als Legacy. Die Entscheidung muss an der SCHEMA-VERSION
    haengen: schema_v >= 6 -> immer strikt, schema_v <= 5 -> Legacy-Migration
    mit Peak-Join. Dasselbe fuer Decisions (eine v6-Decision darf nicht ueber
    peak_id durchrutschen).

A2  Die Kandidaten-Identitaet war an der Archivgrenze ungeschuetzt. Doppelte
    candidate_id wurden weder abgelehnt noch wurde sortiert; eine Akte mit
    zweimal `auto:dup` lud mit beiden Eintraegen und machte damit jede
    CandidateDecision auf diese ID mehrdeutig — genau der Rueckkanal, fuer den
    der ganze Umbau gemacht wurde. Geprueft wird in BEIDE Richtungen: beim
    Laden UND vor dem Schreiben.

NICHT geprueft (bewusst offen, eigene Historien-Entscheidung): ob eine
Decision auf einen aktuell vorhandenen Kandidaten zeigen muss.
"""
import json

import pytest

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ORIGIN_AUTO, PROPOSED, SELECTED)
# validate_candidate_collection wird BEWUSST erst im Test importiert (nicht
# hier oben): sonst scheitert schon das Einsammeln des Moduls, wenn man diese
# Datei gegen einen aelteren Stand laufen laesst — die Gegenprobe soll aber
# Test fuer Test zeigen, was dort durchrutscht.
from core.project_archive import (
    ProjectArchiveError, load_project_archive, save_project_archive)
from tests.test_candidate_baseline_lock import make_session_with_peaks
from tests.malformed_candidates import malformed_candidate

_V6_DECISION = {"candidate_id": "marker:0", "from_status": PROPOSED,
                "to_status": SELECTED, "decided_at": "2026-08-21T10:00:00",
                "source": "manual"}


def _akte(tmp_path, *, candidates=None, decisions=None, schema_version=None):
    """Echte Akte einer Ein-Peak-Session schreiben, danach die Sektionen
    gezielt verbiegen (so wie eine beschaedigte Akte auf Platte aussaehe)."""
    session = make_session_with_peaks([60_000])
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))
    akte = root / ".peakcut" / "project.json"
    payload = json.loads(akte.read_text())
    if schema_version is not None:
        payload["schema_version"] = schema_version
    if candidates is not None:
        payload["clip_candidates"] = candidates
    if decisions is not None:
        payload["candidate_decisions"] = decisions
        payload.pop("peak_decisions", None)
    akte.write_text(json.dumps(payload))
    return root


# --- A1: die Strenge haengt an der Schema-Version -------------------------

def test_a1_v6_kandidat_ohne_candidate_id_aber_mit_peak_id_wird_abgelehnt(tmp_path):
    """Carls reproduzierter Fall. peak_id=0 EXISTIERT im Peak-Satz — unter dem
    alten Kriterium lief der Kandidat deshalb sauber durch die Legacy-
    Migration und landete als `marker:0` in der Session. In einer Schema-6-
    Akte ist das kein Legacy-Kandidat, sondern ein beschaedigter v6-Kandidat
    und muss kontrolliert scheitern."""
    root = _akte(tmp_path, candidates=[{
        "peak_id": 0, "boundary": {"start_ms": 45_000, "end_ms": 75_000},
        "status": "proposed", "transcript_excerpt": "", "reason": "",
        "score": None}])

    with pytest.raises(ProjectArchiveError):
        load_project_archive(str(root), {})


def test_a1_v6_decision_ohne_candidate_id_wird_abgelehnt(tmp_path):
    """Dasselbe fuer den Rueckkanal: eine Schema-6-Decision, die nur noch ein
    altes peak_id traegt, darf NICHT still als `marker:<peak_id>` gelesen
    werden. Sonst erfindet das Laden eine Zuordnung, die in der Akte nicht
    steht."""
    root = _akte(tmp_path, decisions=[{
        "peak_id": 0, "from_status": PROPOSED, "to_status": SELECTED,
        "decided_at": "2026-08-21T10:00:00", "source": "manual"}])

    with pytest.raises(ProjectArchiveError):
        load_project_archive(str(root), {})


def test_a1_v6_decision_mit_leerer_candidate_id_wird_abgelehnt(tmp_path):
    """Gate B Restpunkt P1: eine FEHLENDE candidate_id wird oben schon
    abgelehnt (test_a1_v6_decision_ohne_candidate_id_wird_abgelehnt) -- eine
    LEERE candidate_id ("") ist derselbe Integritaetsbruch (die Decision
    haengt an gar keiner Kennung) und darf nicht als gueltig durchrutschen,
    nur weil das Feld formal vorhanden ist."""
    root = _akte(tmp_path, decisions=[{
        "candidate_id": "", "from_status": PROPOSED, "to_status": SELECTED,
        "decided_at": "2026-08-21T10:00:00", "source": "manual"}])

    with pytest.raises(ProjectArchiveError):
        load_project_archive(str(root), {})


def test_a1_v5_akte_migriert_weiterhin(tmp_path):
    """Gegenprobe, damit A1 nicht einfach alles ablehnt: dieselben Daten in
    einer Schema-5-Akte sind echtes Legacy und muessen weiterhin ueber den
    Peak-Join migriert werden (Anker = peak.position_ms)."""
    root = _akte(tmp_path, schema_version=5, candidates=[{
        "peak_id": 0, "boundary": {"start_ms": 45_000, "end_ms": 75_000},
        "status": "proposed", "transcript_excerpt": "", "reason": "",
        "score": None}], decisions=None)
    akte = root / ".peakcut" / "project.json"
    payload = json.loads(akte.read_text())
    payload["peak_decisions"] = [{
        "peak_id": 0, "from_status": PROPOSED, "to_status": SELECTED,
        "decided_at": "2026-06-01T10:00:00", "source": "manual"}]
    payload.pop("candidate_decisions", None)
    akte.write_text(json.dumps(payload))

    loaded = load_project_archive(str(root), {})
    assert [c.candidate_id for c in loaded.clip_candidates] == ["marker:0"]
    assert loaded.clip_candidates[0].anchor_ms == 60_000
    assert [d.candidate_id for d in loaded.candidate_decisions] == ["marker:0"]


def test_a1_gesunde_v6_akte_laedt_unveraendert(tmp_path):
    """Zweite Gegenprobe: die normale v6-Akte (von PeakCut selbst
    geschrieben) laedt weiterhin vollstaendig."""
    root = _akte(tmp_path, decisions=[_V6_DECISION])
    loaded = load_project_archive(str(root), {})
    assert [c.candidate_id for c in loaded.clip_candidates] == ["marker:0"]
    assert [d.candidate_id for d in loaded.candidate_decisions] == ["marker:0"]


# --- A2: Identitaet der Sammlung, beim Laden UND vor dem Schreiben --------

def _auto(cid, anchor_ms):
    return {"candidate_id": cid, "origin": "auto", "anchor_ms": anchor_ms,
            "peak_id": None,
            "boundary": {"start_ms": anchor_ms - 5_000,
                         "end_ms": anchor_ms + 5_000},
            "status": "proposed", "transcript_excerpt": "", "reason": "",
            "score": None}


def test_a2_doppelte_candidate_id_beim_laden_abgelehnt(tmp_path):
    """Carls reproduzierter Fall: zweimal `auto:dup` lud bisher mit BEIDEN
    Eintraegen. Eine CandidateDecision(candidate_id='auto:dup') waere damit
    mehrdeutig."""
    root = _akte(tmp_path, candidates=[_auto("auto:dup", 90_000),
                                       _auto("auto:dup", 120_000)])

    with pytest.raises(ProjectArchiveError) as exc:
        load_project_archive(str(root), {})
    assert "auto:dup" in str(exc.value)


def test_a2_kandidaten_werden_nach_anker_und_id_sortiert(tmp_path):
    """Nach dem Hydrieren gilt dieselbe Ordnung, die die Reconciliation
    herstellt: (anchor_ms, candidate_id). Sonst haengt die Reihenfolge daran,
    wie die Akte zufaellig auf Platte lag."""
    root = _akte(tmp_path, candidates=[
        _auto("auto:spaet", 120_000),
        _auto("auto:b", 90_000),
        _auto("auto:a", 90_000),
        {"candidate_id": "marker:0", "origin": "marker", "anchor_ms": 60_000,
         "peak_id": 0, "boundary": {"start_ms": 45_000, "end_ms": 75_000},
         "status": "proposed", "transcript_excerpt": "", "reason": "",
         "score": None},
    ])

    loaded = load_project_archive(str(root), {})
    assert [c.candidate_id for c in loaded.clip_candidates] == [
        "marker:0", "auto:a", "auto:b", "auto:spaet"]
    assert [c.anchor_ms for c in loaded.clip_candidates] == [
        60_000, 90_000, 90_000, 120_000]


def test_a2_doppelte_candidate_id_wird_gar_nicht_erst_geschrieben(tmp_path):
    """Dieselbe Pruefung VOR dem Schreiben: PeakCut selbst darf keine Akte
    erzeugen, die es hinterher nicht mehr eindeutig lesen kann. Ohne diesen
    Riegel entsteht die kaputte Akte hier klaglos und faellt erst beim
    naechsten Oeffnen auf — dann ist der Rueckkanal schon mehrdeutig."""
    session = make_session_with_peaks([60_000])
    doppelt = ClipCandidate(
        candidate_id="auto:dup", origin=ORIGIN_AUTO, anchor_ms=90_000,
        peak_id=None, boundary=ClipBoundary(80_000, 100_000))
    session.clip_candidates.append(doppelt)
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:dup", origin=ORIGIN_AUTO, anchor_ms=120_000,
        peak_id=None, boundary=ClipBoundary(110_000, 130_000)))

    root = tmp_path / "folge"
    root.mkdir()
    with pytest.raises(ProjectArchiveError) as exc:
        save_project_archive(session, str(root))
    assert "auto:dup" in str(exc.value)
    assert not (root / ".peakcut" / "project.json").is_file(), \
        "kaputte Akte wurde trotzdem geschrieben"


def test_a2_zentrale_pruefung_ist_eine_funktion():
    """Die Sammlungs-Pruefung ist EINE Funktion (nicht verstreute Pruefungen)
    und direkt aufrufbar — Lade- und Schreibweg benutzen dieselbe."""
    from core.project_archive import validate_candidate_collection

    ok = [ClipCandidate(candidate_id="auto:a", origin=ORIGIN_AUTO,
                        anchor_ms=1_000, peak_id=None,
                        boundary=ClipBoundary(0, 2_000))]
    validate_candidate_collection(ok)          # wirft nicht
    with pytest.raises(ProjectArchiveError):
        validate_candidate_collection(ok + list(ok))


def test_a2_dublette_aus_einer_fremden_quelle_wird_auch_gefangen(tmp_path):
    """Die Sammlungs-Pruefung haengt an der Identitaet, nicht an der
    Herkunft: auch ein (absichtlich ungueltig gebauter) Fremdkandidat mit
    marker:<n>-ID kollidiert mit dem echten Marker-Kandidaten und darf nicht
    geschrieben werden."""
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(malformed_candidate(
        candidate_id="marker:0", origin=ORIGIN_AUTO, anchor_ms=99_000,
        peak_id=None, boundary=ClipBoundary(90_000, 110_000)))

    root = tmp_path / "folge"
    root.mkdir()
    with pytest.raises(ProjectArchiveError):
        save_project_archive(session, str(root))
