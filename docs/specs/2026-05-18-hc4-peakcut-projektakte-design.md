# HC-4 — `.peakcut/`-Projektakte: Persistenz (Spec)

**Status: Spec/Design — noch NICHT in Umsetzung. Bau-Basis ist Carls
Umsetzungsplan, nicht diese Spec.**

**Herkunft:** Health-Check Carl+Claude + 2-Pass-Strategie-Konvergenz
(2026-05-18, von Max abgenommen). Dies ist der **Schlussstein** der
festgeschriebenen Roadmap (CLAUDE.md „Produkt-Strategie & Roadmap",
Punkt 1) — und zugleich der erste konkrete Pilot-Baustein der
Hybrid/NAS-Topologie (Phase 1: „NAS-Projektordner wird Wahrheit").

## Problem (Warum)

PeakCut hat **kein Gedächtnis**. Jeder Lauf beginnt bei null: importieren
→ analysieren (Sync + Peak-Erkennung, schwer, Minuten) → zuordnen →
reviewen → exportieren. Schließt man die App, ist alles weg; eine Folge
erneut anfassen heißt erneut voll analysieren. Verifiziert im Code:
`grep` nach Projekt-Laden/-Speichern → existiert nicht; einziger
persistenter Output sind die Export-Artefakte + `.peakcut_done`.

Die festgeschriebene Strategie sagt: PeakCut soll **das Gedächtnis einer
Produktion** sein (wer hat was markiert, was wurde daraus). Ohne
persistente Projektakte ist *kein* weiterer Roadmap-Schritt tragfähig
(ClipCandidate/Rückweg, Profile, Feedback-Loop, Hybrid/NAS) — sie alle
brauchen einen Ort, an dem Zustand lebt.

## Ziel (Was)

Ein Lauf kann **gespeichert und wieder geladen** werden, statt erneut
analysiert zu werden — portabel (auch vom NAS / anderen Mac aus). Im
Materialordner liegt eine versionierte `.peakcut/`-Akte; ist sie da,
lädt PeakCut den Stand statt neu zu analysieren; ist sie nicht da,
verhält sich PeakCut **exakt wie heute** (frischer Lauf).

## Andockpunkt (verifiziert, de-riskt den Plan)

`session.load_analysis_results(results: dict)` existiert bereits und
ist der natürliche Vertrag: der Analyse-Subprozess liefert einen Dict,
die Session lädt ihn. Die Projektakte persistiert im Kern **genau
diesen Dict** + die Zuordnungen + die Projekt-Identität, mit
**relativen** Pfaden. „Projekt laden" = Analyse überspringen und den
gespeicherten Dict in `load_analysis_results` einspeisen + Zuordnungen
restaurieren. Kein neuer Analysepfad, keine Pipeline-Änderung.

## Umfang / Nicht-Ziele

- **In Scope:** versioniertes `.peakcut/`-Format (Schema-Version);
  Speichern/Laden von: Projekt-Identität (keyboard_track, mic_tracks,
  videos, guest_name — als **relative** Pfade zum Materialordner),
  Analyse-Ergebnis (der `load_analysis_results`-Dict: peaks inkl.
  in/out-Offsets + ignored, video_offsets, speaker_activity-Referenz),
  Zuordnungen (`folgenschnitt_mic_assignments`,
  `folgenschnitt_camera_assignments`, `folgenschnitt_assignment_applied`,
  `speaker_activity_mic_assignments`). Graceful Absence (keine Akte →
  Verhalten wie heute). Großes `speaker_activity` wird per Referenz auf
  die bestehende `speaker_activity.csv` gehalten, NICHT in JSON inlined.
- **Nicht-Ziel (bewusst, Roadmap-Reihenfolge):** `ClipCandidate` /
  Rückweg-Status (= Roadmap #2, eigene Spec), Profile (#4), NAS-
  Wiring/Worker (#5), ein UI-Projekt-Browser/Hub (#6). HC-4 baut das
  *Fundament*, auf das #2–#6 später aufsetzen — das Format muss
  erweiterbar sein, die Erweiterungen werden hier NICHT gebaut.
- **Nicht-Ziel:** keine Änderung an Analyse, Folgenschnitt-Pipeline,
  Exporter, der cutter-validierten Ausgabe oder der Leitplanke.

## Harte Randbedingungen

1. **Additiv & risikolos:** ohne `.peakcut/` verhält sich PeakCut
   bit-genau wie heute. Die Leitplanke (Keyboardstellen-Export läuft
   immer) bleibt unangetastet.
2. **Round-Trip-Exaktheit:** ein gespeicherter + neu geladener Stand
   muss einen **identischen Export** erzeugen wie ohne Speichern —
   insbesondere Peak `position_ms` (immutable), editierte in/out-
   Offsets, `ignored`, `video_offsets`. Reload darf den Schnitt NICHT
   still verändern. (Das ist die HC-4-Entsprechung der „bit-identisch"-
   Bedingung von HC-2/HC-3.)
3. **Portabel:** Pfade relativ zum Materialordner, damit dieselbe
   `.peakcut/`-Akte vom NAS / einem anderen Mac aus funktioniert.
   Fehlende/verschobene Datei → kontrollierter Hinweis, kein Crash.
4. **Versioniert & vorwärtskompatibel:** Schema-Version im Format;
   spätere Felder (ClipCandidate/Profile) müssen sich additiv ergänzen
   lassen, ohne alte Akten zu brechen. Unbekannte Felder ignorieren,
   nicht crashen.
5. Qt-frei bleibt Qt-frei (`core/`).

## Akzeptanzkriterien

- Lauf speichern → App schließen → Projekt aus `.peakcut/` laden →
  Export ist identisch zum Export ohne Speicher-Zyklus (Golden-Test:
  Keyboardstellen-XML + Folgenschnitt-XML byte-/frame-identisch).
- Kein `.peakcut/` → Verhalten unverändert (Regressionswächter grün).
- Verschobener Materialordner (relative Pfade) → Projekt lädt weiterhin;
  fehlende Datei → klare Meldung, kein Crash.
- Alte Akte mit niedrigerer Schema-Version + zukünftiges Zusatzfeld →
  lädt ohne Fehler (Vorwärts-/Rückwärts-Toleranz getestet).
- Volle Suite grün; Folgenschnitt-/XML-/Keyboardstellen-Tests
  unverändert grün.

## Bekannte Schwierigkeiten (Carl im Plan adressieren)

- **Peak-Round-Trip-Exaktheit:** `Peak` hat immutable `position_ms`,
  geclampte in/out-Properties und lazy gesetzte Dauer-Grenzen
  (`_duration_ms`). Serialisierung muss exakt rekonstruieren, dass ein
  reloadeter Peak denselben in/out-Punkt liefert wie der Original-Peak.
  Teststrategie dafür explizit benennen, nicht umgehen.
- **Relative-Pfad-Auflösung:** Materialordner-Wurzel bestimmen,
  Symlinks/NAS-Mounts, fehlende Dateien — Strategie benennen.
- **Schema-Versionierung:** wie additive Felder (#2 ClipCandidate, #4
  Profile) später ohne Bruch andocken — Vertrag jetzt festlegen, Felder
  nicht bauen.
- **`speaker_activity`-Größe** (HR-CSV war 12,7 MB): per Referenz auf
  die `.csv`, nicht inlinen — Konsistenz/Fehlen der CSV behandeln.

## 4-Augen-Prozess

Spec (Claude) → **Max-Read-Gate** (Max delegiert i. d. R. an Claude:
Selbst-Gate-Review + Flag) → Carl schreibt den Umsetzungsplan
(Bau-Basis) → Claude verifiziert Carls Plan gegen den echten Code +
baut TDD → Gates wie von Carl gesetzt → Max entscheidet Merge. Kein Bau
vor Carls Plan.
