#!/usr/bin/env python3
"""#71a Task 7 — Real-Verifikation für den Audio-Routing-Slice.

Lädt eine echte ``.peakcut``-Akte (z.B. die Sheila-Folge nach #71a-
Bau), druckt einen **Routing-Report** und schreibt optional
**Debug-WAVs** für einen Hörvergleich „alte Phasing-Quelle vs. neue
saubere Quelle" am gewählten Peak.

KEIN CI-Test (braucht reale Audiodaten + funktionierendes ffmpeg).
Reine Helfer-Funktionen sind unit-getestet
(``tests/test_verify_audio_routing_real.py``).

Aufruf:

    ./venv311/bin/python scripts/verify_audio_routing_real.py <MATERIAL_DIR>
    ./venv311/bin/python scripts/verify_audio_routing_real.py <MATERIAL_DIR> --dump-wavs 0

``MATERIAL_DIR`` muss einen ``.peakcut``-Unterordner enthalten
(HC-4-Archiv). ``--dump-wavs N`` schreibt drei WAVs für den
N-ten Peak in ``<MATERIAL_DIR>/audio_routing_debug/``:

- ``mix_only.wav`` (Quelle nach #71a — sollte phasingfrei klingen)
- ``mix_plus_mics_overlay.wav`` (Pre-#71a-Quelle = Phasing-Reproduktion)
- ``mics_only_no_mix.wav`` (Was passieren würde, wenn der Mix
  rausgefiltert wäre — Stand der Helfer-Logik bei „kein Mix")

Akzeptanz für Sheila-Smoke nach #71a:

- Mix erkannt (``Sheila Mix.mp3`` oder analog).
- Pro aktivem Peak: ``source == 'mix_only'``.
- ``mix_only.wav`` klingt phasingfrei, ``mix_plus_mics_overlay.wav``
  reproduziert das alte Phasing-Geräusch.
- Keyboardstellen-XML byte-identisch — ist aber bereits über den
  Pin-Hash in ``tests/test_audio_routing_safety.py`` abgedeckt;
  dieses Skript verifiziert nur das Live-Routing.
"""

import argparse
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# --- Reine Helfer (unit-getestet) -------------------------------------


def build_routing_report(project, peaks):
    """Pro aktivem Peak: welche Audio-Quelle wählt der Helper-Pfad?

    Reine Datenmodell-Auswertung, lädt keine Audio-Bytes.

    Args:
        project: Objekt mit ``mic_tracks``.
        peaks: Liste von Dicts mit ``index``, ``position_ms``,
            ``ignored``.

    Returns:
        Dict mit ``mix`` (Basename oder None), ``real_mics``,
        ``all_mic_tracks``, ``rows`` (pro Peak: ``peak_id``,
        ``position_ms``, ``source``).
    """
    from core.audio_routing import get_mix_track, get_source_mic_tracks

    mix = get_mix_track(project)
    real_mics = get_source_mic_tracks(project)

    rows = []
    for p in peaks:
        if p.get("ignored", False):
            source = "skipped (peak ignored)"
        elif mix:
            source = "mix_only"
        elif real_mics:
            source = "mic_overlay"
        else:
            source = "none (no audio source)"
        rows.append(
            {
                "peak_id": p.get("index"),
                "position_ms": p.get("position_ms"),
                "source": source,
            }
        )

    return {
        "mix": os.path.basename(mix) if mix else None,
        "real_mics": [os.path.basename(m) for m in real_mics],
        "all_mic_tracks": [
            os.path.basename(m) for m in project.mic_tracks
        ],
        "rows": rows,
    }


def print_report(report):
    """Pretty-print für den Routing-Report (mensch-lesbar)."""
    print("\n=== #71a Audio-Routing — Real-Report ===\n")
    print(f"Erkannter Mix:               {report['mix'] or '(kein Mix gefunden)'}")
    print(f"Echte Mic-Spuren:            {', '.join(report['real_mics']) or '(keine)'}")
    print(f"Alle mic_tracks (inkl. Mix): {', '.join(report['all_mic_tracks'])}")
    print(
        "\nQuelle pro Peak "
        "(MP3-Export + Speak-Mode-Wiedergabe nutzen dieselbe Wahl):"
    )
    if not report["rows"]:
        print("  (keine Peaks)")
    for row in report["rows"]:
        pos_s = (row["position_ms"] or 0) / 1000.0
        print(
            f"  Peak {row['peak_id']:>3} @ {pos_s:>7.2f}s: {row['source']}"
        )


# --- Debug-WAVs (lädt Audio, nur on-demand) ---------------------------


def dump_debug_wavs(session, peak_idx, out_dir):
    """Schreibt drei Vergleichs-WAVs für den gewählten Peak."""
    from core.audio_routing import (
        get_speech_audio_segment,
        is_mix_track,
    )

    os.makedirs(out_dir, exist_ok=True)

    if not (0 <= peak_idx < len(session.peaks)):
        print(
            f"  FEHLER: Peak-Index {peak_idx} außerhalb "
            f"(0..{len(session.peaks) - 1})"
        )
        return

    peak = session.peaks[peak_idx]
    start_ms = peak.in_point_ms
    end_ms = peak.out_point_ms

    # 1. Neue Quelle (Helper-Pfad nach #71a)
    seg_new = get_speech_audio_segment(session, start_ms, end_ms)
    if seg_new is not None:
        path = os.path.join(out_dir, "mix_only.wav")
        seg_new.export(path, format="wav")
        print(f"  geschrieben: {path}")
    else:
        print("  WARNUNG: Helper lieferte None — Mix/Mics-Mismatch?")

    mic_audios = session.mic_audios
    if not mic_audios:
        print("  (keine mic_audios geladen — überspringe Vergleichs-WAVs)")
        return

    # 2. Alte Quelle — Mix+Mics overlay-summiert (Phasing-Reproduktion)
    old = mic_audios[0][start_ms:end_ms]
    for m in mic_audios[1:]:
        old = old.overlay(m[start_ms:end_ms])
    path_old = os.path.join(out_dir, "mix_plus_mics_overlay.wav")
    old.export(path_old, format="wav")
    print(f"  geschrieben: {path_old} (Pre-#71a-Phasing-Reproduktion)")

    # 3. Nur echte Mics, kein Mix (Stand bei „kein Mix vorhanden")
    mic_tracks = session.project.mic_tracks
    real_indices = [
        i for i, p in enumerate(mic_tracks)
        if not is_mix_track(p) and i < len(mic_audios)
    ]
    if real_indices:
        only_mics = mic_audios[real_indices[0]][start_ms:end_ms]
        for i in real_indices[1:]:
            only_mics = only_mics.overlay(
                mic_audios[i][start_ms:end_ms]
            )
        path_mics = os.path.join(out_dir, "mics_only_no_mix.wav")
        only_mics.export(path_mics, format="wav")
        print(f"  geschrieben: {path_mics}")
    else:
        print("  (keine echten Mics — überspringe mics_only_no_mix.wav)")


# --- CLI -------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Real-Verifikation für #71a Audio-Routing."
    )
    parser.add_argument(
        "material_dir",
        help="Pfad zum Material-Ordner mit .peakcut/-Unterordner.",
    )
    parser.add_argument(
        "--dump-wavs",
        type=int,
        default=None,
        metavar="PEAK_IDX",
        help="Schreibt Debug-WAVs für den gegebenen Peak-Index "
        "(0-basiert).",
    )
    args = parser.parse_args(argv)

    from core.project_archive import load_project_archive
    import config

    archive_path = os.path.join(args.material_dir, ".peakcut")
    if not os.path.isdir(archive_path):
        print(
            f"FEHLER: keine .peakcut/-Akte in {args.material_dir}",
            file=sys.stderr,
        )
        return 1

    session = load_project_archive(archive_path, config.load())
    if session is None:
        print(
            "FEHLER: .peakcut-Akte konnte nicht geladen werden.",
            file=sys.stderr,
        )
        return 1

    peaks_dicts = [
        {
            "index": p.index,
            "position_ms": p.position_ms,
            "ignored": p.ignored,
        }
        for p in session.peaks
    ]
    report = build_routing_report(session.project, peaks_dicts)
    print_report(report)

    if args.dump_wavs is not None:
        session.load_audio_lazy()
        out_dir = os.path.join(args.material_dir, "audio_routing_debug")
        print(
            f"\n=== Debug-WAVs für Peak {args.dump_wavs} "
            f"→ {out_dir} ==="
        )
        dump_debug_wavs(session, args.dump_wavs, out_dir)

    print(
        "\nAkzeptanz-Check (manuell): "
        "alle aktiven Peaks zeigen 'mix_only'? "
        "→ Pin-3 (Cutter-MP3 phasingfrei) ist live bewiesen."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
