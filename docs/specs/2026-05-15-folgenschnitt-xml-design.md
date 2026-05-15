# Design: Folgenschnitt-XML (Auto-Kameraschnitt)

*Stand: 2026-05-15 (Rev. nach externem Review) · Status: Design, noch NICHT in Umsetzung — Reviewer-Kollaboration läuft · MVP = Stufe 1*

---

## Für externe Reviewer: Was ist PeakCut?

PeakCut ist eine Python/PyQt6-Desktop-App (macOS) für die Postproduktion des
Podcasts "Hotel Matze". Aktueller Funktionsumfang:

- Import von Audio-Spuren (mehrere Mikrofone) + mehreren Kamera-Videos einer
  Aufnahme-Session.
- **Video-Audio-Sync**: Findet den zeitlichen Versatz jeder Kamera zur
  Referenz-Audiospur per FFT-Kreuzkorrelation (`core/sync.py`).
- **Peak Detection**: Erkennt Fußpedal-/Keyboard-Marker in einer Audiospur
  (der Moderator drückt während der Aufnahme ein Pedal an interessanten
  Stellen) → `core/detection.py`.
- **Export**: MP3-Clips, TXT-Timecodes und eine **FCP7-XML** (für
  Premiere/FinalCut/DaVinci), die die markierten Stellen als Clips auf eine
  Timeline legt → `core/exporters.py` (`XMLExporter`).

Technische Eckdaten:

- Analyse läuft in einem **separaten Subprozess** (`core/analysis_process.py`),
  angestoßen von einem `QThread` (`gui/workers.py`). Ergebnis kommt als JSON
  zurück.
- State lebt in `core/session.py` (`PeakCutSession`, Qt-frei).
- Datei-Abstraktion: `core/project.py` (`PeakCutProject`).
- Export-Worker: eigener `QThread` (`gui/workers.py` → `ExportWorker`).
- 94 Tests (pytest), CI via GitHub Action.
- Repo-Root liegt unter `App/`. Zentrale Architektur-Doku: `../CLAUDE.md`
  (außerhalb des Repos), Kurzfassung: `../docs/CONTEXT.md`.

Aufnahme-Setup Hotel Matze:

- Jeder Sprecher hat ein eigenes Mikrofon. Konvention: MIC1 = Moderator
  (Max/"Matze"), MIC2 = Gast. MIC3 = Keyboard/Pedal. Konvention ist
  überschreibbar (variiert selten).
- Aktuell 3 Kameras, perspektivisch mehr. Keine feste Kamera→Rolle-Zuordnung
  über Aufnahmen hinweg (variiert pro Aufnahmetag). Typische Rollen:
  Matze-Wide, Gast-Wide, Gast-Close.

---

## Ziel

Zusätzlich zur bestehenden Keyboardstellen-XML soll PeakCut eine **zweite XML**
erzeugen: einen **kompletten Rohschnitt der Folge** mit bereits gesetzten
Kamerawechseln. Der Cutter öffnet sie in Premiere/FCP/DaVinci und hat einen
sinnvollen Startpunkt statt einer leeren Timeline. Es geht ausdrücklich um
einen *Rohschnitt-Vorschlag*, nicht um ein finales Werk.

Die zweite XML kommt **automatisch beim normalen Export** mit raus (kein
Extra-Klick).

---

## Die drei Stufen (Gesamtvision)

| Stufe | Inhalt | Status |
|-------|--------|--------|
| **1** | Wer spricht → seine Wide-Kamera. Vorausschauend in Pausen. | **MVP — dieses Dokument** |
| **2** | Redet *eine* Person lange am Stück → innerhalb des Monologs zwischen ihren Kameras (Wide/Close) auflockern. Ruhig beginnend, progressiv dichter, mit Mindestabstand-Deckel. | Später |
| **3** | AI erkennt Emotionalität / neuen Gesprächsteil → gezielter Wechsel auf Close. Braucht Transkript + Sentiment-Modell. | Forschung, später |

Dieses Dokument spezifiziert **nur Stufe 1**. Stufen 2 und 3 sind hier nur
festgehalten, damit Stufe-1-Architekturentscheidungen sie nicht verbauen.

---

## Stufe 1 — Verhalten

**Eingaben:**
- Mic-Spuren mit Zuordnung Mic→Sprecher (Default-Konvention, überschreibbar).
- Kamera-Videos mit Zuordnung Kamera→Rolle (Matze-Wide / Gast-Wide /
  Gast-Close / …), pro Aufnahme manuell gesetzt.
- Video-Offsets aus der bestehenden Sync-Analyse.

**Sprecher-Erkennung (präzisiert nach externem Review 2026-05-15):**

Nicht "Mic über festem Schwellwert = Sprecher" (zu naiv wegen Mic-Übersprechen).
Stattdessen relativer Pegelvergleich mit Dominanz und Glättung — kein AI, keine
Diarization, keine Kreuzkorrelation:

- Kurze Fenster (100–250 ms), pro Mic Energie im Sprachbereich (RMS o. ä.).
- Pro Spur eigenen Grundpegel ("Noise-Floor") schätzen (niedriges Perzentil).
- Ein Sprecher gilt nur als aktiv, wenn er **deutlich über seinem eigenen
  Grundpegel** liegt.
- Ein Sprecherwechsel nur, wenn eine Spur die andere **mit deutlichem Abstand
  dominiert** (Richtwert 6–10 dB).
- Hysterese + Glättung; kurze Lücken innerhalb desselben Sprechers mergen.
- Bei Unsicherheit / Overlap: **beim vorherigen Sprecher bleiben** (konservativ
  > nervös — für einen Rohschnitt ist "zu spät schneiden" besser als "ständig
  falsch hin und her").

**Schnitt-Regeln (arbeiten auf geglätteten Sprecher-Turns, nicht auf Rohpegeln):**
1. Ein Sprecherwechsel (neue Kameraentscheidung) nur, wenn jemand **≥ 5 Sekunden
   am Stück** spricht. Kurze Einwürfe ("mhm", "ja") lösen keinen Wechsel aus.
2. **Mindest-Shot-Länge** ~2 Sek: kein Bild kürzer als das stehen lassen (gegen
   nervöse Schnitte).
3. Aktiver Sprecher → seine **Wide**-Kamera. (Gast-Close wird zugeordnet, aber
   in Stufe 1 **nicht** im Schnitt verwendet.)
4. **Vorausschauender Schnitt (Anticipation):** Nur bei einer *echten* Pause
   (> ~0,7 Sek). Folgt ein anderer Sprecher, wird **höchstens 1,5–2 Sek vor**
   dessen Einsatz auf seine Kamera geschnitten — *unabhängig von der
   Pausenlänge* (ersetzt die frühere "Mitte der Pause"-Regel; die skalierte bei
   langen Denkpausen schlecht). Folgt derselbe Sprecher, bleibt das Bild stehen.
5. Anfang der Folge: ergibt sich automatisch (Folge startet auf der Kamera
   dessen, der zuerst ≥5 Sek spricht).
6. Beide gleichzeitig / Unsicherheit: Bild bleibt beim vorherigen Sprecher,
   kein Hin-und-Her. Der Cutter korrigiert solche Stellen manuell.

**Ausgabe:**
- Zweite XML ("Folgenschnitt") mit den Kamera-Cuts auf einer durchgehenden
  Timeline, automatisch beim Export, neben der bestehenden Keyboardstellen-XML.

---

## UI-Änderungen (Review-Seite)

Die bestehende Leiste der Review-Seite (Kamera-Auswahl, LUT, Helligkeit) wird
erweitert:

- Pro Kamera ein Drop-Down **"Diese Kamera ist: [Matze-Wide / Gast-Wide /
  Gast-Close / …]"**. Der Nutzer schaltet durch die Kameras (sieht jeweils das
  Bild) und ordnet zu.
- **Mic-Zuordnung**: "Mic 1 = [Matze ▼]", "Mic 2 = [Gast ▼]", vorbelegt mit der
  Konvention, änderbar.

Keine neue Seite, keine Änderung am bestehenden 3-Seiten-Flow
(Welcome → Analysis → Review).

---

## Ausdrücklich NICHT in Stufe 1 (Scope-Grenze)

- Keine Nutzung der Close-Kamera im Schnitt.
- Keine Auflockerung bei langen Monologen (Stufe 2).
- Keine AI / kein Transkript / keine Emotionserkennung (Stufe 3).
- Keine Änderung am bestehenden Keyboardstellen-Export.

---

## Architektur / Pipeline (nach externem Review 2026-05-15)

Folgenschnitt ist ein anderes Kaliber als Keyboardstellen: Keyboardstellen sind
punktuelle Clips, Folgenschnitt ist eine durchgehende Timeline mit Zustand über
die ganze Folge. Deshalb **keine** Direktstrecke "Pegel → XML", sondern eine
klar getrennte, je einzeln testbare Kette:

```
speaker_activity   pro Zeitfenster: Pegel je Mic, Dominanz, Confidence
      │            (core/speaker_activity.py — eigenes Modul)
      ▼
speaker_turns      geglättete Sprecherabschnitte (Hysterese, Lücken-Merge,
      │            5-Sek-/Mindest-Shot-Regeln greifen hier)
      ▼
edit_decisions     konkrete Kameraentscheidungen mit Start/Ende
      │            (Anticipation-Regel; rein logisch, ohne XML — unit-testbar)
      ▼
FolgenschnittXMLExporter   schreibt nur noch diese Entscheidungen als
                           flache FCP7-Timeline (eigener Exporter)
```

**Modul-/Einbettungs-Entscheidungen:**
- Sprecher-Analyse als **eigenes Core-Modul** `core/speaker_activity.py`, vom
  bestehenden Analyse-Subprozess aufgerufen — *nicht* in `analysis_process.py`
  vergraben. Bleibt damit testbar und UI-blockierungsfrei (Analyse läuft eh
  schon im Subprozess).
- Audiodaten **fensterweise / runtergesampelt** lesen (soundfile/NumPy), nicht
  alles in den RAM. Niedrig aufgelöste Fenster → vernachlässigbar gegenüber dem
  bestehenden Video-Sync.
- Ergebnisse als JSON-freundliche Struktur (passt perspektivisch zur V3-Idee
  `.peakcut/speaker_activity.json`).
- **Bestehenden `XMLExporter` nicht verbiegen** — er ist für Keyboardstellen
  gebaut. Folgenschnitt bekommt einen eigenen Exporter (PeakCut hat dafür schon
  die `BaseExporter`-Struktur).

## Contracts — Grundprinzipien (Reviewer-Checkliste, Stand 2026-05-15)

Die Datenmodelle (`ActivityFrame`, `SpeakerTurn`, `EditDecision`, Mic-Rollen,
Kamera-Rollen) werden zuerst festgelegt. Verbindliche Prinzipien:

- **Zeitbasis: intern konsequent Millisekunden.** Frame-Umrechnung **nur ganz
  am Rand im Exporter**. Hält die Audioseite lesbar und begrenzt
  Rundungsfehler auf den Exporter. (Konsistent mit bestehendem PeakCut-Muster:
  `position_ms` etc. intern, `ms_to_frames(ms, fps)` erst im Export.)
- **Einheiten explizit im Feldnamen** (`*_ms`), keine nackten Zahlen.
- **Rollen-Mapping** (Mic→Sprecher, Kamera→Rolle) als eigene klare Struktur,
  nicht implizit über Dateinamen/Reihenfolge.
- **Serialisierbar** (JSON-rund), damit `speaker_turns.json` /
  `edit_decisions.json` und spätere `.peakcut/`-Ablage trivial sind.
- **Unit-testbar ohne Audio/XML**: `edit_decisions` aus `speaker_turns`
  ableitbar als reine Funktion.
- **Stufe-2-andockbar**: Modelle so schneiden, dass die spätere Auflockerung
  bei langen Monologen (zusätzliche Wechsel innerhalb eines Turns) additiv
  andocken kann, ohne die Stufe-1-Strukturen umzubauen.

Genau diese Punkte prüft der externe Reviewer gegen, sobald die Contracts
stehen.

## XML-Format-Entscheidung

- **Ein Format: FCP7-XML, flache lineare Timeline** (harte Schnitte,
  durchgehendes Audio, jeweils aktive Kamera). **Keine** echte
  Multicam-Sequenz (NLE-spezifisch, riskanter) — für einen Rohschnitt nicht
  nötig.
- Zielprogramme bei Hotel Matze: **Premiere + DaVinci Resolve** (Cutter Lukas
  & Alex). Premiere importiert von den XML-Optionen praktisch nur FCP7-XML;
  Resolve kann FCP7-XML ebenfalls. FCP7-XML ist außerdem das Format, das
  PeakCut heute schon schreibt → kleinster gemeinsamer Nenner, kein
  Format-Wechsel, keine Programm-Auswahl im UI nötig.
- Final Cut Pro (FCPXML) wird bei HM nicht genutzt → kein FCPXML-Exporter
  (YAGNI). Falls je nötig: später eigener Exporter.
- **Pflicht-Validierung:** Mit einer kurzen echten Test-Folge in *Premiere und
  Resolve* importieren. Zickt eine der beiden → dann (und nur dann) ein
  zweiter, programmspezifischer Exporter.

## Start-Parameter (interne Konstanten / Preset — NICHT im UI)

Default-Profil, an echten Ausschnitten zu kalibrieren. Bewusst **nicht** als
UI-Regler — PeakCut soll sich nicht wie ein Mischpult bedienen lassen, sondern
"vernünftig genug" out-of-the-box sein. Liegt als interne Konstanten / kleines
Preset im Code.

| Parameter | Startwert |
|-----------|-----------|
| Fenstergröße | 200 ms |
| Hop / Schrittweite | 100 ms |
| Noise-Floor | 10. Perzentil pro Spur |
| Aktiv über Noise-Floor | ~ +10 dB |
| Dominanz zum Wechseln | +6 dB |
| Dominanz zum Halten | +3 dB |
| Glättung | 300–500 ms |
| Lücken mergen | bis 500–700 ms |
| Sprecherwechsel relevant | ≥ 5 s |
| Mindest-Shot | 2 s |
| echte Pause | > 0,7 s |
| Anticipation | 1,5 s (max. 2 s) |

Zwei getrennte Dominanz-Schwellen (Wechsel +6 dB / Halten +3 dB) = Hysterese.

## Debug-Output (zwei Rollen)

- `speaker_activity.csv` — pro Fenster: Zeit, Pegel je Spur, Noise-Floor,
  Dominanz, roher Sprecher, geglätteter Sprecher, Confidence. Zum schnellen
  Draufschauen in Numbers/Excel ("hier denkt er 12 s Gast, obwohl Matze redet").
- `speaker_turns.json` — geglättete Turns.
- `edit_decisions.json` — finale Kameraentscheidungen (Tests, Regression,
  perspektivisch `.peakcut/`).
- Wenn nur eins für den ersten Wurf: **CSV**.

## MVP-Reihenfolge (Risiko zuerst entkoppeln)

1. **Datenmodelle/Contracts** festlegen: `ActivityFrame`, `SpeakerTurn`,
   `EditDecision`, Mic-Rollen, Kamera-Rollen. (Definiert die Schnittstellen
   zwischen den Pipeline-Stufen, bevor Logik gebaut wird.)
2. **`speaker_activity.py`** bauen + `speaker_activity.csv`-Debug.
3. **`FolgenschnittXMLExporter` früh** mit *handgebauten Fake-edit_decisions*
   testen und in Premiere + Resolve importieren. → Beweist das XML-Risiko mit
   einer Mini-Timeline, *bevor* viel Aufwand in die Erkennung fließt.
4. **`speaker_turns` + `edit_decisions`** bauen, stark unit-testen.
5. **End-to-end** mit realen Ausschnitten, Parameter kalibrieren, *dann erst*
   automatischen Export aktivieren.

Begründung (Reviewer): Wer erst die Sprechererkennung perfektioniert und dann
merkt, dass Premiere/Resolve an der XML-Struktur zickt, hat Sicherheit an der
falschen Stelle aufgebaut. XML-Import einmal früh beweisen, dann entspannt
weiter.

## Test-Strategie

Härtester Fall für Stufe 1 ist **nicht** der lange Monolog (Kamera steht ja
einfach), sondern die **lebendige Gesprächsphase**: schneller Schlagabtausch,
kurze Einwürfe ("ja", "mhm", Lachen), leichter Overlap, ein lauter Sprecher der
stark ins andere Mic blutet, ein leiserer der trotzdem erkannt werden muss,
ein paar echte Denkpausen (für Anticipation).

Nicht mit ganzer Folge starten, sondern **3 reale Ausschnitte à ~5 Min**:
1. "Normaler Dialog"
2. "Stress: Overlap / schneller Wechsel"
3. "Pausen / langer Monolog"

Danach **eine ganze Folge** nur für Performance, Premiere/Resolve-Import und
Gesamteindruck ("zappelt es oder spart es Arbeit?").

---

## Durch externes Review geklärt (2026-05-15)

Die ursprünglich offenen Punkte wurden durch das Review entschieden:

1. **Mic-Übersprechen:** Relativer Pegelvergleich + eigener Noise-Floor pro
   Spur + Dominanz-Schwelle + Hysterese (siehe "Sprecher-Erkennung"). Kein AI,
   keine Kreuzkorrelation (hilft beim Sync, nicht bei "wer spricht").
   Konservativ vor nervös.
2. **XML-Format:** FCP7-XML, flache Timeline, ein Format für Premiere+Resolve
   (siehe "XML-Format-Entscheidung"). Per echter Test-Folge zu validieren.
3. **Zustandslogik:** Entschärft — Schnitt-Regeln arbeiten auf *geglätteten
   Turns* statt Rohpegeln, plus Mindest-Shot-Länge und korrigierte
   Anticipation (max 1,5–2 Sek, nur bei echter Pause > 0,7 Sek).
4. **Einbettung:** Eigenes Modul `core/speaker_activity.py`, vom bestehenden
   Analyse-Subprozess aufgerufen; fensterweises Lesen → geringe
   Zusatz-Wartezeit.

## Durch zweite Reviewer-Runde geklärt (2026-05-15)

- **Parameter:** Default-Profil + empirische Kalibrierung an echten
  Ausschnitten (nicht theoretisch tot-tunen, nicht ohne Profil starten). Werte
  als interne Konstanten, *nicht* ins UI. → Sektion "Start-Parameter".
- **Debug:** CSV *und* JSON mit unterschiedlicher Rolle; CSV zuerst. → Sektion
  "Debug-Output".
- **Test:** Härtester Fall = lebhafter Schlagabtausch, nicht Monolog. 3 reale
  Ausschnitte à 5 Min + danach ganze Folge für Performance/Import. → Sektion
  "Test-Strategie".
- **Reihenfolge:** XML-Import-Risiko früh entkoppeln (Contracts → activity+CSV
  → XML früh mit Fake-Decisions in Premiere/Resolve → turns/decisions →
  e2e+kalibrieren). → Sektion "MVP-Reihenfolge".

Reviewer-Fazit: Spec ist in gutem Zustand zum Bauen; erste Umsetzung bewusst
als **Messinstrument** behandeln, nicht als "Feature fertig" — erst sehen, was
echte Folgen sagen, dann Parameter festziehen.

## Was Max beisteuern muss

- **3 reale Ausschnitte à ~5 Min** aus echten Folgen: (1) normaler Dialog,
  (2) Overlap/schneller Wechsel, (3) Pausen/Monolog. Plus eine ganze Folge für
  den abschließenden Performance-/Import-Test.
- **Schnitt-Auge bei der Kalibrierung:** das Erfolgsurteil ("zappelt es oder
  spart es Arbeit?") ist eine Cutter-Einschätzung, keine Metrik.

---

## Erfolgskriterium

Stufe 1 ist erfolgreich, wenn der Rohschnitt in **Premiere und Resolve**
sauber importiert und **ruhig, überwiegend richtig** ist — die Kamera
überwiegend auf der sprechenden Person, ohne nervöses Hin-und-Her, sodass der
Cutter sichtbar Arbeit spart und darauf aufbauen statt bei null anfangen kann.
Ausdrücklich **nicht** das Kriterium: perfekte Sprechererkennung. Für einen
Rohschnitt ist eine konservative Logik besser als eine clevere, die zappelt.

---

## Revisionen

- **2026-05-15 (initial):** Brainstorming-Ergebnis, Stufe 1, mit offenen
  technischen Punkten für externes Review.
- **2026-05-15 (nach externem Review):** Sprecher-Erkennung präzisiert
  (relativer Pegel + Noise-Floor + Dominanz + Hysterese statt fixem
  Schwellwert). Pipeline-Architektur eingeführt (speaker_activity →
  speaker_turns → edit_decisions → eigener Exporter). Anticipation-Regel
  korrigiert (max 1,5–2 s statt "Mitte der Pause"). XML-Format entschieden
  (FCP7-XML flach, Premiere+Resolve). MVP-Vorgehen festgelegt. Verbleibende
  Punkte für nächste Reviewer-Runde markiert. Noch **nicht** in Umsetzung —
  Kollaboration mit Reviewer läuft.
- **2026-05-15 (zweite Reviewer-Runde):** Start-Parameter-Profil festgelegt
  (interne Konstanten, nicht UI). Debug-Output differenziert (CSV + JSON).
  Test-Strategie (3×5-Min-Ausschnitte, härtester Fall = Schlagabtausch nicht
  Monolog). MVP-Reihenfolge umgestellt: XML-Import-Risiko zuerst entkoppeln
  (Contracts → activity → XML früh mit Fake → turns/decisions → e2e). Spec
  laut Reviewer "in gutem Zustand zum Bauen". Erste Umsetzung als
  Messinstrument behandeln. Weiterhin **nicht** in Umsetzung — wartet auf
  Max' Freigabe + Test-Ausschnitte.
- **2026-05-15 (Reviewer-Zusatz):** Contracts-Grundprinzipien festgehalten
  (Zeitbasis intern ms, Frame-Umrechnung nur im Exporter; Rollen-Mapping
  explizit; serialisierbar; unit-testbar; Stufe-2-andockbar) — entspricht
  Reviewer-Checkliste fuer (a). Testmaterial fixiert: Folge "Hartmut Rosa"
  (MIC1/MIC2 getrennt vorhanden), 3 Ausschnitte daraus.
- **2026-05-15 (Bau, Task 2 + 2.1):** Task 2 (FolgenschnittXMLExporter)
  gebaut. Carl fand an Gate B einen echten Bug (negativer Video-Offset am
  Sequenzanfang → duration ≠ out−in). Carl spezifizierte Task 2.1
  (MVP-Policy: source-underflow clampen, lückenlose Timeline-Dauer
  erhalten, source_out = source_in + clip_dur); Claude umgesetzt + gegen
  bestehende Tests verifiziert. 5 Exporter-Tests grün, Suite 106,
  Mini-XML real konsistent.
  **Begründungs-Korrektur (Carl, nach Real-Offset-Test):** Echte
  HM-Sync-Offsets sind massiv negativ (Cam01 −01:43:14, Cam02 −01:53:23).
  Bei diesen Werten ist der geklemmte Bereich am Sequenzanfang NICHT
  "minimal versetzt", sondern ein **echter Source-Underflow von ~100 s**.
  Bewusst als MVP akzeptiert (Timeline lückenlos + importierbar +
  duration==end-start==out-in; Cutter korrigiert Anfang ggf. manuell) —
  ehrlich benannt, nicht als "minimal" verharmlost. Datei-Ende-Overflow
  weiterhin out of scope.
- **Backlog (späterer eigener Task, NICHT MVP, Carls Vorgabe):** "Video
  source underflow reporting / valid camera ranges" — Exporter soll bei
  Underflow warnen ("Cam01: ~103 s Source-Underflow am Sequenzanfang");
  später Decisions erst ab gültigem Kamerabereich oder Fallback-Kamera.
- **2026-05-15 (Gate B grün, vollständig):** Cutter-Sync-Spotcheck auf
  Real-Offset-XML (Timeline 240 s, deckt Underflow + echten Sync-Bereich):
  "ab ca. Minute 2 synchron" — passt exakt zum Underflow-Ende (~1:43–1:53).
  Offset-Formel in der Folgenschnitt-Timeline praktisch korrekt. Alle
  Gate-B-Bedingungen erfüllt: Premiere-Import/Relink ✓, Resolve geparkt
  (Max-Entscheidung A), Negativ-Underflow kein Blocker (Carl), Sync nach
  Underflow ✓. → Bau von Task 3 freigegeben.
- **2026-05-15 (Bau, Gate A grün):** Task 1 (Contracts,
  `core/folgenschnitt_models.py`) gebaut + von Carl gegen Gate-A-Checkliste
  freigegeben (Commit a445661). Offener Zukunftshinweis (blockiert Stufe 1
  NICHT): falls künftig `MATZE_CLOSE` als UI-Kamerarolle gebraucht wird,
  muss `CameraRole` erweitert werden; `EditDecision` selbst hängt nicht an
  Wide/Close, bleibt also stabil.
