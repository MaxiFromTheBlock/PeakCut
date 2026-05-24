# Wiedergabe-UX-Slice (#76) — Design

**Status:** Design, abgenommen 2026-05-21 (Max). Carl-Plan folgt.
**Slot in Roadmap:** Smoke ✓ → **#76 (dies hier)** → #71 Phasing → #70 Prompt-Tuning.

---

## Hintergrund

Smoke 2026-05-21 an Sheila-de-Liz-Material hat die Sinnabschnitt-
Pipeline (#3-Rev) erfolgreich an echtem Material bewährt — 35 von 36
Peaks bekamen narrative Vorschläge mit Konfidenz 0.78–0.80. Max kann
diese Vorschläge aber **nicht beurteilen**, weil die Wiedergabe-Schicht
UX-broken ist:

- Der separate Sinnabschnitt-▶-Knopf startet das Video stumm
  (Audio bleibt aus, Bild läuft).
- Drückt Max anschließend Play, hört er den **Mic-Mode-Mix (±15 s)**
  und nicht den Sinnabschnitt — alte Logik blieb aktiv neben der
  neuen.
- Audio und Bild sind nicht synchron, weil QMediaPlayer (Video) und
  simpleaudio (Mix) als zwei unabhängige Pfade gestartet werden.

Der Smoke ist damit hörmäßig blockiert. Bevor Prompt-Tuning (#70)
oder Phasing-Fix (#71) Sinn ergeben, muss die Wiedergabe sortiert
werden — der Hör-Workflow ist Voraussetzung für jedes Qualitäts-
Urteil über die neue Pipeline.

---

## Ziel

Eine **klare, konsistente Wiedergabe-UI** über alle drei Hör-Perspektiven
(Keyboard-Klick, Sprach-Kontext, Sinnabschnitt), in der Play immer
genau das spielt, was der gerade gewählte Mode signalisiert — Bild
synchron zum Audio.

**Nicht-Ziel:** Auto-Mix-Generierung (eigener späterer Roadmap-Punkt),
Prompt-Tuning, Phasing-Fix, neue Decider-Logik.

---

## Design-Entscheidungen (Max, 2026-05-21)

1. **Drei Modi statt zwei.** Der bestehende Mode-Knopf bekommt
   einen dritten Zustand: **Key → Speak → Smart → Key …**.
   - „Key" = vorher „Keyboard-Mode" (1 s Preview, Keyboard-Spur).
   - „Speak" = vorher „Mic-Mode" (±15 s Mix-Kontext).
   - „Smart" = neuer Sinnabschnitt-Mode (Mix-Audio, Fenster
     start_ms–end_ms aus dem #3-Rev-Decider).

   Begriffe „Key/Speak/Smart" sind die UI-Labels (kurz, klar). Der
   interne Mode-Enum kann den vorhandenen Namen behalten, solange das
   UI mappt.

2. **Play/Stop/Vor/Zurück sind über alle Modi identisch.**
   - Play startet die Mode-spezifische Wiedergabe für den aktuellen
     Peak.
   - Stop hält an.
   - Vor/Zurück wechselt den Peak, **Mode bleibt erhalten**.
   - Es gibt **keinen separaten Sinnabschnitt-▶-Knopf mehr**. Smart-
     Mode + Play tut, was er bisher tat — er entfällt redundant.

3. **Bild läuft synchron zum Audio in allen Modi.** Während der
   Wiedergabe läuft das Video im aktiven Fenster mit (Key: 1 s,
   Speak: ±15 s, Smart: start_ms–end_ms). Bei Stop pausiert beides am
   aktuellen Frame.

4. **Audio-Quelle für Smart = Mix** (gleiche Quelle wie Speak,
   anderes Fenster). Auto-Mix-Generierung für Folgen ohne Mix ist
   bewusst ausgeklammert (Pattern wie Descript-Upload, eigener
   Roadmap-Punkt).

5. **Smart-Mode bei Peak ohne Sinnabschnitt:** Play-Knopf ist
   **disabled (ausgegraut)**. Hover-Tooltip:
   „Kein Sinnabschnitt für diesen Drücker."
   Vor/Zurück bleibt aktiv; auf nächstem Peak mit Vorschlag wird
   Play wieder aktiv. „Kein Sinnabschnitt" greift bei:
   - ignoriertem Peak,
   - DECIDER_VERWORFEN (Bremse hat verworfen, Konfidenz 0.0),
   - INFRA_FEHLT (kein Key/Modell/Transkript),
   - generell: kein gültiger ClipBoundary in der `.peakcut`-Akte.

6. **Mode-Wahl ist sticky über alles** — in `config.json` persistiert,
   überlebt App-Neustart. Bewusst eine persönliche Präferenz, kein
   Pro-Peak-State.

---

## UI-Verhalten im Detail

### Mode-Knopf

- Ein einziger Toggle-Knopf, der zyklisch durch die drei Zustände
  schaltet (klicken → nächster Mode).
- Aktuelle Mode-Bezeichnung sichtbar (Label im Knopf oder daneben).
- Smart bleibt selektierbar **auch wenn der aktuelle Peak keinen
  Sinnabschnitt hat** — nur Play wird dann gegated (s. Punkt 5 oben).
  Begründung: Mode-Wahl ist persönliche Präferenz, nicht peak-
  abhängig. Wenn der Knopf sich pro Peak verändert, fühlt sich UI
  unvorhersehbar an.

### Play-Knopf

- Klick startet Wiedergabe entsprechend aktuellem Mode + aktuellem
  Peak.
- Während Wiedergabe wechselt der Knopf auf „Stop" (entspricht
  aktuellem Verhalten).
- Bei Erreichen des Fenster-Endes (Out-Point) stoppt die Wiedergabe
  automatisch und der Knopf springt zurück auf „Play".
- **Disabled-State** nur in einem Fall: Mode=Smart UND kein Sinn-
  abschnitt für aktuellen Peak.

### Vor / Zurück

- Wechselt Peak.
- Mode bleibt unverändert.
- Falls eine Wiedergabe läuft, wird sie gestoppt; neuer Klick auf
  Play startet sie für den neuen Peak.
- Falls neuer Peak im aktuellen Mode keine Wiedergabe erlaubt (s.
  Disabled-Regel oben), springt Play-Knopf in disabled-State.

### Mode-Wechsel während Wiedergabe

- Klick auf Mode-Knopf während laufender Wiedergabe **stoppt** die
  Wiedergabe. Nutzer drückt anschließend Play neu, hört den neuen
  Mode. Begründung: simpel, vorhersehbar, kein „mitten im Fenster
  switchen mit unklarem Anker".

---

## Architektur-Skizze

### Was bleibt

- `core/session.py`: `mode` als Feld, `switch_mode()`-Methode.
- `core/playback.py`: simpleaudio-basierte Mix-Wiedergabe mit
  `play_from(in_ms, out_ms)`-Vertrag.
- `gui/video_preview_peak.py`: QMediaPlayer + LUT + Brightness.
- `gui/review_page.py`: Peak-Navigation, Mode-Knopf, Play-Knopf,
  Sinnabschnitt-Status.

### Was sich ändert

- **Mode-Enum** bekommt dritten Wert (Smart). Mapping zu UI-Label
  „Key/Speak/Smart".
- **Mode-Persistenz**: aktueller Mode wird beim Wechseln in
  `config.json` geschrieben, beim App-Start gelesen.
- **Play-Dispatcher** in `review_page` (oder gekapselt in Session):
  je nach Mode bestimmt er Audio-Fenster + Video-Fenster.
- **Audio-Video-Synchronisation**: einheitlicher Start-Synchronisations-
  punkt zwischen `playback.play_from()` (simpleaudio) und
  `video_preview_peak.play_from(in_ms, out_ms)` (QMediaPlayer). Beide
  bekommen identische in_ms/out_ms.
- **Sinnabschnitt-Status-Lookup**: ReviewPage fragt die `.peakcut`-
  Akte (oder Session-Cache) ab, ob der aktuelle Peak einen gültigen
  ClipBoundary hat → bestimmt Play-Disabled-State + Tooltip-Text.
- **Sinnabschnitt-▶-Knopf wird entfernt**.

### Technisches Risiko (explizit für Carl-Plan)

**Audio/Video-Synchronisation** ist der heikelste Teil dieses Slices —
und der Wurzelgrund für den Smoke-Befund „war nicht synchron". Aktuell
laufen QMediaPlayer (Video) und simpleaudio (Mix) als zwei
unabhängige Pfade. Ohne abgestimmten Startpunkt entsteht Drift.

Zwei mögliche Lösungswege, **Carl entscheidet im Plan**, welcher
gewählt wird (oder ob es einen dritten gibt):

- **(a) QMediaPlayer übernimmt auch das Audio** — Video-Datei wird
  entstummt, simpleaudio entfällt im UI-Pfad. Einfacher, ein einziger
  Lifecycle. Nachteil: Audio-Quelle ist dann der Kamera-Ton, nicht
  der Mix → bricht Design-Entscheidung 4 (Smart soll Mix nutzen).
  Vermutlich verworfen, aber sauberer aufzuschreiben als unklar zu
  lassen.
- **(b) Mix per simpleaudio + Video per QMediaPlayer, mit
  präziser Start-Synchronisation** — beide bekommen denselben in_ms,
  werden in derselben Funktion in stabiler Reihenfolge angestoßen,
  optional Drift-Monitoring per Timer (jede x ms vergleichen,
  korrigieren wenn > Schwelle). Mehr Code, mehr Tests, aber treu
  zur Design-Entscheidung.

Wir bevorzugen (b). Carl wird gebeten, im Plan den genauen
Synchronisationspunkt + Drift-Bremse zu definieren, idealerweise mit
einem Mini-Mess-Skript (analog zu `verify_smart_boundary_real.py`),
das die Drift an echtem Sheila-Material misst.

---

## Out-of-Scope (bewusst nicht in #76)

- **Auto-Mix-Generierung** (PeakCut erzeugt selbst einen Mix, wenn
  keiner vorhanden ist). Pattern aus #3-Rev R2 (Descript-Upload),
  eigener Roadmap-Punkt, brauchen wir nicht für Sheila/Hotel-Matze.
- **Phasing-Fix** im MP3Exporter (Task #71). Direkt im Anschluss
  geplant — eigener Slice, weil andere Codeebene (Exporter, nicht
  ReviewPage).
- **Prompt-Tuning** (Task #70). Erst nach Phasing — und erst, wenn
  die Wiedergabe verlässlich genug ist, dass Max + Carl A/B-Urteile
  abgeben können.
- **Neuer Decider, neuer Cache, neues `.peakcut`-Schema.** Reine UI-
  und Wiedergabe-Schicht.

---

## Tests-Plan (Vorschlag; Carl-Plan kann verfeinern)

- **Mode-Enum + Persistenz:** drei Modi, Round-Trip durch
  config.json, Sticky über simulierte App-Neustarts.
- **Mode-Cycle:** Klick zyklisch Key → Speak → Smart → Key.
- **Play-Dispatcher pro Mode:** parametrisiert über die drei Modi,
  jeweils korrekte Audio- und Video-Fenster ausgewählt
  (Mock-Playback + Mock-Video, nur Aufrufe verifizieren).
- **Smart-Disabled-Logik:**
  - Peak ignoriert → Play disabled, Tooltip vorhanden.
  - DECIDER_VERWORFEN → Play disabled.
  - INFRA_FEHLT → Play disabled.
  - Gültiger ClipBoundary → Play enabled.
- **Sinnabschnitt-▶-Knopf entfernt:** Regression — Knopf existiert
  nicht mehr in der ReviewPage.
- **Audio/Video-Sync (Mess-Skript, kein Test im üblichen Sinn):**
  echtes Sheila-Fenster spielen, Drift in ms loggen, harte Obergrenze
  als Akzeptanzkriterium definieren (Carl-Plan-Vorschlag).
- **Stufe-1-Schutz:** Keyboardstellen-XML byte-identisch vor/nach
  Slice. Pin-3-Garantie aus #3-Rev gilt unverändert.

---

## Carl-Briefing (für Max zum Weiterleiten)

Übergabe analog zu #3-Rev:
1. Diese Spec lesen.
2. Plan im Stil der vorigen Carl-Pläne (Tasks, Files, Steps, TDD-Gate).
3. Besonderes Augenmerk: **Synchronisations-Strategie**
   (Lösungsweg (b) vs. anderen Vorschlag), inkl. Mini-Mess-Skript
   für die Drift-Verifikation an echtem Sheila-Material.
4. Stufe-1-Schutz (Keyboardstellen-XML byte-identisch) explizit als
   Pin im Plan.
5. Plan zurück an Max → Claude verifiziert gegen Code → TDD-Bau
   Task-für-Task mit Carl-Gates.

---

*Spec-Pfad:* `docs/specs/2026-05-21-wiedergabe-ux-slice-design.md`
