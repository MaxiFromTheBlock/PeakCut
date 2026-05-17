# HC-3 — Sync/Audio: Fenster-/Streaming-Lesen statt Voll-Last (Spec)

**Status: Spec/Design — noch NICHT in Umsetzung. Bau-Basis ist Carls
Umsetzungsplan, nicht diese Spec.**

**Herkunft:** Health-Check Carl + Claude (2026-05-17). Carls Fund (von
Claude im ersten Pass übersehen) — daher hohe Relevanz, eigenständig
isoliert.

## Problem (Warum)

`sync.py` lädt für die Video-Audio-Synchronisation mehr Audio
vollständig in den RAM, als der schnelle Pfad braucht:

- `load_audio_as_array(path, max_seconds=None)` (`sync.py:46-57`) macht
  `sf.read(path)` — liest die **ganze Datei** in den Speicher — und
  schneidet *danach* erst auf `max_seconds`. Der `max_seconds`-
  Parameter wird zudem von **keinem** Aufrufer genutzt.
- `sync_videos` lädt die volle Referenz (`sync.py:155`,
  `load_audio_as_array(reference_path)` ohne Grenze).
- `_sync_single_video` lädt das volle extrahierte Video-Audio
  (`sync.py:115`, `load_audio_as_array(temp_audio_path)` ohne Grenze).
- Der schnelle Pfad braucht aber nur die ersten `_SYNC_WINDOW_S = 600`
  Sekunden (`sync.py:119-121`). Nur wenn die Korrelation schwach ist
  (`confidence < _CORRELATION_THRESHOLD`), fällt er auf die volle
  Länge zurück (`sync.py:123-127`).
- Mehrere Videos laufen parallel (`ThreadPoolExecutor`,
  `max_workers=len(video_files)`, `sync.py:166-175`) → bei langen
  Folgen (Hotel Matze ~166 Min) × mehreren Kameras liegen **N volle
  Audio-Arrays gleichzeitig** im RAM, obwohl je nur 10 Min gebraucht
  werden. Carls „heimliche RAM-Wetten".

## Ziel (Was)

Der schnelle Sync-Pfad zieht nur das benötigte 10-Minuten-Fenster von
der Platte in den RAM. Die volle Audiolänge wird **nur dann**
materialisiert, wenn der Confidence-Fallback tatsächlich greift (selten).
Spitzen-Speicher für Sync ist durch Fenstergröße × N begrenzt, nicht
durch Folgenlänge × N. **Die berechneten Offsets bleiben bit-identisch.**

## Umfang / Nicht-Ziele

- **In Scope:** `sync.py` — `load_audio_as_array` echtes Teil-/
  Fenster-Lesen (soundfile kann partielles Lesen: `frames=`/`start=`
  bzw. `sf.SoundFile`/`sf.blocks`), Aufrufer lesen erst nur das
  Fenster, volle Länge nur bei ausgelöstem Fallback. Plus die
  Testabsicherung der Offset-Identität.
- **Nicht-Ziel — bewusst, nicht vergessen:** `session.py:189
  load_audio_lazy` (Playback lädt Keyboard + alle Mics voll via pydub).
  Das ist ein **anderes Problem**: Wiedergabe braucht wahlfreien
  Zugriff über die ganze Timeline (nicht nur ein Anfangsfenster),
  Streaming dort ändert die nutzersichtbare Playback-Architektur und
  ist ein eigenes, größeres, riskanteres Vorhaben. Gehört in eine
  eigene Aufgabe bzw. zum V3-/Timeline-Strang (HC-5), NICHT in diese
  Perf-Härtung gebündelt (gezielte Härtung, kein Umbau).
- **Nicht-Ziel:** keine Änderung an Korrelations-Algorithmus,
  `_CORRELATION_THRESHOLD`, `_SYNC_WINDOW_S`, `fps`, Offset-Format
  oder der öffentlichen `sync_videos`-Signatur.

## Harte Randbedingungen

1. **Sync-Offsets bit-identisch zum jetzigen Stand.** Folgenschnitt
   UND der produktive Keyboardstellen-Export hängen an exakten
   Offsets; bestehende Sync-Regressionssicherung muss grün bleiben.
   Das ist DIE Bedingung (analog zu HC-2 „keine Folgenschnitt-
   Regression").
2. **Fallback-Pfad bleibt verhaltensgleich** — wenn die schwache
   Korrelation auf volle Länge zurückfällt, muss das Ergebnis
   identisch zum heutigen Voll-Lesen sein.
3. **Numerische Identität der Korrelations-Eingabe:** das partiell
   gelesene Fenster muss exakt dasselbe Array ergeben wie heute
   „voll lesen, dann `[:max_samples]` schneiden" — inkl.
   Stereo→Mono-Mittelung, dtype, letztem Teilframe.
4. Qt-frei bleibt Qt-frei (`sync.py` ist `core/`, bleibt es).

## Akzeptanzkriterien

- Auf einem synthetischen Mehrspur-Fixture sind die Offsets vor/nach
  dem Umbau identisch (Golden-Offset-Test), schneller Pfad **und**
  erzwungener Fallback-Pfad.
- Nachweis (Test/Messung), dass im schnellen Pfad nur Fenster-Samples
  materialisiert werden, nicht die volle Datei (z. B. über die
  gelesene Sample-Anzahl / einen Lese-Spy).
- Volle Suite grün; Sync-/XML-/Folgenschnitt-Regressionswächter
  unverändert grün.

## Bekannte Schwierigkeit (Carl im Plan adressieren)

`sf.read(path)` voll + `[:n]` vs. partielles Lesen (`frames=n` /
`sf.SoundFile.read`) können in Randfällen abweichen (Resampling-Rand
durch das vorgeschaltete `extract_audio_from_video -ar ref_sr`,
letzter Teilframe, float64 vs. Mono-Mittelung-Reihenfolge). Der Plan
muss die Teststrategie für die **Offset-Identität** ausdrücklich
benennen (Golden-Offsets auf festem Fixture, schneller + Fallback-
Pfad), statt sie zu umgehen.

## Abgrenzungs-Frage an Carl (ausdrücklich zum Widerspruch)

Claude argumentiert: Sync-Voll-Laden (HC-3) und Playback-Voll-Laden
(`session.py:189`) sind **gleiches Symptom, andere Wurzel** → trennen.
Begründung = Zugriffsmuster: Sync braucht nur ein festes Anfangsfenster
(sequenziell, einmalig, verwerfbar) und liest aus Versehen alles;
Playback braucht wahlfreien Zugriff über die ganze Folge (die Voll-Last
ist dort eine echte Anforderung, kein Versehen) → keine gemeinsame
Lösung heute, kein geteilter Baustein, Zusammenlegen spart keine Arbeit
und verheiratet einen risikolosen Fix mit einem nutzersichtbaren Umbau.
Sinnvoller Vereinigungsort später: die Audio-Schicht des internen
Timeline-Modells / V3 (HC-5).

**Carl: bitte unabhängig prüfen und widersprechen, falls du eine
gemeinsame Wurzel/einen geteilten Baustein siehst, der ein
Zusammenmachen *jetzt* rechtfertigt.** Diese Scope-Grenze wurde von Max
bewusst hinterfragt — sie soll nicht aus Zufall stehen, sondern geprüft.

## 4-Augen-Prozess

Spec (Claude) → **Max liest gegen (Gate)** → Carl schreibt den
Umsetzungsplan (Bau-Basis) → Claude verifiziert Carls Plan gegen den
echten Code + baut TDD → Gates wie von Carl gesetzt → Max entscheidet
Merge. Kein Bau vor Carls Plan.
