# HC-2 — Rückgrat: Worker-/Subprocess-Lifecycle-Härtung (Spec)

**Status: Spec/Design — noch NICHT in Umsetzung. Bau-Basis ist Carls
Umsetzungsplan, nicht diese Spec.**

**Herkunft:** Health-Check Carl + Claude (2026-05-17), unabhängig
durchgelaufen. Dieser Punkt ist die einzige Stelle, die *beide* Pässe
unabhängig an *derselben* Stelle als gravierend isoliert haben → höchste
Konfidenz, keine Designdiskussion über das *Ob*, nur über das *Wie*.

## Problem (Warum)

Der fragilste Teil von PeakCut ist nicht die Schnittlogik, sondern der
GUI-/Prozess-Rand. Konkret, mit Fundstellen:

1. **Frozen-Analyse-Timeout faktisch wirkungslos** —
   `workers.py:~91` `_run_multiprocess()`: die `while proc.is_alive()`-
   Pollschleife läuft ohne Deadline; `proc.join(timeout=600)` kommt erst
   *danach*, wenn die Schleife schon zurück ist. Im gebündelten `.app`
   hat die Analyse damit effektiv **keinen** 10-Minuten-Timeout, obwohl
   Doku/Watchdog ihn behaupten. Zusätzlich: `proc.exitcode` kann `None`
   sein → `!= 0` true → fälschliches „Analyse fehlgeschlagen". *Echter
   latenter Bug, kein Stilthema.*
2. **Prozess-Handle ohne Lock** — `AnalysisWorker`: `self._process`
   wird aus dem Watchdog-Lambda *und* dem Worker-Thread angefasst
   (`workers.py:~119-191`) → Race zwischen Kill und normalem Ende.
3. **GUI-Blockade im Cleanup** — `ScreenshotWorker`-Cleanup wartet bis
   3 s pro Worker auf dem GUI-Thread; `cleanup()` macht überlebende
   Worker nicht `deleteLater()` (`video_preview_peak.py:~530-560`).
4. **closeEvent unvollständig** — greift in `_worker._process`-Interna
   und behandelt nur den Subprozess-, nicht den Multiprocessing-Pfad
   (`main_window.py:~291-307`).

**Meta:** Genau diese Zone (`workers.py`, `video_preview_peak.py`,
`analysis_process.py`, `main_window.py`) hat **wenig bis keine** eigenen
Tests. Die Crash-Zone ist die Test-Lücke. Härtung *und* Test-Aufbau
gehören zusammen.

## Ziel (Was)

Der Worker-/Subprocess-/Prozess-Lebenszyklus ist deterministisch und
nachweisbar korrekt für: normales Ende, Timeout, Abbruch/Close,
Dev-Pfad *und* Frozen-`.app`-Pfad. Keine Endlos-Analyse, keine
Race-bedingten Falschmeldungen, kein GUI-Einfrieren beim Cleanup,
sauberer Shutdown beider Prozess-Pfade.

## Umfang / Nicht-Ziele

- **In Scope:** die vier Punkte oben + die dafür nötige Testabdeckung
  (Timeout greift, Abbruch sauber, exitcode-Logik korrekt, closeEvent
  beendet beide Pfade). TDD für die historisch untestete Zone ist
  *Teil* der Aufgabe, nicht optional.
- **Nicht-Ziel:** Kein Rewrite der Worker-Architektur, keine neue
  Threading-Bibliothek, kein „while ich hier bin"-Refactoring.
  Gezielte Härtung, kein Umbau.
- **Nicht-Ziel:** Performance/Streaming (= getrennt HC-3),
  Timeline-Modell (= HC-5).

## Harte Randbedingungen

1. **Keine Regression des cutter-validierten Folgenschnitt-/
   Keyboardstellen-Pfads.** Bestehende Regressionswächter müssen grün
   bleiben; Verhalten bit-/frame-stabil wo bisher gesichert.
2. **Qt-frei bleibt Qt-frei** — Härtung passiert in der GUI-/Worker-
   Schicht, nicht im `core/`.
3. **Leitplanke unangetastet** — Keyboardstellen-Export läuft weiter
   immer, auch bei Analyse-/Worker-Fehler.
4. **Dev- und Frozen-Pfad gleichwertig** behandeln — der Frozen-Pfad
   ist genau der, der heute kaputt ist; er darf nicht „nur in Dev"
   getestet sein.

## Akzeptanzkriterien

- Analyse im Multiprocess-/Frozen-Pfad bricht nachweislich nach der
  Deadline ab (Test simuliert Hänger → Timeout greift, kontrollierte
  Fehlermeldung, kein `None`-exitcode-Falschpositiv).
- Abbruch/Close beendet beide Prozess-Pfade sauber, ohne Zombie, ohne
  GUI-Freeze; Test deckt closeEvent für beide Pfade ab.
- Kein gleichzeitiger ungeschützter Zugriff auf das Prozess-Handle
  (Race nachweisbar geschlossen oder strukturell ausgeschlossen).
- Worker-Cleanup blockiert den GUI-Thread nicht spürbar; Überlebende
  werden korrekt freigegeben.
- Volle Suite grün; neue Worker-/Lifecycle-Tests dauerhaft im CI.

## 4-Augen-Prozess

Spec (Claude) → **Max liest gegen (Gate)** → Carl schreibt den
Umsetzungsplan (Bau-Basis) → Claude verifiziert Carls Plan gegen den
echten Code + baut TDD, `superpowers:systematic-debugging` für die
Bug-Anteile → Gates wie von Carl gesetzt → Max entscheidet Merge.
Kein Bau vor Carls Plan.
