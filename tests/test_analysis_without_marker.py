"""Analyse OHNE Marker-Spur (Max-Entscheid 2026-08-17, Carl-Gate 2026-08-19).

PeakCut ist capability-driven (core/project_capabilities.py): der Marker schaltet
NUR die Keyboardstellen frei. Fremdproduktionen haben kein Fusspedal — dort muessen
Video-Sync und Sprecher-Aktivitaet (= die Grundlage des Folgenschnitts) trotzdem
entstehen.

Bis 1de8d05 brach `run_analysis` in Step 3 hart ab und WARF DAMIT DIE BEREITS
BERECHNETEN Ergebnisse aus Step 1 und Step 2 WEG.

Vertrag (Carl-Gate A):
- Die WAHRHEIT ueber Faehigkeiten ist project_capabilities, NICHT ein Flag hier.
- `skipped_steps` ist ein fluechtiger Laufhinweis (Schritt -> Grund), bewusst
  allgemein statt ein Flag je Fall, und wird NICHT in die Akte persistiert.
- Fehlender Marker laesst NUR Step 3 aus; er beendet die Pipeline nicht.

Abgrenzung — bewusst NICHT hier: Screenshots und Sinnabschnitte ohne Marker.
Die Sinnabschnitt-Pipeline stuerzt bei null Peaks nicht ab (clip_boundary/
pipeline.py:98 steigt vorher sauber aus), sie erzeugt aber auch nichts.
Transkriptweites Finden ist eigene Produktlogik -> eigener Slice.
"""
import ast
import io
import os

import numpy as np
import soundfile as sf

import core.sync
from core.analysis_process import run_analysis

SENTINEL_OFFSET = [("cam01.mp4", "-00:00:07:12")]


def _write_wav(path, samples, sample_rate=16_000):
    sf.write(str(path), samples.astype(np.float32), sample_rate)


def _config(tmp_path, keyboard_track, *, with_video=False):
    """Zwei Mics mit klar getrennter Aktivitaet (erste/zweite Haelfte)."""
    sr, duration_s = 16_000, 1
    mic1 = np.random.RandomState(1).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic2 = np.random.RandomState(2).normal(0, 0.002, sr * duration_s).astype(np.float32)
    mic1[: sr // 2] += 0.2
    mic2[sr // 2:] += 0.2

    mic1_path, mic2_path = tmp_path / "MIC1.wav", tmp_path / "MIC2.wav"
    _write_wav(mic1_path, mic1, sr)
    _write_wav(mic2_path, mic2, sr)

    export_dir, temp_dir = tmp_path / "export", tmp_path / "temp"
    export_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)

    cfg = {
        "mic_tracks": [str(mic1_path), str(mic2_path)],
        "videos": [],
        "reference_track": None,
        "temp_dir": str(temp_dir),
        "export_dir": str(export_dir),
        "config": {"threshold_factor": 1.0, "min_gap_ms": 12_000,
                   "context_duration_ms": 15_000, "fps": 25},
    }
    if keyboard_track is not None:
        cfg["marker_track"] = keyboard_track
    if with_video:
        # Step 1 laeuft nur bei videos UND reference_track. Die Datei muss nicht
        # echt sein — sync_videos wird gemockt; hier zaehlt der Datenweg.
        cfg["videos"] = [str(tmp_path / "cam01.mp4")]
        cfg["reference_track"] = str(mic1_path)
    return cfg, export_dir


def test_analyse_ohne_marker_liefert_sprecher_aktivitaet_statt_abbruch(tmp_path):
    """Kein Marker -> kein Fehler, keine Peaks, aber Sprecher-Aktivitaet ist da."""
    config, export_dir = _config(tmp_path, keyboard_track=None)

    results = run_analysis(config)

    assert results["error"] is None, f"Analyse brach ab: {results['error']}"
    assert results["peaks"] == []
    assert results["speaker_activity"], "Sprecher-Aktivitaet fehlt — Step 2 wurde verworfen"
    assert results["speaker_activity_csv"] == str(export_dir / "speaker_activity.csv")
    assert results["speaker_activity_mic_assignments"][0]["speaker_key"] == "mic_1"
    assert results["speaker_activity_mic_assignments"][1]["speaker_key"] == "mic_2"


def test_ohne_marker_ueberlebt_der_video_sync(tmp_path, monkeypatch):
    """Carl-Gate: Step 1 muss im markerlosen Ergebnis WIRKLICH ankommen.

    Der Vorgaenger-Test bewies nur Step 2 (er lief mit videos=[]). Hier wird
    sync_videos auf einen Sentinel gemockt und im Ergebnis nachgewiesen.
    """
    calls = []

    def fake_sync_videos(**kwargs):
        calls.append(kwargs)
        return SENTINEL_OFFSET

    monkeypatch.setattr(core.sync, "sync_videos", fake_sync_videos)

    config, _ = _config(tmp_path, keyboard_track=None, with_video=True)
    results = run_analysis(config)

    assert calls, "sync_videos wurde ohne Marker gar nicht erst aufgerufen"
    assert results["video_offsets"] == SENTINEL_OFFSET
    assert results["error"] is None
    assert results["peaks"] == []


def test_ohne_marker_meldet_den_uebersprungenen_schritt(tmp_path):
    """Ehrliches Signal statt Stille — allgemein, nicht als Einzel-Flag."""
    config, _ = _config(tmp_path, keyboard_track=None)

    results = run_analysis(config)

    assert results["skipped_steps"]["peak_detection"] == "marker_missing"
    assert results["error"] is None


def test_leerer_marker_pfad_zaehlt_wie_kein_marker(tmp_path):
    """Der Web-Pfad reicht '' statt None durch — darf nicht anders behandelt werden."""
    config, _ = _config(tmp_path, keyboard_track="")

    results = run_analysis(config)

    assert results["error"] is None
    assert results["skipped_steps"]["peak_detection"] == "marker_missing"
    assert results["peaks"] == []


def test_nicht_existierender_marker_pfad_ist_ein_ECHTER_fehler(tmp_path):
    """Abgrenzung: 'kein Marker bestaetigt' ist etwas anderes als 'bestaetigte Datei weg'.

    Ein gesetzter, aber verschwundener Pfad ist ein Materialfehler und muss laut
    bleiben — sonst laeuft eine HM-Folge still ohne Keyboardstellen durch.
    """
    config, _ = _config(tmp_path, keyboard_track=str(tmp_path / "weg.wav"))

    results = run_analysis(config)

    assert results["error"] is not None
    assert "peak_detection" not in results["skipped_steps"]


def test_mit_marker_bleibt_alles_wie_bisher(tmp_path):
    """Regressionsnetz: der HM-Normalfall darf sich nicht veraendern."""
    sr = 16_000
    keyboard_path = tmp_path / "keyboard.wav"
    _write_wav(keyboard_path, np.zeros(sr, dtype=np.float32), sr)
    config, export_dir = _config(tmp_path, keyboard_track=str(keyboard_path))

    results = run_analysis(config)

    assert results["error"] is None
    assert results["skipped_steps"] == {}
    assert results["speaker_activity_csv"] == str(export_dir / "speaker_activity.csv")


def test_fehlender_marker_beendet_die_pipeline_nicht():
    """Carl-Gate, struktureller Riegel gegen eine Regression, die man sonst nicht sieht.

    Ein fehlender Marker darf NUR Step 3 auslassen. Heute folgt danach kein
    Step 4 — ein frueher `return` faellt also verhaltensmaessig nicht auf und
    wuerde einen kuenftigen markerunabhaengigen Schritt still mitverschlucken.
    Deshalb wird hier am Syntaxbaum geprueft, dass run_analysis GENAU EIN
    return hat: den gemeinsamen am Schluss.
    """
    src_path = os.path.join(os.path.dirname(core.sync.__file__), "analysis_process.py")
    tree = ast.parse(io.open(src_path, encoding="utf-8").read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run_analysis")
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]

    assert len(returns) == 1, (
        f"run_analysis hat {len(returns)} return-Anweisungen. Erwartet: genau 1 "
        "(der gemeinsame am Schluss). Ein frueher Ausstieg ueberspringt kuenftige Schritte."
    )
