"""Analyse OHNE Marker-Spur (Max-Entscheid 2026-08-17).

PeakCut ist capability-driven (core/project_capabilities.py): der Marker schaltet
NUR die Keyboardstellen frei. Fremdproduktionen haben kein Fusspedal — dort muessen
Sync und Sprecher-Aktivitaet (= die Grundlage des Folgenschnitts) trotzdem entstehen.

Bis heute brach `run_analysis` in Step 3 hart ab (`results["error"] = "No keyboard
file"`, frueher Return) und WARF DAMIT DIE BEREITS BERECHNETEN Ergebnisse aus Step 1
(Video-Sync) und Step 2 (Sprecher-Aktivitaet) WEG. Genau das ist hier verriegelt.

Abgrenzung — bewusst NICHT hier getestet: Screenshots und Sinnabschnitte haengen an
der Peak-Navigation bzw. iterieren ueber Peaks (`core/clip_boundary/pipeline.py:103`
`max(p.position_ms for p in peaks)` wirft bei leerer Liste). Der Vertrag verspricht
beide ohne Marker — das ist ein offener Entwurf, kein Schalter. Siehe BACKLOG.
"""
import numpy as np
import soundfile as sf

from core.analysis_process import run_analysis


def _write_wav(path, samples, sample_rate=16_000):
    sf.write(str(path), samples.astype(np.float32), sample_rate)


def _two_mics(tmp_path, sr=16_000, duration_s=1):
    """Zwei Mics mit klar getrennter Aktivitaet (erste/zweite Haelfte)."""
    mic1 = np.random.RandomState(1).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic2 = np.random.RandomState(2).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic1[: sr // 2] += 0.2
    mic2[sr // 2:] += 0.2

    mic1_path = tmp_path / "MIC1.wav"
    mic2_path = tmp_path / "MIC2.wav"
    _write_wav(mic1_path, mic1, sr)
    _write_wav(mic2_path, mic2, sr)
    return mic1_path, mic2_path


def _config(tmp_path, keyboard_track):
    export_dir = tmp_path / "export"
    temp_dir = tmp_path / "temp"
    export_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)
    mic1_path, mic2_path = _two_mics(tmp_path)
    cfg = {
        "mic_tracks": [str(mic1_path), str(mic2_path)],
        "videos": [],
        "reference_track": None,
        "temp_dir": str(temp_dir),
        "export_dir": str(export_dir),
        "config": {
            "threshold_factor": 1.0,
            "min_gap_ms": 12_000,
            "context_duration_ms": 15_000,
            "fps": 25,
        },
    }
    if keyboard_track is not None:
        cfg["keyboard_track"] = keyboard_track
    return cfg, export_dir


def test_analyse_ohne_marker_liefert_sprecher_aktivitaet_statt_abbruch(tmp_path):
    """Kein Marker -> kein Fehler, keine Peaks, aber Sprecher-Aktivitaet ist da."""
    config, export_dir = _config(tmp_path, keyboard_track=None)

    results = run_analysis(config)

    # Kein harter Abbruch mehr
    assert results["error"] is None, f"Analyse brach ab: {results['error']}"

    # Keine Peaks, aber sauber leer (nicht None) — load_analysis_results iteriert darueber
    assert results["peaks"] == []

    # Und der eigentliche Punkt: die Arbeit aus Step 1+2 ueberlebt
    assert results["speaker_activity"], "Sprecher-Aktivitaet fehlt — Step 2 wurde verworfen"
    assert results["speaker_activity_csv"] == str(export_dir / "speaker_activity.csv")
    assert results["speaker_activity_mic_assignments"][0]["speaker_key"] == "mic_1"
    assert results["speaker_activity_mic_assignments"][1]["speaker_key"] == "mic_2"


def test_analyse_ohne_marker_meldet_die_fehlende_faehigkeit_explizit(tmp_path):
    """Ehrliches Signal statt Stille: die UI muss 'keine Keyboardstellen' anzeigen koennen."""
    config, _ = _config(tmp_path, keyboard_track=None)

    results = run_analysis(config)

    assert results["marker_missing"] is True
    assert results["error"] is None


def test_leerer_marker_pfad_zaehlt_wie_kein_marker(tmp_path):
    """Der Web-Pfad reicht '' statt None durch — darf nicht anders behandelt werden."""
    config, _ = _config(tmp_path, keyboard_track="")

    results = run_analysis(config)

    assert results["error"] is None
    assert results["marker_missing"] is True
    assert results["peaks"] == []


def test_nicht_existierender_marker_pfad_ist_ein_ECHTER_fehler(tmp_path):
    """Abgrenzung: 'kein Marker bestaetigt' ist etwas anderes als 'bestaetigte Datei weg'.

    Ein gesetzter, aber verschwundener Pfad ist ein Materialfehler und muss laut
    bleiben — sonst laeuft eine HM-Folge still ohne Keyboardstellen durch.
    """
    config, _ = _config(tmp_path, keyboard_track=str(tmp_path / "weg.wav"))

    results = run_analysis(config)

    assert results["error"] is not None
    assert results["marker_missing"] is False


def test_mit_marker_bleibt_alles_wie_bisher(tmp_path):
    """Regressionsnetz: der HM-Normalfall darf sich nicht veraendern."""
    sr = 16_000
    keyboard_path = tmp_path / "keyboard.wav"
    _write_wav(keyboard_path, np.zeros(sr, dtype=np.float32), sr)
    config, export_dir = _config(tmp_path, keyboard_track=str(keyboard_path))

    results = run_analysis(config)

    assert results["error"] is None
    assert results["marker_missing"] is False
    assert results["speaker_activity_csv"] == str(export_dir / "speaker_activity.csv")
