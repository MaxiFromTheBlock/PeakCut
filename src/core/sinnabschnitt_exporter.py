"""Roadmap #3 Task 7 — Sinnabschnitte-Zusatz-Export.

Strikt getrennter Zusatz: eigene Dateien `Sinnabschnitte - {Gast}.{txt,
xml}`, EIGENER Codepfad (importiert core/exporters.py NICHT), nutzt
ClipCandidate.boundary statt Peak.in/out. Gehört NICHT in
_build_exporters/exported und läuft erst NACH dem Export-Handoff
(Task 8). Berührt den Keyboardstellen-Pfad nie.

v1-Scope (bewusst, Gate-E-Flag): die XML ist eine leichtgewichtige
xmeml-Spannenliste (Audio-Referenz), KEIN voller Multicam-Relink —
das bleibt der unangetastete Keyboardstellen-Exporter.
"""

import os
from xml.sax.saxutils import escape

from utils import ms_to_timecode, ms_to_frames
# Geteilter URL-Helfer (Carl Gate-E P2): import ist ok — "eigener
# Codepfad" = nicht in _build_exporters / Keyboardstellen-Exporter
# unangetastet, NICHT "keine gemeinsame Util".
from .exporters import _file_url
from .clip_candidates import DISCARDED
from .audio_routing import get_mix_track, get_source_mic_tracks


def _active(session):
    # Nur ECHTE Smart-Ergebnisse exportieren: status != discarded UND
    # score is not None. Bootstrap-Kandidaten (kein Transkript/kein
    # Smart-Lauf) haben score=None -> KEINE leere Nebenprodukt-Datei
    # (Schritt-1-Realbefund / Carl-Checkliste). Konsistent zur
    # Gate-G-Vorschau-Semantik; Fallback score=0.0 bleibt sichtbar.
    return [c for c in getattr(session, "clip_candidates", []) or []
            if c.status != DISCARDED and c.score is not None]


def _paths(session, ext):
    guest = session.project.guest_name
    return os.path.join(session.project.export_dir,
                        f"Sinnabschnitte - {guest}.{ext}")


def _select_audio_reference(session) -> str:
    """Audio-Referenz für die Sinnabschnitt-Spannenliste.

    Nutzt dieselbe Mix-vs-echte-Mics-Wahrheit wie die übrigen
    Hörpfade: Mix zuerst, sonst erste echte Mic-Spur, sonst stabiler
    Default für die leichtgewichtige v1-XML.
    """
    mix = get_mix_track(session.project)
    if mix:
        return mix
    source_mics = get_source_mic_tracks(session.project)
    if source_mics:
        return source_mics[0]
    return "audio.wav"


class SinnabschnittTXTExporter:
    """Lesbare Cutter-Fassung: pro Sinnabschnitt Peak-ID, Start/Ende,
    Dauer, Confidence, Grund, Transkript-Auszug."""

    def export(self, session) -> str:
        active = _active(session)
        if not active:
            return ""
        fps = session.config.get("fps", 25)
        os.makedirs(session.project.export_dir, exist_ok=True)
        path = _paths(session, "txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 48 + "\n")
            f.write("SINNABSCHNITTE (Roadmap #3 — provisorisch)\n")
            f.write("=" * 48 + "\n\n")
            for c in active:
                b = c.boundary
                dur_s = (b.end_ms - b.start_ms) // 1000
                f.write(f"[PEAK {c.peak_id}]\n")
                f.write(f"start      = {ms_to_timecode(b.start_ms, fps)}\n")
                f.write(f"end        = {ms_to_timecode(b.end_ms, fps)}\n")
                f.write(f"dauer      = {dur_s} s\n")
                f.write(f"confidence = "
                        f"{'-' if c.score is None else c.score}\n")
                f.write(f"grund      = {c.reason}\n")
                f.write(f"auszug     = {c.transcript_excerpt}\n\n")
        return path


class SinnabschnittXMLExporter:
    """Leichtgewichtige FCP7-xmeml-Spannenliste auf Basis der smarten
    Grenzen (Audio-Referenz). Eigener Codepfad."""

    def export(self, session) -> str:
        active = _active(session)
        if not active:
            return ""
        fps = session.config.get("fps", 25)
        os.makedirs(session.project.export_dir, exist_ok=True)
        path = _paths(session, "xml")
        ref = _select_audio_reference(session)
        ref_name = escape(os.path.basename(ref))
        ref_url = _file_url(ref)
        rate = (f"<rate><timebase>{fps}</timebase>"
                f"<ntsc>FALSE</ntsc></rate>")

        clips = []
        cursor = 0
        for i, c in enumerate(active):
            in_f = ms_to_frames(c.boundary.start_ms, fps)
            out_f = ms_to_frames(c.boundary.end_ms, fps)
            length = max(1, out_f - in_f)
            start, end = cursor, cursor + length
            cursor = end
            clips.append(
                f'        <clipitem id="sinn-{c.peak_id}">\n'
                f'          <name>Sinnabschnitt {c.peak_id}</name>\n'
                f'          <start>{start}</start>\n'
                f'          <end>{end}</end>\n'
                f'          <in>{in_f}</in>\n'
                f'          <out>{out_f}</out>\n'
                f'          <file id="sinn-audio">\n'
                f'            <name>{ref_name}</name>\n'
                f'            <pathurl>{ref_url}</pathurl>\n'
                f'            {rate}\n'
                f'          </file>\n'
                f'        </clipitem>\n')

        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE xmeml>\n')
            f.write('<xmeml version="5">\n')
            f.write('  <sequence id="peakcut-sinnabschnitte">\n')
            f.write('    <name>PeakCut Sinnabschnitte</name>\n')
            f.write(f'    <duration>{cursor}</duration>\n')
            f.write(f'    {rate}\n')
            f.write('    <media>\n      <audio>\n        <track>\n')
            for cl in clips:
                f.write(cl)
            f.write('        </track>\n      </audio>\n    </media>\n')
            f.write('  </sequence>\n')
            f.write('</xmeml>\n')
        return path
