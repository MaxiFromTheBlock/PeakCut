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

## Vorschlag — HYBRID (v1, mit Carl abgestimmt 28.06.)

Nicht nur reine verstreute Stichprobe, sondern zweistufig:
1. **Verstreute Fenster über die ganze Datei** (z. B. 8×15 s) → `silence_ratio` = Mittel,
   `peak` = **max** über die Fenster.
2. **Bounded Voll-Peak-Pass NUR für „verdächtige" Kandidaten:** ist ein langer Kandidat
   **sehr still** (`silence >= MARKER_SILENCE_THRESHOLD`), zeigt aber **noch keinen Impuls**
   (`peak < MARKER_PEAK_THRESHOLD`), dann blockweise über die ganze Datei NUR das Maximum
   suchen — fängt **spärliche Fußpedal-Klicks**. Greift nur für diese wenigen stillen
   Episoden-Kandidaten; **die 188 SFX werden nie teuer gescannt** (kurz → nicht
   Episoden-Länge → `audio_silence_peak` wird für sie gar nicht erst gerufen).

`_suggest`-Schwellen (`MARKER_SILENCE_THRESHOLD` 0.85 / `MARKER_PEAK_THRESHOLD` 0.2 /
`EMPTY_PEAK_THRESHOLD` 0.05) bleiben. Name bleibt Evidence, Confirm bleibt Wahrheit.

Optionaler v2 (nur falls v1 in der Praxis Fehlgriffe zeigt): Marker = wenige **scharfe**
Transienten (Impuls-Dichte/Anstiegszeit), um lautes-aber-kontinuierliches Signal sauberer
vom Fußpedal zu trennen.

## Gate / Test (Carl)

- Audio-Heuristik = **Carls Gebiet → 4-Augen**.
- **Klick erst nach 120 s wird erkannt** (der Kernfall — verstreute Fenster + Voll-Pass).
- **Leerer langer Kanal bleibt `ignore`** (still + kein Impuls auch nach Voll-Pass → Peak ~0).
- **Speech/Mix wird nicht Marker** (niedrige Stille → kein Marker, egal welcher Peak).
- **Real-Smoke Ilka `1_Material`:** MIC4 wird als Marker **vorgeschlagen**, **P8Mix bleibt Mix**,
  übrige Rollen unverändert.
- Voller Desktop-Lauf + `test_audio_routing_safety` (Pin-1) grün — darf sich nicht bewegen.

## Verwandt

- Bestätigen-Screen + capability-driven Import: `PeakCut-web/design/handoff/2026-06-25-import-confirm/`,
  `PeakCut-web/engine/import_scan.py`, `core/material_scanner.py`.
- Marker-Namens-Fragilität (anderes Thema, schon gelöst für den **Mix**: B1 `_MIX_DEVICE_RE`).
