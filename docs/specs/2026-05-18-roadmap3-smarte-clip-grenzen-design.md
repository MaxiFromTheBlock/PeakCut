# Roadmap #3 — Smarte Clip-Grenzen (Sinnabschnitt) — Design

> Status: **Design abgenommen von Max (2026-05-18)**, bereit für Carl-Plan.
> **Erweitert 2026-05-18 (nach Max-Review): Zwei-Stufen-Trennung mit
> gespeichertem Transkript** (Transkription früh & parallel, Sinnabschnitt
> später als Konsument) — siehe §3-Prinzip, §4. Ersetzt die frühere
> Einstufen-Reihenfolge „alles nach dem Export".
> **Verfeinert 2026-05-18 (Carl-Gegenpass + Max-Workflow-Wissen):**
> Whisper-Startzeitpunkt ist *kein* Annahme-Streit mehr — Default
> „parallel zur Analyse + Prioritätsschutz", ein **Mess-Gate** im
> Hand-Prüfskript entscheidet den finalen Default. Persistenz konkret
> als referenzierte `transcript.json` (gegen `project_archive`-Code
> verifiziert, analog `speaker_activity.csv`).
> Methode: 4-Augen — Carl schreibt den Umsetzungsplan, Claude verifiziert
> ihn gegen den echten Code + baut TDD Schritt für Schritt, Max entscheidet
> den Merge. Vorgänger: Roadmap #2 (ClipCandidate + Rückweg, Merge d8d9e33).

---

## 1. Ziel & Identität

Die heute starre Clip-Grenze **Drücker −15 s / +15 s** wird ersetzt durch
einen **klugen Sinnabschnitt**: die kleinste zusammenhängende Strecke rund
um eine Markierung, in der die ganze kleine Geschichte *vollständig*
drinsteckt — Anlauf nicht abgeschnitten, Pointe/Paukenschlag mit drin (auch
wenn er *nach* dem Drücker kommt), kein harter Schnitt am Drücker.

Maßstab für „gut": Der Abschnitt funktioniert als **eigenständige kleine
Geschichte** — jemand ohne Vorwissen versteht ihn und er fühlt sich
abgeschlossen an. Es gibt **kein festes Schema** (kein Frage-Antwort-,
kein Pointen-Template) — die Gäste sind zu verschieden (knappe
Wirtschaftserklärung / starkes Bild / lustiger Schlagabtausch). Einziger
gemeinsamer Nenner: eigenständige kleine Geschichte.

Was #3 **nicht** ist: kein fertig getrimmter 60–90-s-Clip, kein
Video-Rendern, kein KI-Kamerawechsel. #3 liefert die *Grenze* (den
Sinnabschnitt) als zusätzliche Information — das Trimmen auf Endlänge
bleibt Cutter-Arbeit.

### Workflow-Kontext (warum das so geschnitten ist)

Heute: Matze drückt während der Aufnahme das Keyboard, wenn etwas gut war
→ Marker. Nach der Aufnahme bekommt Matze die Keyboardstellen-MP3, hört
seine Stellen durch, wählt eine Handvoll aus und schickt dem Cutter Zahlen
(manchmal + Titel). Der Cutter sucht im 30-s-Fenster den guten Anfang/das
gute Ende → V1 → Matze-Feedback → V2.

Strukturelle Fakten, die die Mechanik bestimmen (von Max bestätigt):

- Der Drücker ist **immer eine Reaktion, die hinterherläuft** — nie
  vorausschauend. Der gute Inhalt liegt praktisch immer *vor* dem
  Drücker: meist kurz davor, **manchmal aber deutlich weiter zurück**
  (wenn Matze erst spät merkt, dass ein ganzer Teil stark war).
- Der Peak sitzt also **irgendwo *in* der Geschichte**, nicht an ihrem
  Ende. Nach hinten ist die variable Hauptarbeit (Strecke mal kurz, mal
  lang). Nach vorne ist es **nicht** nur „Satz zu Ende", sondern
  ebenfalls inhaltlich: bis der Gedanke landet — ein echter Paukenschlag
  *nach* dem Drücker kann das Ende sein. **Nie hart am Drücker schneiden.**
- Matzes Titel-Vorschläge sind **keine** Eingabe für PeakCut (kommt oft
  nur als Zahl, würde den Ablauf absurd machen) — die Logik arbeitet
  ausschließlich aus dem gesprochenen Inhalt.
- Fertige Clips sind real 20–60 s, max ~1:30 — aber das ist das
  *Cutter-Endprodukt*. Der Sinnabschnitt darf großzügiger sein; der
  Cutter trimmt *innerhalb* der Strecke runter. Erfolgsmaßstab: der
  Cutter muss **nie außerhalb** der vorgeschlagenen Strecke suchen.

---

## 2. Scope v1

### In Scope

**Stufe A — früh & parallel (eigener entkoppelter Job):**

1. **Transkription (Whisper lokal)** — gemeinsame Grundschicht.
   **Startet, sobald die Analyse startet**, läuft parallel und
   entkoppelt, **bremst Analyse und Keyboardstellen-Export nie**.
   Ergebnis (das Transkript) wird **in der `.peakcut`-Projektakte
   gespeichert** → einmal abgetippt, nie wieder; füttert später auch den
   Track-2-Regisseur.

**Stufe B — später & schnell (Konsument, nach dem Export-Handoff):**

2. **Deterministischer Vorbau** — Suchfenster + natürliche Schnittkanten
   (nutzt vorhandene `speaker_activity`/Pausen-Infrastruktur wieder).
3. **Semantischer Entscheider (Claude API)** + **Plausibilitätsbremse**
   mit sicherem Rückfall.
4. **Zusätzliche Ausgabe-Artefakte**: `Sinnabschnitte - {Gast}.xml` +
   `.txt` für **alle** Drücker, neben den unveränderten
   Keyboardstellen-Dateien.

Stufe B nimmt nur das **schon gespeicherte Transkript** und ist dadurch
schnell (das Langsame ist in Stufe A längst gelaufen).

**Quer zu beiden:**

5. **Kleine Verifizierungs-Vorschau** in der bestehenden Review-Ansicht:
   Sinnabschnitt eines Drückers abspielen, durchsteppen, selbst urteilen
   („passt / passt nicht"). Querformat, bestehende Kamera-Logik. Zweck:
   Max kalibriert die Sinn-Logik selbst, cutter-unabhängig.
6. Läuft v1-A für **jeden** Drücker.

### Bewusst NICHT in v1 (nächste Brocken, nicht verloren)

- **9:16-Zuschnitt, Kameraschnitt *während* des Abspielens nach
  etablierter Folgenschnitt-Logik, Mehrfach-Auswahl, MP4-Rendern der
  Ausgewählten** = Hub-/Render-Brocken (Roadmap #6 / #7).
- **KI-gesteuerter Kamerawechsel** (Track-2-Regisseur) = eigener
  Roadmap-Schritt. Die Transkriptions-Grundschicht wird *wiederverwendbar*
  gebaut, damit sie ihn später mitfüttern kann — aber er wird hier nicht
  gebaut.
- **„Nur für ausgewählte Drücker rechnen"**-Sparen = kommt mit dem Hub,
  sobald es dort ein Auswahl-Signal gibt, das PeakCut sieht. Heute gibt
  es keins (Auswahl passiert nachgelagert bei Matze/Cutter, außerhalb).
- Matzes Titel als Eingabe.

---

## 3. Architektur — zwei Stufen + Vorschau

Jeder Baustein hat eine klare Aufgabe, eine definierte Schnittstelle und
ist einzeln testbar.

> **Architektur-Prinzip (warum zwei Stufen):** PeakCut wird **nicht**
> durch „Maschine maximal auslasten" schnell/robust, sondern durch
> *Klugheit darüber, wann und ob Arbeit überhaupt getan wird*. Konkret:
> (1) das Langsamste (Whisper) so früh wie möglich starten — *ob* das
> die produktionskritische Analyse spürbar bremst, wird **gemessen,
> nicht angenommen** (Mess-Gate, §6/§7); (2) das Transkript
> **speichern** → nie zweimal abtippen, derselbe Text füttert später
> den Track-2-Regisseur;
> (3) eine Tempo-Schraube (Whisper-Modellgröße) statt roher Parallelität.
> **Bewusst NICHT weiter zerstückeln/parallelisieren** — die einzige
> sinnvolle Naht ist Stufe A (Transkription, vorne & allein) vs.
> Stufe B (Rest, zusammen). Mehr Gleichzeitigkeit = mehr Stellen, an
> denen der historisch fragile Qt-/Worker-Bereich kracht.

### Stufe A · Baustein 1 — Transkription (`core/transcription.py`, neu)

- **Aufgabe:** Audio (die Mix-/Referenzspur, auf der auch die Drücker
  erkannt werden) → Liste zeitgestempelter Wörter/Segmente
  (`start_ms`, `end_ms`, `text`), Sprache fest Deutsch,
  **wort-genaue Zeitstempel**.
- **Wann:** **provisorischer Default = parallel zur Analyse**
  (Max-Instinkt; das Workflow-Wissen zeigt: es gibt vor dem Export eh
  kein freies Fenster — Screenshots dominieren die Zeit nach der
  Analyse, Review ist kurz). Eigener entkoppelter Hintergrund-Job,
  **Analyse hat OS-Vorrang, Whisper niedrigste Priorität**, nicht auf
  dem Analyse-Kritikpfad. **Harte Regel: der Keyboardstellen-/Analyse-
  Weg wartet NIE auf Whisper.** Der *finale* Default wird **gemessen**
  (Mess-Gate, §6): bremst paralleles Whisper die Analyse real spürbar
  → Default kippt auf „nach der Analyse". Einstellbare Schraube (§7).
- **Ergebnis wird gespeichert (verifiziertes Muster):** das Transkript
  wird als **referenzierte Beidatei `.peakcut/transcript.json`**
  abgelegt — exakt analog `.peakcut/speaker_activity.csv`
  (`project_archive.py`: `ARCHIVE_DIR`/`_CSV_NAME`/`_CSV_REF`, gegen
  echten Code verifiziert). `project.json` hält nur einen Referenzblock
  (Pfad + `engine`/`model`/`language`/relativer `audio_path`), **nicht**
  das Transkript inline. Cache/Arbeitsprodukt, **kein Export**. Fehlt/
  kaputt → neu transkribieren oder Smart überspringen, **Normalflow
  nie crashen**. Projekt erneut geöffnet → Transkript da, kein erneutes
  Abtippen. Stufe B konsumiert nur dieses gespeicherte Transkript.
- **Engine:** lokales Whisper, Apple-Silicon-Variante (konkrete Lib =
  Plan-Entscheidung mit Carl; Kandidaten: `mlx-whisper` /
  `faster-whisper`). Läuft offline, kostenlos, Gast-Audio bleibt auf
  dem Mac.
- **Schnittstelle:** Engine hinter einer **injizierbaren** Funktion/
  einem Protocol (gleiches Muster wie die `AnalysisWorker`-Factories aus
  HC-2 und die `FolgenschnittLooseningStrategy` aus Stufe 2). In der
  Testsuite ein Stub; echtes Whisper nur im Hand-Prüfskript.
- **Lebenszyklus:** echt abbrechbar im **HC-2-Stil (`request_stop()`)** —
  kein blindes `wait()`. App-Schließen während laufender Transkription
  darf weder hängen noch unkontrolliert abreißen (langer Job, genau der
  HC-2-Fall).
- **Abhängigkeiten:** ffmpeg (vorhanden), Whisper-Lib (neu, in
  `requirements.txt`). Python 3.11 (Produktteil, gepinnt).
- **Wiederverwendbarkeit:** eigenständig, ohne Clip-Logik — füttert
  später auch den Track-2-Regisseur.

### Stufe B (Konsument, nach dem Export-Handoff)

Stufe B liest **ausschließlich das gespeicherte Transkript** aus Stufe A.
Ist es bei Stufe-B-Start noch nicht fertig, **wartet Stufe B kurz oder
fällt zurück** — der Keyboardstellen-/Export-Weg wartet trotzdem nie
(der ist zu diesem Zeitpunkt längst fertig & übergeben, s. §4).

### Stufe B · Baustein 2 — Deterministischer Vorbau (`core/clip_boundary/scaffold.py`, neu)

- **Aufgabe:** pro Drücker (Peak)
  1. Suchfenster spannen: **Peak −3 min / +60 s** (provisorisch,
     in `config.json` einstellbar — s. §7).
  2. Innerhalb des Fensters die **natürlichen Schnittkanten** sammeln:
     Satzenden (aus Transkript-Interpunktion/Wortlücken),
     Sprecherwechsel + Sprechpausen aus der **vorhandenen**
     `speaker_activity`/`build_pause_ranges`-Infrastruktur (aus Stufe-2
     `folgenschnitt_loosening`).
  3. Einen kompakten, strukturierten Text-Ausschnitt erzeugen:
     Transkript mit Zeitstempeln, **Drücker-Position klar markiert**,
     Liste der Snap-Kandidaten.
- **Voll deterministisch** → ohne jedes Modell unit-testbar.
- **Schnittstelle:** reine Funktion `build_scaffold(peak, transcript,
  speaker_activity, config) -> Scaffold`.

### Baustein 3 — Semantischer Entscheider + Plausibilitätsbremse (`core/clip_boundary/decider.py`, neu)

- **Aufgabe:** Scaffold → `(start_ms, end_ms, reason, confidence)`.
- **Entscheider:** Claude (Anthropic API, Max' Key). Auftrag: kleinste
  zusammenhängende Strecke finden, die eine **eigenständige kleine
  Geschichte** mit dem markierten Moment ist; Start dort, wo der Anlauf
  beginnt; Ende dort, wo der Gedanke landet (inkl. Paukenschlag *nach*
  dem Drücker, falls vorhanden); **nie hart am Drücker**. Start/Ende auf
  eine der mitgelieferten natürlichen Kanten gesnappt. Ein-Satz-Grund +
  Konfidenz 0..1. Niedrige Temperatur, strukturierte Ausgabe.
- **Hinter austauschbarer Schnittstelle** (`BoundaryDecider` Protocol —
  Muster wie `FolgenschnittLooseningStrategy`). In der Testsuite ein
  **deterministischer Stub** — **kein echter API-Aufruf in pytest**
  (CI bleibt offline & grün). Echtes Claude nur im Hand-Prüfskript.
- **Plausibilitätsbremse** (deterministisch, dahinter — exakt das von
  Max zweimal abgenommene Muster aus Stufe 2 / `analyze_fcpxml.py`):
  Ergebnis verworfen, wenn
  - Strecke länger als das Suchfenster bzw. > sinnvolles Max
    (provisorisch, s. §7),
  - kürzer als sinnvolles Min,
  - leer / Ende ≤ Drücker ohne Inhalt,
  - Konfidenz unter Schwelle.
  → **Sicherer Rückfall**: konservativ weiteres Fenster (mindestens das
  heutige ±15 s, eher etwas weiter), Kandidat als **unsicher** markiert
  (niedriger `score`). **Nie schlechter als heute.**

### Verifizierungs-Vorschau (Erweiterung der bestehenden Review-Ansicht)

- **Aufgabe:** Max steppt durch die Drücker und sieht den **smarten
  Sinnabschnitt** als abgespieltes Video, urteilt selbst.
- **Umsetzung:** nutzt die **vorhandene** Review-Vorschau
  (`gui/video_preview_peak.py` `play_from(in_ms, out_ms)`,
  Peak-Navigation). Delta: die Vorschau bekommt
  `ClipCandidate.boundary` statt des ±15-s-Fensters; sichtbar wird
  Grund + Konfidenz; Hinweis bei Bremsen-Rückfall.
- **Querformat, bestehende Kamera-Auswahl-Logik. KEIN** 9:16, **KEIN**
  Rendern, **KEINE** Mehrfach-Auswahl, **KEIN** Auswahl-zum-Export-Schritt.
- **Achtung Risiko:** das ist die historisch fragilste Stelle
  (Qt/QMediaPlayer-Vorschau, Crash-Historie, in HC-2 gehärtet). „Klein"
  heißt real klein, aber nicht gratis — gleiche 4-Augen-/TDD-Disziplin,
  Lifecycle-Tests wie HC-2.

---

## 4. Datenfluss & Integration

**Harte Reihenfolge:**

1. **Analyse-Start** → Stufe A (Transkription) wird als eigener,
   entkoppelter Hintergrund-Job angestoßen — parallel zur Analyse,
   niedrige Priorität, **nicht auf dem Analyse-Kritikpfad**.
2. **Keyboardstellen-/Folgenschnitt-Export** läuft & wird vollständig
   fertig (unverändert, gleiche Geschwindigkeit wie heute) → `.peakcut_done`
   geschrieben → `ExportWorker.finished(exported)` → **CheckIn-Handoff
   darf übernehmen**. Von Whisper **nicht** ausgebremst.
3. **Stufe B** startet **erst nach** diesem Export-Handoff, aus dem
   Erfolgspfad (`ReviewPage._on_export_done`, als *letzte* Aktion nach
   `session_changed.emit()`; **nie** aus `_on_export_error`), als eigener
   entkoppelter Worker. Liest **nur das gespeicherte Transkript** aus
   Stufe A; ist es noch nicht fertig → Stufe B **wartet kurz oder fällt
   zurück**. Der Keyboardstellen-/Export-Weg wartet **nie** (zu diesem
   Zeitpunkt längst fertig & übergeben).
4. Stufe B füllt den bestehenden **`ClipCandidate`** (Roadmap #2):
   `boundary` = smarter Sinnabschnitt (statt rohem Bootstrap-Fenster),
   `transcript_excerpt` = Text der Strecke, `reason` = Ein-Satz-Grund,
   `score` = Konfidenz. Status bleibt `proposed`.

- **Persistenz Transkript (verifiziert):** referenzierte Beidatei
  `.peakcut/transcript.json` analog `.peakcut/speaker_activity.csv`
  (`project_archive.py` macht das Sidecar-Muster bereits genau so —
  `ARCHIVE_DIR`/`_CSV_NAME`/`_CSV_REF`, relativierte Pfade, gegen Code
  verifiziert). `project.json` bekommt nur einen Referenzblock, **nicht**
  das Transkript inline → `project.json` bleibt schlank, große wachsende
  Daten daneben. Transkript = Cache/Arbeitsprodukt, kein Export; fehlt/
  kaputt → neu/überspringen, Normalflow nie crashen. Bestehende
  `.peakcut`-/Keyboardstellen-Last unberührt.
- **Zusätzliche Ausgabe-Artefakte** im Export-Ordner, klar getrennt
  benannt: `Sinnabschnitte - {Gast}.xml` und `.txt`, für **alle**
  Drücker. Eigener Exporter, **außerhalb** `_build_exporters` und
  **nicht** Teil der `exported`-Liste / des `.peakcut_done`-Triggers.
- **Schalter** in `config.json` (z.B. `smart_boundary_enabled`),
  **Default AN**. Nur als Notbremse: aus → der gesamte neue Pfad
  (Stufe A *und* B) läuft gar nicht (kein Whisper, kein Claude),
  PeakCut verhält sich exakt wie heute.

### Harte Leitplanke (regression-gesichert, kein Versprechen)

Die vom Cutter gelobten Keyboardstellen-Dateien (XML/MP3/TXT) werden
**nicht angefasst** und bleiben **byte-identisch**. Beweis: ein
Regressionstest prüft maschinell Keyboardstellen-Ausgabe mit *und* ohne
aktivierte Smart-Pipeline byte-für-byte gleich (wie Roadmap #2 / HC-4).
Gleiche Philosophie wie die Folgenschnitt-Leitplanke: der wichtige
Export bricht NIE wegen #3.

---

## 5. Fehlerbehandlung

Jeder Fehlerfall: **nie schlechter als heute, blockiert nie Analyse/Export.**

- Whisper fehlt/scheitert → kein Transkript → smarte Grenze entfällt für
  den Drücker, `ClipCandidate` behält das sichere heutige Fenster,
  Kandidat markiert. App/Analyse laufen normal weiter.
- Claude offline/Fehler/Timeout → Plausibilitätsbremse-Pfad → sicherer
  Rückfall, niedriger `score`. Kein Block.
- Schalter aus → kompletter Pfad (Stufe A *und* B) inaktiv, Verhalten
  = heute.
- **Stufe A entkoppelt & prioritäts-geschützt:** eigener Job, Analyse
  hat OS-Vorrang, Whisper niedrigste Priorität, nicht auf dem Analyse-
  Kritikpfad. Ob paralleles Whisper die Analyse real bremst, ist
  **gemessen, nicht angenommen** (Mess-Gate, §6); bremst es → Default
  „nach der Analyse". Keyboardstellen-Weg wartet so oder so nie.
- **Schwächere Maschine degradiert sanft** (PeakCut ist Produkt auch für
  andere, nicht nur Max' starker Mac): langsameres oder kein Transkript
  → Stufe B fällt zurück, Keyboardstellen-Ausgabe unberührt.
- Transkription, die **früh** scheitert, ist sogar sicherer: lange vor
  dem Export bekannt, Stufe B fällt sauber zurück.

---

## 6. Teststrategie

- **Baustein 1:** injizierbare Engine, Stub + winziger echter
  Audio-Schnipsel als Fixture.
- **Baustein 2:** voll deterministisch — Fenster-Mathematik,
  Snap-Kanten-Extraktion, Drücker-Markierung, Randfälle (Fenster ragt
  über Folgenanfang/-ende, leeres Fenster).
- **Baustein 3:** deterministischer Stub-Entscheider in der Suite;
  Plausibilitätsbremse mit absichtlich kaputten Antworten getestet
  (zu lang / zu kurz / leer / Ende ≤ Drücker / niedrige Konfidenz);
  Rückfall == sicheres Fenster bewiesen.
- **Identitäts-/Regressionstest:** Keyboardstellen-Ausgabe byte-identisch
  mit/ohne Smart-Pipeline (Regression-Lock wie Roadmap #2).
- **Verifizierungs-Vorschau:** Lifecycle-Tests wie HC-2
  (`test_video_preview_lifecycle.py`-Stil), kein echter Mediendecode in
  der Suite.
- **CI bleibt offline & grün:** kein echtes Whisper, kein echtes Claude
  in pytest.
- **Hand-Prüfskript** `scripts/verify_smart_boundary_real.py` (Muster
  wie `verify_hc3_sync_real.py` / `verify_folgenschnitt_recut.py`):
  echtes Whisper + echtes Claude an echter markierter Folge (Max'
  Hartmut-Rosa-Material). Prüft: enthalten die gewählten Abschnitte die
  bekannten guten Geschichten, stoßen sie nie an die Fenster-Decke
  (Zeichen, dass das Fenster zu eng war), wird ein bekannt guter Anfang
  je abgeschnitten. **Grundlage für die Kalibrierung der provisorischen
  Zahlen.**
- **Mess-Gate Transkriptions-Start (Teil desselben Skripts):** misst
  die Analyse-Wanduhr-Laufzeit **mit** vs. **ohne** parallel laufendes
  Whisper an echter HR-Folge. Spürbare Bremse → finaler Default kippt
  von „parallel zur Analyse" auf „nach der Analyse". Entscheidet die
  Schraube aus §7 mit Daten statt Annahme.

---

## 7. Provisorische Zahlen (werden kalibriert)

Gleiche Disziplin wie Stufe-2-v1 und FCPXML-Bremse — vernünftiger
Startwert, dann an echten Folgen justiert:

| Parameter | Startwert | Begründung |
|---|---|---|
| Suchfenster zurück | ~3 min | deckt „kurz davor" + „ganzer Teil war stark" |
| Suchfenster vor | ~60 s | Paukenschlag + Landen, ohne nächstes Thema |
| Max-Streckenlänge (Bremse) | ~3 min | > Fenster bzw. unsinnig → Rückfall |
| Min-Streckenlänge (Bremse) | ~10–15 s | darunter keine Geschichte |
| Konfidenz-Schwelle (Bremse) | ~0,5 | darunter → sicherer Rückfall |
| Transkriptions-Start | parallel zur Analyse + Prioritätsschutz | **Mess-Gate** (Analyse-Laufzeit mit/ohne paralleles Whisper, echte HR-Folge) entscheidet finalen Default; kippt auf „nach Analyse" bei spürbarer Bremse |
| Whisper-Modellgröße | schnelles Apple-Silicon-Modell | *die* Tempo-Schraube; Genauigkeit↔Tempo |

Alle in `config.json`. Kalibrierung über das Hand-Prüfskript (§6).

---

## 8. Dateien (Orientierung für den Carl-Plan)

- **Neu:** `core/transcription.py`, `core/clip_boundary/scaffold.py`,
  `core/clip_boundary/decider.py`, ein Sinnabschnitte-Exporter (neben
  `core/exporters.py`), `scripts/verify_smart_boundary_real.py`.
- **Geändert:** `core/session.py` (Stufe-B-Pipeline füllt
  `ClipCandidate`), `core/project_archive.py` (Transkript als additive
  optionale Sektion speichern/tolerant laden), Stufe-A-Anstoß nahe
  Analyse-Start als entkoppelter Worker (`gui/workers.py` /
  `gui/main_window.py` — exakter Ort = Carl-Plan), Stufe-B-Anstoß nach
  Export-Handoff (`gui/review_page.py` `_on_export_done`, Erfolgspfad),
  `gui/video_preview_peak.py` (Vorschau bekommt `ClipCandidate.boundary`
  + Grund/Konfidenz), `config.py`/`config.json` (Schalter + Parameter),
  `requirements.txt` (Whisper-Lib). `ExportWorker` bleibt semantisch
  unverändert (kein Smart darin).
- **Unberührt:** Keyboardstellen-Exporter, `_build_exporters`/
  `exported`/`.peakcut_done`-Pfad, Folgenschnitt-Leitplanke. Exakte
  Schema-Mechanik der neuen Transkript-Sektion = Carl-Plan, Claude
  verifiziert gegen `project_archive`.

Exakte Pfade/Signaturen legt der Carl-Plan fest; Claude verifiziert sie
gegen den echten Code, bevor gebaut wird.

---

## 9. Ablauf

Diese Spec → **Carl** schreibt den Umsetzungsplan → **Claude**
verifiziert den Plan gegen den echten Code und baut TDD Schritt für
Schritt mit Gates → **Max** entscheidet den Merge. Bewährte
4-Augen-Methode (wie HC-2/3/4, Roadmap #2).
