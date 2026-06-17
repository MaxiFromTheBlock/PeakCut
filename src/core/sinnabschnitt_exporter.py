"""Roadmap #3 Task 7 — Sinnabschnitte-Zusatz-Export.

Strikt getrennter Zusatz: eigene Dateien `Sinnabschnitte - {Gast}.{txt,
xml}`, EIGENER Codepfad (importiert core/exporters.py NICHT), nutzt
ClipCandidate.boundary statt Peak.in/out. Gehört NICHT in
_build_exporters/exported und läuft erst NACH dem Export-Handoff
(Task 8). Berührt den Keyboardstellen-Pfad nie.

Marker-Slice 2026-06-17: die XML ist jetzt eine kompakte Multicam-Liste
(Video + Ton) mit nummerierten Markern ("Stelle N"), strukturgleich zur
Keyboardstellen-XML, damit Max beide in Premiere direkt vergleichen kann.
Die Stellennummern kommen aus der gemeinsamen Keyboard-Nummernkarte
(xml_sequence_helpers), NICHT aus candidate.peak_id. Sequenz heißt
"Keyboardstellen smart". Der Keyboardstellen-Exporter bleibt ein eigener,
unabhängiger Codepfad.
"""

import os
from xml.sax.saxutils import escape

from utils import ms_to_timecode, ms_to_frames, parse_timecode_to_ms
# Geteilte Helfer (Carl Gate-E P2): import ist ok — "eigener Codepfad" =
# nicht in _build_exporters / Keyboardstellen-Exporter unangetastet, NICHT
# "keine gemeinsame Util".
from .exporters import _file_url, _probe_audio_info, _probe_video_info
from .audio_routing import get_mix_track, get_source_mic_tracks
from .xml_sequence_helpers import (
    build_smart_spans, sequence_markers_xml, active_smart_candidates)

# Filter/Sortierung/Nummerierung der exportierbaren Smart-Kandidaten leben
# zentral in xml_sequence_helpers.active_smart_candidates (status != discarded,
# score is not None, nur mit aktivem Peak — Bootstrap & verworfene raus).


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
    """Lesbare Cutter-Fassung: pro Sinnabschnitt Stellennummer, Start/Ende,
    Dauer, Confidence, Grund, Transkript-Auszug. Nummerierung = Keyboard-
    Stelle (wie XML), nicht candidate.peak_id."""

    def export(self, session) -> str:
        active = active_smart_candidates(session)
        if not active:
            return ""
        fps = session.config.get("fps", 25)
        os.makedirs(session.project.export_dir, exist_ok=True)
        path = _paths(session, "txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("=" * 48 + "\n")
            f.write("SINNABSCHNITTE (Roadmap #3 — provisorisch)\n")
            f.write("=" * 48 + "\n\n")
            for number, c in active:
                b = c.boundary
                dur_s = (b.end_ms - b.start_ms) // 1000
                f.write(f"[PEAK {number}]\n")
                f.write(f"start      = {ms_to_timecode(b.start_ms, fps)}\n")
                f.write(f"end        = {ms_to_timecode(b.end_ms, fps)}\n")
                f.write(f"dauer      = {dur_s} s\n")
                f.write(f"confidence = "
                        f"{'-' if c.score is None else c.score}\n")
                f.write(f"grund      = {c.reason}\n")
                f.write(f"auszug     = {c.transcript_excerpt}\n\n")
        return path


class SinnabschnittXMLExporter:
    """Kompakte FCP7-xmeml Multicam-Liste (Video + Ton) der smarten
    Sinnabschnitte mit nummerierten Markern ("Stelle N"). Strukturgleich
    zur Keyboardstellen-XML, damit beide in Premiere vergleichbar sind.
    Eigener Codepfad. Nummern aus der gemeinsamen Keyboard-Nummernkarte."""

    def export(self, session) -> str:
        # (Stellennummer, candidate) — gefiltert (kein discarded/score=None/
        # ohne aktiven Peak) und nach Stelle sortiert. Gleiche Quelle wie die
        # Marker, damit Nummern & Reihenfolge mit Keyboardstellen matchen.
        smart = active_smart_candidates(session)
        if not smart:
            return ""
        fps = session.config.get("fps", 25)
        os.makedirs(session.project.export_dir, exist_ok=True)
        path = _paths(session, "xml")

        video_paths = list(session.project.videos)
        offset_lookup = {}
        for vfn, off in getattr(session, "video_offsets", []) or []:
            offset_lookup[vfn] = parse_timecode_to_ms(off, fps)

        vid_w, vid_h = 3840, 2160
        if video_paths:
            vid_w, vid_h = _probe_video_info(video_paths[0])

        ref = _select_audio_reference(session)          # Mix bevorzugt
        ref_base = os.path.basename(ref)
        sample_rate, bit_depth, channels = _probe_audio_info(ref)

        rate = (f"<rate><timebase>{fps}</timebase>"
                f"<ntsc>FALSE</ntsc></rate>")
        tc = (f"<timecode>{rate}<string>00:00:00:00</string>"
              f"<frame>0</frame><displayformat>NDF</displayformat></timecode>")

        spans = build_smart_spans(session)
        total_frames = spans[-1].rec_end_f if spans else 0
        markers = sequence_markers_xml(spans)

        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE xmeml>\n')
            f.write('<xmeml version="5">\n')
            f.write('  <sequence id="keyboardstellen-smart">\n')
            f.write('    <name>Keyboardstellen smart</name>\n')
            f.write(f'    <duration>{total_frames}</duration>\n')
            f.write(f'    {rate}\n')
            f.write(f'    {tc}\n')
            f.write('    <format>\n')
            f.write('      <samplecharacteristics>\n')
            f.write(f'        <width>{vid_w}</width>\n')
            f.write(f'        <height>{vid_h}</height>\n')
            f.write('        <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'        {rate}\n')
            f.write('      </samplecharacteristics>\n')
            f.write('    </format>\n')
            # Nummerierte Sequenz-Marker — gleiche Nummern wie Keyboardstellen.
            f.write(markers)
            f.write('    <media>\n')

            # === VIDEO: eine Spur je Kamera, Clip je Sinnabschnitt ===
            f.write('      <video>\n')
            f.write('        <format>\n')
            f.write('          <samplecharacteristics>\n')
            f.write(f'            <width>{vid_w}</width>\n')
            f.write(f'            <height>{vid_h}</height>\n')
            f.write('            <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'            {rate}\n')
            f.write('          </samplecharacteristics>\n')
            f.write('        </format>\n')
            for track_idx, video_path in enumerate(video_paths):
                file_id = f"sinn-video-{track_idx + 1}"
                video_file = os.path.basename(video_path)
                clip_name = escape(os.path.splitext(video_file)[0])
                offset_ms = offset_lookup.get(video_file, 0)
                f.write('        <track>\n')
                rec = 0
                for clip_idx, (number, c) in enumerate(smart):
                    src_in = max(0, c.boundary.start_ms + offset_ms)
                    src_out = max(0, c.boundary.end_ms + offset_ms)
                    in_f = ms_to_frames(src_in, fps)
                    out_f = ms_to_frames(src_out, fps)
                    dur = max(1, out_f - in_f)
                    start, end = rec, rec + dur
                    rec = end
                    f.write(f'          <clipitem id="sinn-v{track_idx + 1}'
                            f'-{number}">\n')
                    f.write(f'            <name>{clip_name}</name>\n')
                    f.write(f'            <duration>{dur}</duration>\n')
                    f.write(f'            {rate}\n')
                    f.write(f'            <start>{start}</start>\n')
                    f.write(f'            <end>{end}</end>\n')
                    f.write(f'            <in>{in_f}</in>\n')
                    f.write(f'            <out>{out_f}</out>\n')
                    if clip_idx == 0:
                        f.write(f'            <file id="{file_id}">\n')
                        f.write(f'              <name>{escape(video_file)}'
                                f'</name>\n')
                        f.write(f'              <pathurl>{_file_url(video_path)}'
                                f'</pathurl>\n')
                        f.write(f'              {rate}\n')
                        f.write(f'              {tc}\n')
                        f.write('              <media>\n')
                        f.write('                <video>\n')
                        f.write('                  <samplecharacteristics>\n')
                        f.write(f'                    <width>{vid_w}</width>\n')
                        f.write(f'                    <height>{vid_h}</height>\n')
                        f.write('                    <pixelaspectratio>Square'
                                '</pixelaspectratio>\n')
                        f.write(f'                    {rate}\n')
                        f.write('                  </samplecharacteristics>\n')
                        f.write('                </video>\n')
                        f.write('              </media>\n')
                        f.write('            </file>\n')
                    else:
                        f.write(f'            <file id="{file_id}"/>\n')
                    f.write('          </clipitem>\n')
                f.write('        </track>\n')
            f.write('      </video>\n')

            # === AUDIO: eine Spur (Mix bevorzugt, kein Phasing) ===
            f.write('      <audio>\n')
            f.write('        <format>\n')
            f.write('          <samplecharacteristics>\n')
            f.write(f'            <samplerate>{sample_rate}</samplerate>\n')
            f.write(f'            <depth>{bit_depth}</depth>\n')
            f.write('          </samplecharacteristics>\n')
            f.write('        </format>\n')
            f.write('        <track>\n')
            rec = 0
            for clip_idx, (number, c) in enumerate(smart):
                in_f = ms_to_frames(c.boundary.start_ms, fps)
                out_f = ms_to_frames(c.boundary.end_ms, fps)
                dur = max(1, out_f - in_f)
                start, end = rec, rec + dur
                rec = end
                f.write(f'          <clipitem id="sinn-a1-{number}">\n')
                f.write(f'            <name>{escape(os.path.splitext(ref_base)[0])}'
                        f'</name>\n')
                f.write(f'            <duration>{dur}</duration>\n')
                f.write(f'            {rate}\n')
                f.write(f'            <start>{start}</start>\n')
                f.write(f'            <end>{end}</end>\n')
                f.write(f'            <in>{in_f}</in>\n')
                f.write(f'            <out>{out_f}</out>\n')
                if clip_idx == 0:
                    f.write('            <file id="sinn-audio">\n')
                    f.write(f'              <name>{escape(ref_base)}</name>\n')
                    f.write(f'              <pathurl>{_file_url(ref)}'
                            f'</pathurl>\n')
                    f.write(f'              {rate}\n')
                    f.write(f'              {tc}\n')
                    f.write('              <media>\n')
                    f.write('                <audio>\n')
                    f.write('                  <samplecharacteristics>\n')
                    f.write(f'                    <samplerate>{sample_rate}'
                            f'</samplerate>\n')
                    f.write(f'                    <depth>{bit_depth}</depth>\n')
                    f.write('                  </samplecharacteristics>\n')
                    f.write(f'                  <channelcount>{channels}'
                            f'</channelcount>\n')
                    f.write('                </audio>\n')
                    f.write('              </media>\n')
                    f.write('            </file>\n')
                else:
                    f.write('            <file id="sinn-audio"/>\n')
                f.write('            <sourcetrack>\n')
                f.write('              <mediatype>audio</mediatype>\n')
                f.write('            </sourcetrack>\n')
                f.write('          </clipitem>\n')
            f.write('        </track>\n')
            f.write('      </audio>\n')

            f.write('    </media>\n')
            f.write('  </sequence>\n')
            f.write('</xmeml>\n')
        return path
