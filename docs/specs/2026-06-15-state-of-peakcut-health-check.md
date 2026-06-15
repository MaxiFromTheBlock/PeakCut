# State of PeakCut — Fundament-Gesundheitscheck (2026-06-15)

> **Was das ist:** Ein tiefer, beweisbasierter Gesundheitscheck der PeakCut-Codebasis,
> abgeglichen mit der Roadmap. Ziel (Max): *„Wie tragfähig ist das Fundament wirklich,
> und was sollten wir JETZT festzurren, um danach freier ausbauen zu können — statt
> ständig ein weiteres Stockwerk auf etwas Wackliges zu setzen?"*
>
> **Wie es entstanden ist:** Mehr-Agenten-Analyse („ultracode"). 9 Spezial-Agenten haben
> parallel den *echten* Code gelesen (nicht die Doku-Selbstauskunft), jeder auf eine
> Dimension fokussiert. Jeder schwere Befund wurde von einem skeptischen Gegen-Agenten am
> Code gegengeprüft. Zwei unabhängige Synthese-Agenten (risk-first + roadmap-first) haben
> die Reihenfolge abgeleitet — und kamen zum **selben Ergebnis**. Insgesamt 27 Agenten,
> ~2,9 Mio Token, 31 Min, 420 Werkzeug-Aufrufe. 593 Tests laufen verifiziert grün (59s).

---

## Roadmap-Legende (für dieses Dokument)

| Kürzel | Ziel |
|---|---|
| **G1** | Internes Timeline-Modell statt handgeschriebener XML-Strings (mehrere Exporter; löst Resolve-Relink an der Wurzel) |
| **G2** | Projekt-/Session-Persistenz + **Undo** (V3-Voraussetzung) |
| **G3** | NAS-Hybrid: `.peakcut` wird die EINE Wahrheit; Headless-Worker `peakcut analyze/export <ordner>` lokal/im Synology-Container; Web-Hub für Status |
| **G4** | Profile als Datenmodell (Production-Profil + Brand/Social-Profil) |
| **G5** | ClipCandidate-Negativdaten-Burggraben → Prompt-Tuning (#70) |
| **G6** | Hub / Projekt-öffnen-UI (.peakcut öffnen, Zuordnung editieren, Archiv reset) |
| **G7** | Headless/CLI-Worker abgespalten von der PyQt-GUI |

In-Flight-Slices: **Slice B** Multi-Track-XML (code-fertig), **#76** Wiedergabe-UX,
**Slice A** Cross-Talk-Totale, **#77** Import-Refactor, **#70** Prompt-Tuning.

---

## TL;DR — Gesamturteil: **mostly-solid**

**Das Fundament ist überraschend sauber gebaut und trägt die Roadmap im Kern. Nichts
blockiert das Weiterbauen heute.** Die kritischen Lücken sind klein und billig — sie sind
eher *„noch nicht gelegt"* als *„falsch gebaut"*. Das ist die seltene, gute Sorte
Health-Check-Ergebnis: kein Abriss nötig, nur fünf Nähte festzurren, bevor die nächsten
Stockwerke drauf gehen.

**Was echt solide ist** (am Code verifiziert, nicht nur behauptet):
- `core/` ist nachweislich **Qt-frei** — die Voraussetzung für den Headless-Worker (G7) und
  den NAS-Container (G3) ist bereits gelegt und durch Tests geschützt.
- Der Subprozess-Lebenszyklus (Analyse/Transkription) ist **gehärtet** (Watchdog, sauberer
  Abbruch, kein Hängen).
- Die XML-Exporte sind mit **byte-identischen Prüfsummen verriegelt** — der cutter-gelobte
  Keyboardstellen-Export kann nicht versehentlich kaputtgehen. Das ist kein Theater.
- Die KI-Pipeline hat eine **unzerstörbare Plausibilitätsbremse** (das Modell kann nie einen
  strukturell kaputten Schnitt durchdrücken) und Key-Sicherheit nach deiner Doppelgänger-Lektion.

**Was vor weiterem Bauen festgezurrt gehört** (5 Nähte, 3× klein / 2× mittel):
die Akte gegen Selbstzertrümmerung absichern, ein Versions-Regime einziehen, die
Export-Steuerung aus der GUI in den Kern heben, die Klassifizierung auf eine Wahrheit
zusammenführen, und einen Riegel gegen vergiftete Lerndaten setzen.

**Wichtigste Einzel-Erkenntnis:** Der teuerste spätere Umbau (G1, internes Timeline-Modell)
ist **kein Neubau** — das Fundament steht zu ~80% (saubere, eingefrorene Logik-Schicht).
Es ist ein Tausch der Schreibschicht. Das ist eine sehr gute Nachricht.

---

## 1. Was schon solide ist — und geschützt gehört

Dieser Teil ist wichtig: ein Health-Check, der nur Probleme listet, verführt zum Kaputt-
Optimieren von Dingen, die richtig sind. **Folgendes nicht anfassen / nicht „vereinfachen" /
nicht over-engineeren:**

1. **`core/` ist Qt-frei.** Kein einziger PyQt-Import im Kern; die Session nutzt eine eigene
   Callback-Klasse statt Qt-Signale. → Das ist die Grundvoraussetzung für G7/G3. Nie ein
   schnelles Qt-Import in `core` einschmuggeln.
2. **Saubere Config-Trennung.** Der Kern kennt die globale Einstellungs-Datei nicht, er liest
   nur über ein injiziertes Dict. → Genau der Datenvertrag, den G4 (Profile) braucht.
3. **`analysis_process.py` ist bereits ein Headless-Worker-Prototyp** (Ordner-Daten rein,
   Ergebnis raus, kein Qt). → Die fertige Blaupause für den noch fehlenden Export-Pfad.
4. **Gehärteter Subprozess-Lebenszyklus** (HC-2): geschütztes Handle, sauberer Abbruch,
   Eskalation terminate→kill, spawn-Kontext gegen die macOS-Crash-Falle, Watchdog. → Trägt G7.
5. **Byte-identische XML-Prüfsummen** + ein Test, der den Test selbst vor Verflakerung
   schützt. → Gelebtes „Vertrauen durch Tooling". Bei der G1-Migration als Regressions-Gate
   behalten.
6. **Reine, eingefrorene Entscheidungs-/Layout-Logik** (decisions/loosening/multitrack_layout):
   deterministisch, lückenlos-by-construction. → **Das IST schon ein primitives
   Timeline-Modell** und macht G1 zum Tausch der Schreibschicht statt eines Neubaus.
7. **Der Folgenschnitt-Exporter löst die Video/Audio-Drift bereits korrekt** (gemeinsames
   Record-Grid). → Das Muster, das G1 überall erzwingen soll. Verallgemeinern, nicht anfassen.
8. **`audio_routing.is_mix_track`** als token-bewusster, pin-geschützter Klassifizierer-Hub.
   → Die anderen Insel-Heuristiken HIER hineinziehen, nicht den Hub aufblasen.
9. **FFT-Sync-Pipeline** (Teil-Lesen, lazy Referenz, Confidence-Fallback, framegenau gegen
   echte XML verifiziert). → Solides Herzstück des Assistant-Editor-Versprechens.
10. **KI-Sicherheitsnetz**: deterministische Bremse, Drei-Kategorien-Ergebnis
    (OK / DECIDER_VERWORFEN / INFRA_FEHLT), Key-Sicherheit ohne Key-Leck in Fehlertexten,
    injizierbare Provider-Nähte (Cloud-Tier-Vorbereitung). → Zaha-Hadid-Niveau. Nicht wegrefactoren.
11. **Disziplinierte Fehlerbehandlung**: keine einzige `bare except` in `src`; die breiten
    Stellen sind kommentiert und leiten Fehler über kontrollierte Kanäle sichtbar weiter.
12. **Atomarer `transcript.json`-Schreiber** existiert bereits — das Vorbild für den
    `project.json`-Fix unten.

---

## 2. JETZT festzurren — die 5 Nähte (vor weiterem Bauen)

Beide Synthese-Agenten priorisierten unabhängig dieselben fünf. Reihenfolge = Hebelwirkung.

### 2.1 `project.json` atomar schreiben · Aufwand: **klein (S)** · `DATA-1`
**Problem:** Die zentrale Akte (`project.json`) wird mit einem simplen „Datei öffnen + reinschreiben"
gespeichert. Bricht das mitten ab (Crash, Kill, Stromausfall, volle Platte), bleibt eine
zerstückelte, unlesbare Datei zurück — der ganze gespeicherte Lauf (Zuordnung, Kandidaten,
Ignoriert-Status) ist weg. **Das atomare Muster (erst in temporäre Datei, dann umbenennen)
liegt im Schwester-Modul direkt nebenan und wird für die wichtigere Datei nicht genutzt.**
Autosave feuert nach Analyse, Zuordnung, jedem Ignorieren, jedem KI-Lauf und beim Schließen
— viele Abbruch-Gelegenheiten.
**Warum jetzt:** Auf dem NAS (langsamer/unzuverlässiger I/O — genau wohin G3 zeigt) steigt das
Risiko deutlich. Undo (G2) ist wertlos, wenn die Wahrheit verdampfen kann. „Vertrauen durch
Tooling" verbrennt beim ersten Datenverlust.
**Ermöglicht:** G2, G3. · **Beleg:** `project_archive.py:246-248` vs. `transcript_archive.py:82-85`.

### 2.2 R2-Ausricht-Riegel: vergiftete Lerndaten verhindern · Aufwand: **klein (S)** · `KI-2`
**Problem:** Wenn ein Transkript zeitlich falsch ausgerichtet ist (z.B. Descript-Import mit
Versatz), erzeugt die KI-Pipeline **trotzdem** Clip-Vorschläge — mit Confidence-Score, die
gespeichert werden. Der vorhandene Schutz ist nur ein Status-Hinweis in der Oberfläche, kein
echter Riegel im Datenpfad. (Die Worker-Meldung „werden NICHT still berechnet" ist faktisch
falsch — sie werden berechnet und autogespeichert.) Die nötigen Daten (Drift) liegen bereits vor.
**Warum jetzt:** Diese Vorschläge landen in der `peak_decisions`-Sammlung — **genau dem
nicht-kopierbaren Wettbewerbsvorteil (G5)**. Vergiftete Daten sind nicht nachträglich
sauberzumachen; späteres #70/ML lernt auf falschen Daten.
**Ermöglicht:** G5, #70. · **Beleg:** `clip_boundary/pipeline.py:68-162`, `config.py:38-40` (fordert das selbst), `review_page.py:629-639`.

### 2.3 Versions-Regime für die `.peakcut`-Akte · Aufwand: **mittel (M)** · `DATA-2`
**Problem:** Die Schema-Version wird gespeichert, aber **nirgends ausgewertet** — kein
Abzweig, keine Migrationskarte, keine Ablehnung. Ein älterer Client lädt eine neuere Akte
„so gut es geht" und schneidet beim nächsten Speichern neuere Felder still weg.
**Warum jetzt:** Heute (ein Mac, eine Code-Version) harmlos. Genau diese zwei Annahmen brechen
im G3-Multi-Mac-Szenario. Billig einzuziehen, solange erst ein Schema-Stand existiert — teuer,
wenn schon v3-Akten auf dem NAS verteilt sind.
**Ermöglicht:** G3, G4, G2. · **Beleg:** `project_archive.py:144, 195`.

### 2.4 Export-Steuerung aus der GUI in den Kern heben · Aufwand: **mittel (M)** · `ARCH-1`
**Problem:** Der eigentliche Produktkern — *„Ordner rein → fertiges Paket raus"* — lebt in
einem GUI-Thread (`ExportWorker`) und in `review_page.py`, **nicht im Kern**. Der Analyse-Teil
ist schon sauber headless; der Export-Teil hat kein Gegenstück. Die schützende Folgenschnitt-
Leitplanke (die den cutter-gelobten Keyboardstellen-Export sichert) existiert NUR im GUI-Thread.
**Warnsignal:** Das Smoke-Hilfsskript für Slice B re-implementiert den Export bereits separat
*ohne* die Leitplanke. (Das Skript ist ein Wegwerf-Testhelfer, kein Produktpfad — aber es zeigt
genau die Driftgefahr: zwei Export-Wege, die auseinanderlaufen.)
**Warum jetzt:** G7 (Headless) und G3 (Container) müssten diese Steuerung sonst neu bauen oder
aus Qt entwirren. Je länger der zweite Pfad existiert, desto weiter driften GUI- und CLI-Export.
**Ermöglicht:** G7, G3, G6. · **Beleg:** `workers.py:295-344`, `scripts/smoke_multitrack_export.py:50`.
**Lösung:** `core/export_pipeline.py` mit `run_export(session)` — analog zum schon-headless `analysis_process.py`.

### 2.5 Klassifizierung auf eine Wahrheit zusammenführen (grep-Pass vor #77) · Aufwand: **klein (S)** · `AUD-1`/`CQ-2`
**Problem:** Die Frage *„ist diese Datei Mix / Keyboard / echtes Mikro?"* wird an **mindestens
4 Stellen mit 3 verschiedenen Algorithmen** beantwortet. Live belegt: `mixer_recording.wav`
wird vom korrekten Hub als Nicht-Mix erkannt, von einer Insel fälschlich als Mix. **Das ist
exakt deine eigene Memory-Regel „Heuristik-Inseln vor dem Slice greppen".**
**Wichtige Nuance:** Eine der Inseln (`guest_name.py`) ist byte-identisch verriegelt (der
Gastname steckt im XML-Dateinamen) — **diese eine Insel gehört bewusst erst IN #77 mit
Schema-Migration, nicht jetzt umgestellt.** Die anderen drei jetzt.
**Warum jetzt:** Sonst erbt der #77-Import-Refactor 4 Stellen statt einer, und eine vierte
Insel taucht erst im Schluss-Cross-Review als P3 auf. G4 und G3 bauen darauf, dass die
Klassifikation EINE Regel ist.
**Ermöglicht:** #77, G4, G3, G7, Slice A, Slice B. · **Beleg:** `audio_routing.py:55-67` (korrekt) vs. `speaker_activity.py:49-52`, `main_window.py:232`, `guest_name.py:12`.

---

## 3. BALD — vor dem jeweiligen Slice

Diese sitzen jeweils direkt **vor** einem geplanten Slice und sollten dessen Teil sein:

| Vorarbeit | Aufwand | Sitzt vor | Befund |
|---|---|---|---|
| **Wiedergabe-Architektur entscheiden** (zwei unsynchronisierte Engines → eine Uhr) | L | **#76** Wiedergabe-UX | `CONC-1` |
| **Charakterisierungs-Test für die Datei-Kategorisierung** (`_categorize_files` hat 0 Tests) | S | **#77** Import-Refactor | `TEST-2` |
| **Echte QThread-Integrationstests** (kein Test startet je einen echten Thread) | L | Threading-Härtung / **G7** | `TEST-1` |
| **Prompt injizierbar machen** + Beispiel-Datenmodell (A/B-Harness kann sonst nicht andocken) | M | **#70** Prompt-Tuning | `KI-1`/`KI-7` |
| **Python-Pin maschinell erzwingen** (.python-version + CI exakt + Entry-Guard) | S | G3/G7 | `DEP-3`/`DEP-1` |
| **Worker-Handle-Disziplin** (Neustart überschreibt alten Thread ohne Abbau; Vorbild existiert) | M | G6/G3/G7 | `CONC-2`/`CONC-3` |

**Hintergrund Wiedergabe (#76):** Ton läuft über eine Engine, Bild über eine zweite (stumm
geschaltet), ohne gemeinsame Uhr. Das ist die **Wurzel von #76** — der KI-Vorschlag spielt
stumm/unsynchron. Vor dem #76-Bau muss die Wiedergabe zusammengeführt werden, sonst baut man
auf zwei Uhren weiter. Beim Bau prüfen, ob die ohnehin vorhandene Qt-Audio-Schicht die alte,
unmaintainte Ton-Bibliothek (`simpleaudio`, `DEP-4`) gleich mit ablöst.

---

## 4. SPÄTER — die großen, roadmap-gekoppelten Investitionen

Lohnen erst, **nachdem** die 5 Nähte sitzen. Jede ist groß, betrifft aber gezielt ein Ziel:

- **G1 — Internes Timeline-Modell + EIN Serializer** (L). Drei Exporter schreiben das XML-Gerüst
  je selbst (dreifache Kopie). Es gibt eine echte Video/Audio-Drift-Bug-Klasse bei negativem
  Kamera-Offset (`EXP-1`), und der framegenaue Sync-Offset wird sofort auf ganze Frames
  gerundet (bis ~40ms Verlust, `AUD-2`). **Das ist kein Aufräumen, sondern Korrektheit** — und
  kein Neubau, weil die Logik-Schicht zu 80% schon ein Timeline-Modell ist. Löst EXP-1/EXP-2/AUD-2/EXP-4 in einem Zug.
- **G5-Zulauf — produktiver Schreibpfad für ClipCandidate** (M). Die Statusmaschine
  (vorgeschlagen→ausgewählt→produziert→veröffentlicht) ist **fertig gebaut, aber der einzige
  produktive Aufruf setzt nur „verworfen".** Das Reservoir des Burggrabens steht, der Zulauf
  fehlt. **WANN welcher Status gesetzt wird = deine redaktionelle Entscheidung** (`DATA-5`).
  Risiko bei Aufschub: jede produzierte Folge ohne Status-Erfassung ist verbrannte Lerndatenmenge.
- **G4 — Production-Profil-Datenvertrag** (M). Helligkeit lebt flüchtig im Widget, das aktive
  LUT global statt pro Projekt, die Mix-Datei strukturell als anonyme Mic-Spur. Diese Felder in
  das `.peakcut`-Schema ziehen (`ARCH-3`/`DATA-4`).
- **G3 — Plattform-Gabel härten** (M). macOS-Kopplungen (TTS via `say`, Keychain) und die
  Whisper-Engine sind Apple-gebunden → der Synology-Container braucht Adapter dahinter
  (`ARCH-6`/`KI-6`). Plus: der zentrale ffmpeg-Pfad gilt nur für die Hälfte der Aufrufe (`DEP-2`).
- **Doku-Entrümpelung + Logger-Konsistenz** (M). Das Dependency-Diagramm in CLAUDE.md nennt
  gelöschte Module; ein Logger umgeht das Datei-Log (`ARCH-7`/`CQ-3`/`CQ-6`).

**Bewusst NICHT vorgezogen:** Die ~60 Zeilen duplizierter Worker-Lebenszyklus-Code (`CQ-1`/`CONC-5`)
sind durch Tests gepinnt und kein aktiver Blocker — gehören in den G7-Slice, wo der Lebenszyklus
ohnehin aus der GUI gehoben wird, statt jetzt isoliert refactoriert.

---

## 5. Dimensions-Scorecard

| Dimension | Urteil | Kernsatz |
|---|---|---|
| Architektur & Schichtung | **mostly-solid** | Schichtung real & sauber; Schwäche: Export-Orchestrierung klebt in der GUI. |
| Nebenläufigkeit & Lebenszyklus | **mixed** | Subprozess-Schicht solide; GUI-Qt-Objekt-Disziplin schwach (zwei Wiedergabe-Uhren = Wurzel #76). |
| Export- & Timeline-Kern | **mixed** | Logik-Schicht sauber; Bruch in der dreifach kopierten XML-String-Schreibschicht. |
| Datenmodell & Persistenz | **mostly-solid** | Für einen Mac heute solide; für NAS-Multi-Mac fehlen atomarer Write + Versions-Regime + Sperre. |
| Audio / Sync / Signal | **mostly-solid** | Sync-Kern stark; Klassifizierung an 4 Stellen + Frame-Quantisierung als Bremsen. |
| KI- / Clip-Pipeline | **mostly-solid** | Überraschend reif; aber nicht #70-bereit (Prompt hartcodiert, R2-Riegel fehlt). |
| Test-Sicherheitsnetz | **mostly-solid** | Für `core` echt & teils herausragend; Lücke bei echtem Thread-Cleanup + `_categorize_files`. |
| Abhängigkeiten & Laufzeit | **mostly-solid** | Stabil im Alltag; zwei tickende Uhren (pydub→audioop in 3.13, Python-Pin nicht erzwungen). |
| Code-Qualität & Konsistenz | **mostly-solid** | Fehlerbehandlung vorbildlich; Kosten in Worker-Duplikation + Heuristik-Inseln + God-Object. |

---

## 6. Warum diese Reihenfolge freieres Bauen ermöglicht

Ein Prinzip: **zuerst die billigen Nähte, die gleichzeitig mehrere Ziele entkoppeln; dann die
teuren Modell-Umbauten, die nur ein Ziel betreffen.**

- Der Akte-Block (atomarer Write + Versions-Regime) kommt zuerst, weil er das Fundament *jedes*
  datentragenden Ziels ist (G2 Undo, G3 Multi-Mac, G4 Profil, G5 Burggraben) — mit kleinem/mittlerem
  Aufwand erschlagen, **bevor** irgendwo eine v3-Akte verteilt ist. Danach darf jeder weitere Stock
  die Akte als verlässliche Wahrheit voraussetzen.
- Die Export-Extraktion folgt sofort, weil der Schaden bereits eintritt (zweiter Export-Pfad ohne
  Leitplanke existiert schon).
- Klassifizierer-Merge und R2-Riegel sind die zwei kleinen Riegel **vor** ihren Slices (#77 bzw. #70).
- Erst **danach** lohnen die großen Investitionen: G1 löst gleich vier Befunde in einem Zug, ist aber
  durch die schon vorhandene Logik-Schicht halbiert.

So werden die teilbaren, parallel baubaren Stücke (G1, G5-Zulauf, #76-Wiedergabe) erst freigegeben,
wenn ihr **gemeinsames** Fundament — verlässliche Akte, EIN Export-Einstieg, EINE Klassifikation —
nicht mehr unter ihnen wackelt.

---

## Anhang A — Alle 55 Befunde

Legende: Schweregrad nach Verifikation (`hoch→mittel` = vom Gegen-Agenten herabgestuft, aber
weiterhin echtes Risiko). Alle 16 hoch/kritisch-Befunde wurden gegengeprüft — **keiner war ein
Fehlalarm**. Aufwand: S=klein, M=mittel, L=groß.

### Architektur & Schichtung
- `ARCH-1` **hoch** (S→ Lösung M) — Export-Orchestrierung lebt in der GUI statt im Kern. → §2.4
- `ARCH-2` hoch→mittel — Smart-Boundary-Steuerung als verstecktes Zustands-Maschinchen in ReviewPage (God-Object).
- `ARCH-3` mittel — Render-State (Helligkeit pro Kamera, aktives LUT) lebt außerhalb von Session/Akte. → G4
- `ARCH-4` mittel — Datei-Kategorisierung als Heuristik im MainWindow statt im core-Datenmodell.
- `ARCH-6` mittel — macOS-harte Kopplungen (say-TTS, Keychain) blockieren den Linux/Synology-Headless. → G3
- `ARCH-5` niedrig — globaler Wiedergabe-Singleton-State.
- `ARCH-7` niedrig — Doku-Drift: Dependency-Diagramm nennt nicht-existente Module.

### Nebenläufigkeit & Lebenszyklus
- `CONC-1` **hoch** (L) — zwei unsynchronisierte Wiedergabe-Engines ohne gemeinsame Uhr (Wurzel #76). → §3
- `CONC-2` mittel — wieder-erstellte Worker-Handles überschreiben Vorgänger ohne Stop/Abbau.
- `CONC-3` mittel — QMediaPlayer/QAudioOutput/QVideoSink werden nie heruntergefahren.
- `CONC-4` mittel — Thumbnail-/MicPreview-Worker ohne sauberen Abbruch (blockierender Cleanup).
- `CONC-5` niedrig — Prozess-Lifecycle-Maschine zweifach dupliziert.
- `CONC-6` niedrig — globaler simpleaudio-Singleton ohne Owner.

### Export- & Timeline-Kern
- `EXP-1` hoch→mittel — Keyboardstellen-Exporter driftet Video gegen Audio bei negativem Offset (echte Render-Bug-Klasse, von Pin-1 zementiert). → G1
- `EXP-2` hoch→mittel — dreifach kopiertes XML-Gerüst über drei Exporter. → G1
- `EXP-3` mittel — Sinnabschnitt-Exporter schreibt strukturell ungültigen FCP7-Block.
- `EXP-4` mittel — geteilte Datei-URL erzeugt absolute Pfade (Resolve-Relink-Schmerz, NAS-Bruch).
- `EXP-5` niedrig — asymmetrische Frame-Rundung bei negativen Werten (latente Off-by-one).
- `EXP-6` niedrig — Pin-1 verriegelt auch die Bug-Klasse aus EXP-1 (Garantie ≠ Korrektheit).

### Datenmodell & Persistenz
- `DATA-1` **hoch** (S) — project.json nicht atomar geschrieben → Teil-Schreiben zertrümmert die Akte. → §2.1
- `DATA-2` hoch→mittel — schema_version gespeichert aber nie ausgewertet. → §2.3
- `DATA-3` mittel — keine Datei-Sperre → gleichzeitiger Zugriff zweier Macs ungeschützt. → G3
- `DATA-4` mittel — Mix-Datei strukturell als Mic-Spur → Persistenz friert die Übergangs-Schuld ein. → #77
- `DATA-5` mittel — ClipCandidate-Schreibpfad (selected/produced/published) fehlt produktiv. → G5
- `DATA-6` niedrig — material_root kann zwischen Transcript-Worker und Autosave divergieren.

### Audio / Sync / Signal
- `AUD-1` hoch→mittel — Klassifizierung an 4 Stellen / 3 Algorithmen (Heuristik-Insel). → §2.5
- `AUD-2` hoch→mittel — framegenauer Sync-Offset sofort auf ganze Frames quantisiert. → G1
- `AUD-3` mittel — negative Offsets: asymmetrisches Clamping verschiebt statt verkürzt.
- `AUD-4` mittel — globaler Playback-State, fragil für #76.
- `AUD-5` niedrig — Peak-Schwelle robust für Marker, grob für Smart-Boundaries.
- `AUD-6` niedrig — audioop/pydub-Deprecation live im Test-Run.

### KI- / Clip-Boundary-Pipeline
- `KI-1` hoch→mittel — Prompt hartcodiert + nicht injizierbar → #70-Harness kann nicht andocken. → §3
- `KI-2` **hoch→mittel** (S) — R2-Ausricht-Schutz nur ein Status-Label → vergiftete Kandidaten. → §2.2
- `KI-3` mittel — selbst-berichtete Modell-Confidence als harte Brems-/Score-Achse, unkalibriert.
- `KI-5` mittel — keine UI/CLI zum Hinterlegen des Keys (store() ohne Aufrufer).
- `KI-4` niedrig — Modell-ID `claude-opus-4-7`, eine Generation hinter Opus 4.8 (trivialer Wechsel).
- `KI-6` niedrig — Transkriptions-Engine + Descript-Import als Sackgassen-Nähte.
- `KI-7` niedrig — JSON-Extraktion „erstes { bis letztes }" fragil bei Prosa-mit-Klammern.

### Abhängigkeiten, Laufzeit & Build
- `DEP-1` hoch→mittel — pydub hängt komplett an stdlib audioop (in 3.13 entfernt); jede Audio-Op läuft hindurch. → §3
- `DEP-2` mittel — gespaltener ffmpeg-Pfad: pydub via PATH statt zentraler FFMPEG_BIN. → G3
- `DEP-3` mittel — Python-Pin nur in Doku, nirgends erzwungen. → §3
- `DEP-4` mittel — simpleaudio (unmaintained C-Extension) NICHT geparkt, sondern load-bearing für #76.

### Code-Qualität & Konsistenz
- `CQ-1` hoch→mittel — ~60 Zeilen duplizierter Prozess-Lebenszyklus in der churn-stärksten Datei. → §4 (G7)
- `CQ-2` hoch→mittel — drei divergierende Mix-Erkennungs-Heuristiken. → §2.5
- `CQ-3` mittel — video_preview_peak nutzt un-konfigurierten Logger, umgeht das Datei-Log.
- `CQ-4` mittel — keine systematische Type-Hint-Abdeckung (GUI ~14%).
- `CQ-5` mittel — review_page.py (771 LOC) mischt UI/Wiedergabe/Export/Smart (God-Object).
- `CQ-6` niedrig — Doku/Code-Drift bei Testzahl.
- `CQ-7` niedrig — Kind-Prozess-Fehler im Dev-Pfad zu flüchtigen Meldungen herabgestuft.

### Test-Sicherheitsnetz
- `TEST-1` hoch→mittel — kein Test startet einen echten QThread / beweist C++-Cleanup. → §3
- `TEST-2` hoch→mittel — `_categorize_files` (der #77-Punkt) hat keinen eigenen Test. → §3
- `TEST-3` mittel — review_page.py (höchster Churn) nur in Orchestrierungs-Logik abgedeckt.
- `TEST-4` mittel — Fehlerpfade der breiten except-Blöcke kaum direkt getestet.
- `TEST-5` niedrig — ein Pin-Hash absolut hartcodiert (bricht bei legitimer Plattform-Drift).
- `TEST-6` niedrig — kein Undo-Test (Feature existiert noch nicht). → G2

---

## Anhang B — Methode

- **Werkzeug:** Mehr-Agenten-Workflow („ultracode"), Lauf-ID `wf_7f48e235-cb1`.
- **Phase 1:** 9 Dimensions-Agenten lesen den echten Code (Read/Grep), je strukturierter
  Befund-Satz mit Beleg (file:line), Schweregrad, Fundament-Impact, Roadmap-Bezug, Aufwand.
- **Phase 2:** 16 adversariale Gegen-Agenten prüfen alle hoch/kritisch-Befunde am Code
  (confirmed / overstated / misdiagnosed / false + korrigierter Schweregrad).
- **Phase 3:** 2 unabhängige Synthese-Agenten (risk-first + roadmap-first) → konvergent.
- **Filter:** Subagent-Output wurde gegen Max' Realität geprüft, bevor er hier landete
  (z.B. Smoke-Skript als Wegwerf-Helfer eingeordnet; guest_name-Insel als bewusst Pin-1-verriegelt).
