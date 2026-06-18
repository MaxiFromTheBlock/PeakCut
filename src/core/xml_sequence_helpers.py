"""Gemeinsame Bausteine für die kompakten Clip-an-Clip-XMLs
(Keyboardstellen raw + Keyboardstellen smart).

EINE Wahrheit für (a) die Stellennummer (peak.index -> Stelle 1..N über
die aktiven, nicht-ignorierten Peaks — exakt die Keyboardstellen-
Nummerierung) und (b) die kumulativen Record-Positionen in der kompakten
Premiere-Timeline. So tragen Keyboardstellen- und Sinnabschnitt-XML
dieselben Marker-Nummern, obwohl die eine über Peaks und die andere über
Smart-Kandidaten läuft (deren candidate.peak_id == peak.index, aber NICHT
== Stellennummer, sobald früh ein Peak ignoriert wurde).

Bewusst KLEINE Helfer (Carl-Plan Punkt d): die stabilen XML-Writer bleiben
getrennt, geteilt sind nur Nummern, Spannen und Marker.
"""

from collections import namedtuple
from xml.sax.saxutils import escape

from utils import ms_to_frames
from .clip_candidates import DISCARDED

# Eine Spanne in der kompakten exportierten Timeline.
#   number       = Stellennummer (= Keyboardstellen-Nummer, 1..N)
#   source_in_f  / source_out_f = Quell-In/Out in Frames (ohne Video-Offset)
#   rec_start_f  / rec_end_f    = Position in der kompakten Sequenz (Frames)
SequenceSpan = namedtuple(
    "SequenceSpan",
    ["number", "source_in_f", "source_out_f", "rec_start_f", "rec_end_f"])


def _fps(session) -> int:
    return session.config.get("fps", 25)


def build_peak_number_map(session) -> dict:
    """peak.index -> Stellennummer (1..N über die aktiven Peaks).

    get_active_peaks zählt nur nicht-ignorierte Peaks hoch -> identisch zur
    Keyboardstellen-Nummerierung.
    """
    return {peak.index: num for num, peak in session.get_active_peaks()}


def build_keyboard_spans(session) -> list:
    """Keyboardstellen-Spannen: aktive Peaks, Quelle = peak.in/out, Record
    kumulativ (kompakte Clip-an-Clip-Timeline)."""
    fps = _fps(session)
    spans = []
    rec = 0
    for num, peak in session.get_active_peaks():
        in_f = ms_to_frames(peak.in_point_ms, fps)
        out_f = ms_to_frames(peak.out_point_ms, fps)
        length = max(1, out_f - in_f)
        spans.append(SequenceSpan(num, in_f, out_f, rec, rec + length))
        rec += length
    return spans


def active_smart_candidates(session) -> list:
    """(Stellennummer, candidate) für die exportierbaren Smart-Kandidaten,
    sortiert nach Stellennummer.

    EINE Quelle für Filter + Sortierung + Nummer (Keyboardstellen-XML und
    Sinnabschnitt-XML hängen sich beide hier an). Raus fallen: verworfene,
    Bootstrap (score=None) und Kandidaten ohne aktiven Peak (ignoriert /
    kein Mapping — sonst keine Vergleichbarkeit). Die Nummer kommt aus der
    Keyboard-Nummernkarte, NICHT direkt aus candidate.peak_id.
    """
    number_map = build_peak_number_map(session)
    active = [c for c in (getattr(session, "clip_candidates", []) or [])
              if c.status != DISCARDED and c.score is not None
              and c.peak_id in number_map]
    active.sort(key=lambda c: number_map[c.peak_id])
    return [(number_map[c.peak_id], c) for c in active]


def build_smart_spans(session) -> list:
    """Sinnabschnitt-Spannen (smart): aktive Smart-Kandidaten, Quelle =
    candidate.boundary, Record kumulativ. Nummer + Filter via
    active_smart_candidates."""
    fps = _fps(session)
    spans = []
    rec = 0
    for number, c in active_smart_candidates(session):
        in_f = ms_to_frames(c.boundary.start_ms, fps)
        out_f = ms_to_frames(c.boundary.end_ms, fps)
        length = max(1, out_f - in_f)
        spans.append(SequenceSpan(number, in_f, out_f, rec, rec + length))
        rec += length
    return spans


def marker_xml(number: int, in_frame: int, out_frame: int,
               indent: str = "    ") -> str:
    """Ein Sequenz-Marker 'Stelle N' als BEREICH (in..out) — so lang wie die
    Stelle, damit Premiere das Label lesbar anzeigt (Max-Wunsch)."""
    name = escape(f"Stelle {number}")
    return (f"{indent}<marker>\n"
            f"{indent}  <name>{name}</name>\n"
            f"{indent}  <comment></comment>\n"
            f"{indent}  <in>{in_frame}</in>\n"
            f"{indent}  <out>{out_frame}</out>\n"
            f"{indent}</marker>\n")


def sequence_markers_xml(spans, indent: str = "    ") -> str:
    """Alle Sequenz-Marker einer Spannenliste, jeweils über die ganze Stelle
    (rec_start..rec_end)."""
    return "".join(
        marker_xml(s.number, s.rec_start_f, s.rec_end_f, indent)
        for s in spans)
