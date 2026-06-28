# Marker-Auto-Erkennung verbessern (capability-driven Import)

> Status: **Vorschlag / zur Abstimmung mit Carl** (Audio-Heuristik = Carls Gebiet).
> Auslöser: Live-Test Ilka Bessin (28.06.) — die Fußpedal-Spur (MIC4) wurde NICHT
> automatisch als Marker vorgeschlagen; Max musste sie im Bestätigen-Screen von Hand
> auf „Marker" stellen. Max-O-Ton: „mic4 wurde nicht als marker spur erkannt — wie auch?".

## Problem

Im capability-driven Import schlägt `core/material_scanner` Rollen vor. Der Marker
(Fußpedal) wird über ein **dünnes Inhalts-Signal** erkannt: viel Stille + laute Impulse.
Das Signal kommt aus `audio_silence_peak(path)`:

```python
# core/material_scanner.py
frames = min(len(f), f.samplerate * 120)   # NUR die ersten <=120 s
data = f.read(frames, dtype="float32")
a = np.abs(data)
return float((a < 0.01).mean()), float(a.max())   # (Stille-Anteil, MAX-Impuls)
```

`_suggest`: `silence >= 0.85 AND peak >= 0.2` → Marker.

**Wurzel:** Bei einer 2,5-h-Folge sind die Fußtritte oft **spärlich** und nicht in den
ersten 120 s. Dann ist im Probefenster zwar die Stille hoch, aber **kein** lauter Impuls
(`peak < 0.2`) → MIC4 fällt auf `mic` (oder bei `peak < 0.05` auf `ignore`). Der Marker
wird verfehlt.

**Wirkung:** Funktional aufgefangen (der Bestätigen-Screen ist genau dafür da, und seit
28.06. warnt er, wenn kein Marker gewählt ist). Aber eine bessere Auto-Erkennung spart
den Hand-Griff — gerade bei HMs immer gleicher Studio-Struktur (eine Marker-Spur pro Folge).

## Was NICHT betroffen ist (Riegel)

- Reiner **Import-Scanner** (Vorschlag), KEIN Export-/Routing-Pfad. **Pin-1 + #71a
  (`get_speech_audio_segment`, `test_audio_routing_safety`) unberührt** — der XML/MP3-Export
  hängt an den bestätigten Rollen, nicht an diesem Signal.
- Der Name bleibt nur **Evidence**; die Wahrheit setzt weiter der Confirm-Schritt. Eine
  bessere Heuristik macht NUR den Vorschlag treffsicherer.

## Optionen

**(a) Verstreute Stichprobe (Empfehlung).** Statt eines 120-s-Blocks am Anfang N kurze
Fenster über die **ganze** Datei (z. B. 8×15 s, gleichmäßig verteilt; `soundfile.seek`).
- `silence` = Mittel über die Fenster; `peak` = **MAX** über alle Fenster.
- Fängt einen spärlichen, lauten Impuls **egal wo** in der Folge.
- Kosten: ~gleiche Datenmenge wie heute (≈120 s gelesen), nur mehr Seeks. Kein Voll-Read.

**(b) Voll-Scan (genauer, schwerer).** Peak/Stille über die ganze Datei (`soundfile`-Blöcke
oder ein `ffmpeg volumedetect`-Pass). Treffsicherster, aber I/O auf 2,5-h-Dateien × vielen
Kanälen — gehört dann eher in den (ohnehin schweren) Analyse-/Job-Pfad, nicht in den
interaktiven Scan beim Öffnen.

**(c) Status quo.** Marker dünn lassen, Confirm + Warnung fangen es. Kein Code.

## Vorschlag

**(a)** für den interaktiven Scan: verstreute Stichprobe, bounded cost, fängt genau den
Ilka-Fall. `audio_silence_peak` bekommt eine Fenster-Strategie; `_suggest`-Schwellen
(`MARKER_SILENCE_THRESHOLD` 0.85 / `MARKER_PEAK_THRESHOLD` 0.2) bleiben erstmal.

Optionaler v2-Feinschliff (mit Carl, falls nötig): Marker = wenige **scharfe** Transienten
(Impuls-Dichte/Anstiegszeit), um ein lautes-aber-kontinuierliches Signal sauberer vom
Fußpedal zu trennen. Erst, wenn (a) in der Praxis Fehlgriffe zeigt.

## Gate / Test

- Audio-Heuristik = **Carls Gebiet → 4-Augen**, kein Solo-Bau.
- TDD am Scanner: injizierbares `audio_signal`/`probe_duration` schon vorhanden
  (`scan_material(paths, audio_signal=…)`) → Fenster-Strategie unit-testbar ohne echtes Audio.
- **Real-Smoke** an Ilka `1_Material`: MIC4 wird jetzt als Marker **vorgeschlagen**
  (Confidence-Badge ok), die übrigen Rollen unverändert.
- Voller Desktop-Lauf + `test_audio_routing_safety` (Pin-1) grün — darf sich nicht bewegen.

## Verwandt

- Bestätigen-Screen + capability-driven Import: `PeakCut-web/design/handoff/2026-06-25-import-confirm/`,
  `PeakCut-web/engine/import_scan.py`, `core/material_scanner.py`.
- Marker-Namens-Fragilität (anderes Thema, schon gelöst für den **Mix**: B1 `_MIX_DEVICE_RE`).
