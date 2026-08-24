# PeakCut — Backlog (Single Source of Truth)

> **Die EINE Todo-Wahrheit für PeakCut.** Neue Todos NUR hier eintragen.
> Specs/Pläne beschreiben das *Wie* eines Punktes, duplizieren aber nie diese Liste.
> Memory/Notion bleiben todo-frei und verweisen hierher.
>
> **„#76", „#77", „G1", „ARCH-1" usw. sind nur Namen/Label — KEINE Aufgabenzahl.**
>
> Stand: **2026-08-24** (davor 2026-08-17) · Quelle: Carl-Gesundheitscheck 12.08. +
> Ultracode-Sweep 17.08., Befunde am Code gegengeprüft.
>
> Je Punkt: **[Aufwand S/M/L/XL]** · **braucht:** Carl-Plan / Max-Entscheidung / Max-Material / nichts.
>
> ### ⚠️ Wo die Arbeit gerade wirklich liegt
> Seit Juli läuft die Hauptarbeit an der **neuen Oberfläche** im Schwester-Repo
> `PeakCut-web`, nicht an diesem Kern. **Max-Entscheid 2026-08-17: Sie soll die
> PyQt-App ersetzen** — Paketierung, Selbst-Start der Engine und CheckIn-Anbindung
> sind damit echte Aufgaben. Die dortige Reihenfolge steht in
> `PeakCut/App/docs/CONTEXT.md` → „Aktuelle Prioritaeten". Todos, die **nur** die
> neue Oberfläche betreffen, gehören nicht in diese Liste; alles was den **Kern**
> anfasst, schon.

---

## 🐛 Bugs
- **Desktop-Export und Web-Export liefern unterschiedliche Dateisätze** `[M]` · braucht: Carl-Plan
  **NEU 2026-08-17 (Ultracode-Sweep).** Der Export-Knopf der PyQt-App schreibt **keine**
  Sinnabschnitt-Dateien (`gui/workers.py:295-298` — bedingter Pfad), die Web-Engine
  schreibt sie **immer** (`PeakCut-web/engine/engine_core.py:290-292`). Der Byte-
  Paritäts-Vergleich kann das strukturell **nicht** sehen, weil sein Desktop-Teil die
  Bedingung umgeht — er meldet grün, obwohl die Ergebnisse sich unterscheiden.
  Fällt sauber mit ARCH-1 (eine Export-Steuerung) weg; bis dahin ist es eine Falle.
- **Gastname kommt nicht aus dem Kern zurück** `[S]` · braucht: nichts
  **NEU 2026-08-17.** `core/project_archive.py:478-479` gibt den gespeicherten
  Gastnamen beim Analyse-Abschluss nicht heraus, deshalb verpufft er im Web-Pfad
  (dort baut `analyze_runner.py:159-162` die Akte danach frisch auf). Betrifft den
  Kern, nicht nur die Oberfläche — der Gastname färbt die Sprecher-Vorbelegung **vor**
  der Analyse, ist also nicht nachreichbar. Folge sonst: Exportordner „Unknown".
- **Sinnabschnitte-Zähler wird herkunftsblind, sobald Auto-Kandidaten existieren** `[S]` · braucht: nichts
  **NEU 2026-08-19/20 (Kandidaten-quellenunabhängig, Abschluss-Review, deferred).**
  `gui/review_page.py:590-591` und `:687-689` bilden zwei Aggregate über
  `session.clip_candidates`, ohne nach `origin` zu filtern. Heute folgenlos (es gibt
  nur Marker-Kandidaten), aber am Tag des ersten Auto-/Transkript-Kandidaten
  unterdrückt ein einziger fremder Kandidat MIT Score den ganzen Smart-Lauf
  (`_maybe_start_smart_worker` hält ihn fälschlich für „schon berechnet") und die
  Statuszeile zeigt eine falsche Zahl „Sinnabschnitte bereit (N)". Fix: beide
  Aggregate auf `origin == ORIGIN_MARKER` filtern (über `core/candidate_view.py`,
  nicht roh über `clip_candidates` iterieren). **Wichtigster** der zurückgestellten
  Punkte dieser Runde.
- **`main_window.py` fängt `ClipCandidateError` an zwei Stellen nicht ab** `[S]` · braucht: nichts
  **NEU 2026-08-19/20 (Kandidaten-quellenunabhängig, Abschluss-Review, deferred).**
  `_load_from_archive` (`:280`) fängt nur `ProjectArchiveError`; `_on_analysis_done`
  (`:317`, ruft `session.load_analysis_results`) fängt gar nichts. Eine kaputte Akte
  mit doppelten Peak-Indizes/`candidate_id`s entkommt damit dem „kontrollierter
  Hinweis statt Crash"-Vertrag, den `build_playback_window` und `review_page.on_ignore`
  (Fix-Welle 2026-08-19/20) für denselben Fehlertyp schon einhalten.

## 🔧 Funktions-Ausbau (nächste Features)
- **Sinnabschnitt-Grenzen auf Satzanfang/-ende einrasten** `[M]` · braucht: Carl-Plan
  Aus der Philip-Siefer-Produktion: smarte Sinnabschnitte fangen/hören teils mitten
  im Satz an/auf (z. B. Stelle 7 endet auf „…wo.").
  **Befund (geprüft 2026-06-18):** Das Whisper-Transkript hat fast KEINE Satzzeichen
  (54 Punkte / 7 Fragezeichen auf 14.400 Wörter, nur ~14 % der Blöcke enden auf `.?!`)
  → kein verlässliches „echtes Satzende" zum Einrasten. PeakCut schneidet heute schon
  an Sprechpausen (~0,9 s), aber „Satzende" = nur Whisper-Blockende, kein echtes.
  Zwei Wege: **(a) günstig** — Pausen-Schwelle nachschärfen + Entscheider-Hinweis
  „an fertiger Aussage enden", an echtem Material gegenchecken; **(b) sauber** — echtes
  Satz-Signal besorgen (besseres Transkript/Descript oder KI-Satzgrenzen-Schritt).
  Erst (a), dann ggf. (b). **NICHT** die Aufhänger-Wahl (bester Einstiegssatz) → #70.
- **Import-Umbau: feste Slots statt Namensraten** (#37/#77) `[XL]` · braucht: nichts — **IM KERN GEBAUT, in der PyQt-App NICHT VERDRAHTET**
  **Korrigiert 2026-08-17.** Die alte Notiz („Strukturteil erledigt, Rest geparkt")
  ist überholt: Der capability-driven Import ist im Kern **fertig** —
  `core/material_scanner.py` (Rollen-Vorschlag inkl. Marker-Erkennung am Signal),
  `core/project_capabilities.py` (7 verriegelte Tests), `core/import_model.py`,
  `core/import_project.py`, Schema **v5** mit PENDING-Zwischenzustand
  (`project_archive.read_pending_import`). Alles auf allen drei Zweigen (Merge `deb6265`).
  **Was fehlt:** `material_scanner` hat in `App/src` **keinen einzigen Aufrufer**. Die
  PyQt-App rät weiter per Dateiname (`gui/main_window.py:219-236`). Genutzt wird der
  Pivot bisher nur von der neuen Oberfläche. → Verdrahten + AUD-1 in einem Rutsch.
  Weiter geparkt: Task 5 „Mix aus `mic_tracks` strippen" (Pin-1-riskant + kosmetisch).
- **Prompt-Tuning für die KI-Clip-Grenzen** (#70) `[L]` · braucht: Max-Material
  Few-Shot-Beispiele + Anti-Muster + HM-Stilprofil, messbar über A/B-Vergleich.
  Beinhaltet die **Aufhänger-Wahl** (welcher Satz ist der beste Einstieg — z. B.
  Stelle 7: Frage „Woher kommt das?" vs. die Erklärung). Gate (erfüllt): nach #76.

## 🏗️ Fundament & Architektur
- **Export-Steuerung aus der Oberfläche in den Kern holen** (ARCH-1) `[M]` · braucht: Carl-Plan
  Folgenschnitt-Leitplanke lebt nur im GUI-Code; ein zentraler `run_export`-Kern
  garantiert sie überall (nötig vor NAS/Headless).
- **Internes Timeline-Modell statt handgeschriebener XML-Strings** (G1) `[XL]` · braucht: Carl-Plan
  Löst Frame-Drift bei negativem Offset, dreifach kopiertes XML-Gerüst und den
  Resolve-/FCPXML-Schmerz an der Wurzel. Logik-Schicht ist ~80% schon da.
  Konkretes Symptom (Carl-Schluss-Review 2026-06-18): in den **kompakten XMLs** kommt
  die Video-Clip-Länge aus offset-**geclampter** Source, Marker/Audio aber aus
  **ungeclampter** Peak-/Boundary-Dauer (`exporters.py` ~323, `sinnabschnitt_exporter.py`
  ~164). Bei großen negativen Offsets am Sequenzanfang können Video-Clips kürzer sein
  als die Marker-/Audio-Spanne. Aus raw geerbt (nicht neu durch Marker-Slice), kein
  Blocker (Philip-Siefer abgenommen) — fällt mit G1 weg.
- **Projekt-Speichern/Laden + Undo** (G2) `[L]` · braucht: Carl-Plan
  Persistenz (.peakcut) ist gelandet; **Undo fehlt** — V3-Voraussetzung, kein nice-to-have.
- **Threading-/Lebenszyklus-Härtung + echte Thread-Tests** `[L]` · braucht: Carl-Plan
  Worker-Handle-Disziplin (Neustart ohne sauberen Abbau), echte QThread-Tests
  (TEST-1). Durch #76 teilweise entschärft, Rest offen.
- **Historien-Frage: muss eine Decision auf einen vorhandenen Kandidaten zeigen?** `[S]` · braucht: Carl-Plan
  **NEU 2026-08-21 (Gate B / Block A, bewusst offen gelassen).** Die Sammlungs-Prüfung
  an der Archivgrenze (`validate_candidate_collection`) sichert nur die EINDEUTIGKEIT
  der `candidate_id`. Ob das Entscheidungslog auch referenziell sauber sein muss (jede
  Decision zeigt auf einen aktuell existierenden Kandidaten) ist eine eigene
  Vertragsfrage — Decisions sind Historie und dürfen Kandidaten überleben.
- **Letzte Klassifizierer-Insel zusammenführen** (AUD-1) `[S]` · braucht: nichts
  **Präzisiert 2026-08-17 (selbst nachgegrept, vorher zu pauschal formuliert):** Der
  ganze `core/`-Baum geht inzwischen über `import_classifier` — `audio_routing:52`,
  `speaker_activity:52-57`, `guest_name:18`, `material_scanner:16`, `import_model:13`,
  `project:43`. **Übrig ist GENAU EINE Insel:** `gui/main_window.py:231`
  (`_categorize_files`) prüft weiter inline `any(kw in filename for kw in
  ["keyboard","keys","klavier"])` und kennt weder das Mix-Gerätemuster (P8Mix) noch
  die Inhalts-Erkennung. Sinnvoll zusammen mit dem Verdrahten von
  `core/material_scanner.py` in die PyQt-App zu erledigen (siehe Punkt darunter).

## 🧹 Hygiene & Wartung

**Aus dem Abschluss-Audit 2026-08-24 (49 Prüfer, jeder Befund gegengeprüft):**

- **CheckIn-Oberfläche: fünf Altlasten als Bündel** `[S]` · vier davon sitzen im
  heute angefassten Übergabe-Weg, keine verliert Daten:
  (1) toter Aufruf `onDesktopChanged` wirft bei jedem Start einen Fehler in die
  Konsole; (2) der Übergabe-Knopf wird nach einem späteren Refresh wieder klickbar
  und zeigt dann „0 Dateien kopiert" (die Zeile `uebergabeBtn.disabled =
  !result.uebergabe_folder` überschreibt den Erfolgszustand — Altbestand, nicht neu);
  (3) der Aufgabenzähler zählt eine erledigte Übergabe als offen; (4) roher
  Python-Fehlertext landet als Knopfbeschriftung; (5) tote Konstante
  `CHECKLIST_LABELS` (die echten Labels stehen in `index.html`).
- **NAS-Sortierwerkzeug kennt nur den alten Namen** `[S]` · `inventory_episode.sh`
  sucht `Keyboardstellen`. Heute harmlos, weil dort über den Ordnerpfad einsortiert
  wird, nicht über den Dateinamen — aber bewusst gestaffelt und deshalb hier
  festgehalten, statt nur in einer lokalen Datei.
- **Cockpit-Doku auf den neuen Dateinamen ziehen** `[XS]` ·
  `HM/6_Cockpit/Infrastruktur.md:166` und `Roadmap.md:62` beschreiben die Übergabe
  noch mit `Keyboardstellen - {Gast}.mp3`.
- **Kein automatischer Wächter in Web und CheckIn** `[M]` · braucht: Carl-Klärung.
  Der Kern hat eine automatische Testprüfung, die anderen beiden nicht — CheckIn ist
  die Brücke zur laufenden Produktion und damit das einzige Programm ohne Netz.

- **Zwei kosmetische Restpunkte aus dem Kandidaten-Umbau** `[S]` · braucht: nichts
  **Präzisiert 2026-08-23 beim Merge — Zeilen am Code nachgeprüft.** Der frühere
  Sammelposten nannte vier Punkte; zwei davon waren zu dem Zeitpunkt bereits behoben
  (der Kommentar-Zeilendrift in `session.py` und die Stellung des
  „bewusst NICHT angefasst"-Kommentars) und sind gestrichen. Übrig:
  (1) `core/candidate_view.py:17` liest die Session defensiv per `getattr`, den
  Kandidaten aber hart per `c.origin` — inkonsistent.
  (2) `core/clip_boundary/pipeline.py:106` und `core/session.py:214` nutzen
  `list.index()` über Wertgleichheit statt Identität; heute sicher, weil zwei
  wertgleiche Kandidaten dieselbe `candidate_id` hätten und die zentrale Sicht
  vorher wirft — aber eine unausgesprochene Abhängigkeit.
- **Versions-Drift in build.sh / PeakCut.spec** (stehen auf 2.9.0, App ist 2.11) `[S]` · braucht: Max-Entscheidung
  Vor Wiederbelebung des macOS-Bundles beide aktualisieren.
- **Sammel-Tech-Schulden** `[L]` · braucht: nichts — geparkt
  Type Hints systematisch, FCPXML-Export, Drop-Frame 29.97, simpleaudio ersetzen,
  ffmpeg-Versionspin. Loser „irgendwann"-Sammelposten.

## ✔️ Abnahme & Validierung
- **Marker-XML in Premiere importieren** (Max) `[S]` · letzter Riegel vor dem
  Produktivgebrauch der Umbenennung.
  Belege liegen in `~/Desktop/MF/Vibecoding/PeakCut/Abnahmen/2026-08-24 Marker/`
  (`_WAS-IST-DAS.md` erklärt, welche Datei welche ist). Zu importieren:
  `Marker - Ilka Bessin.xml` — echt aus der Ilka-Akte erzeugt, 31 Marker.
  Die Smart-XML dort ist nur eine Strukturprobe aus der Testvorrichtung; für eine
  echte Smart-XML braucht es eine Akte mit bewerteten Sinnabschnitten.
  Carl hat Kern, Web und CheckIn am 2026-08-24 abgenommen — nur diese Sichtprüfung
  in Premiere fehlt noch.

## 🤔 Offene Entscheidungen (Max)
- **Distributions-Pfad festlegen** · braucht: Max-Entscheidung
  Bewusst „interne Repo-App" bleiben ODER saubere Releases/Versionierung + Code
  Signing. „Dazwischen" tut langfristig weh.
- **Drift-Toleranz Ton↔Bild final bestätigen** (steht provisorisch auf 100 ms) `[S]` · braucht: Max-Entscheidung
  100 ms wurde mit #76 gemergt; offene Carl-Methodik-Frage „enger korrigieren?" nach mehr Real-Material.

## 🔮 Zukunftsmusik (später)
- **Produktions-Profile als Datenmodell** (G4) `[M]` · Carl-Plan — Helligkeit/LUT/Mix strukturell ins Format (HM ≠ 1plus1).
- **Hub / Projekt-öffnen-Oberfläche** (G6) `[L]` · Carl-Plan — .peakcut öffnen, Zuordnung editieren, Archiv neu analysieren, Ignoriert-Status sichtbar.
- **Plattform-Gabel härten für NAS-Container** (G3) `[M]` · Carl-Plan — macOS-Kopplungen (say-TTS, Keychain, Whisper) + ffmpeg-Pfad kapseln.
- **Lerndaten-Zulauf für Clip-Statusmaschine** (G5) `[M]` · Max-Entscheidung — produktiver Schreibpfad selected/produced/published (der Burggraben).
- **Sprecher-Gegencheck über die Mics** `[M]` · Carl-Plan — Descript-Label gegen Mic-Aktivität abgleichen.
- **SRT-Untertitel für Premiere** `[L]` · Carl-Plan — **NEU (Max-Wunsch Philip Siefer)**: SRT aus dem
  Transkript erzeugen, direkt in Premiere ziehbar. Descript-API als mögliche Transkript-/Untertitel-Quelle
  prüfen (steht ohnehin auf der Geparkt-Liste).
- **Competitor-Recherche** `[S]` · nichts — autocut.com, Resolve Scene-Cut, GitHub. Geparkt.

---

## ✅ Erledigt (Historie, Kurzform)
- **Keyboard→Marker Teil 2 (Byte-ändernder Teil) durch** (2026-08-24, Carl-Schluss-Gate grün) — Max-Entscheid „Marker überall". Sieben Export-Literale umgestellt: die drei Dateinamen (`Marker - {Gast}.{mp3,txt,xml}`), TXT-Kopfzeile `KEYBOARD PEAKS`→`MARKER`, Raw-Sequenzname `Marker raw`, Smart-Sequenz-ID `marker-smart`, Smart-Sequenzname `Marker smart`. **Pin-1 bewusst neu eingefroren** (`e45cc987…`→`a70a8b8c…`); der normalisierte Byte-Diff der Raw-XML umfasst genau die Sequenzzeile — vor dem Einfrieren gemessen, Sequenz-ID `peakcut-sequence` unberührt. Eigener Strukturtest für `marker-smart` (Pin-1 deckt nur Raw). Kompatibilitätsgrenze unangetastet: `CAP_KEYBOARDSTELLEN`, die `keyboardstellen_*`-Protokoll-IDs (auch die Wörterbuch-Schlüssel im Web-Paritätsgate), `keyboard_track` als Archiv-Lese-Alias, Erkennungstokens `keyboard`/`keys`/`klavier`, reale Quelldateinamen. CheckIn ging bewusst ZUERST live (eigenes Repo, `main`=`13b6351`): liest neuen und alten Namen dauerhaft (kein Ablaufdatum), Exaktheit schlägt Namensvariante, Mehrdeutigkeit bricht laut ab und wird in der Oberfläche angezeigt; geschrieben wird nur der neue Name. 910 Kern / 363 Web-Engine / 64 CheckIn grün, C1-Paritätsgate gegen die echte Ilka-Akte 🟢 read-only. Kern `main`=`d140202`, Web `develop`=`bc641e6` (Web-`main` bewusst nicht nachgezogen). Offen: nur noch Max' Premiere-Import (→ Abnahme & Validierung).
- **Stellen quellenunabhängig + Namensdrift begradigt** (2026-08-23, Carl-Gate B grün) — `ClipCandidate` trägt `candidate_id`/`origin`/`anchor_ms` (optionales `peak_id`), Akten-Schema v5→v6 mit Migration beim Hydrieren, Reconciliation statt Replace (Neu-Analyse vernichtet keine Fremdquellen und kein Entscheidungslog mehr), zentrale Marker-Sicht statt fünf blinder `peak_id`-Joins, Invarianten an der Wurzel (`origin != marker` ⇒ `peak_id is None`, reservierter Namensraum `marker:`), Identitäts-Validierung an der Archivgrenze. Kanonisch: `session.candidate_decisions` / Akten-Sektion `candidate_decisions` / Klasse `CandidateDecision`; `peak_decisions` nur noch als Legacy-JSON-Schlüssel, `PeakDecision`-Alias entfernt. 909 Kern-Tests, Pin-1 byte-identisch, reales Ilka-Paritäts-Gate 6/6.
- **Gate B / Block A — v6-Strenge, Kandidaten-Identität, Wurzel-Invarianten** — drei Vertragslücken aus Carls Abschluss-Gate geschlossen (2026-08-21): (A1) die v6-Strenge hing an `if "candidate_id" in d` statt an der Schema-Version — eine beschädigte Schema-6-Akte tarnte sich als Legacy und lud still als `marker:0`; jetzt entscheidet `schema_v >= 6` (Kandidaten UND Decisions). (A2) neue zentrale Sammlungs-Prüfung `validate_candidate_collection` in BEIDE Richtungen (Laden + vor dem Schreiben): doppelte `candidate_id` → `ProjectArchiveError`, nach dem Hydrieren Sortierung nach `(anchor_ms, candidate_id)`. (A3) die peak_id-Kollisionsklasse ist an der Wurzel geschlossen (`ClipCandidate.__post_init__`): `origin != marker` erzwingt `peak_id is None`, Marker-ID muss zur `peak_id` passen, Namensraum `marker:` reserviert. Die zentrale Marker-Sicht bleibt als zweite Verteidigungslinie; die Kollisionstests arbeiten dafür mit absichtlich ungültigen Objekten (`tests/malformed_candidates.py`). 903 Tests grün, Pin-1 stabil
- **Marker + Vergleichbarkeit Keyboardstellen ↔ Sinnabschnitte** — Carl-Plan, TDD (5 Tasks, 785 Tests). Beide XMLs: Video + Ton (smart hat jetzt dieselben Tonspuren wie raw), nummerierte Bereich-Marker „Stelle N" (synchron trotz peak_id-Versatz), Clip-Namen = Quelldateien, Sequenzen „Keyboardstellen raw"/„smart". Pin-1 bewusst neu eingefroren. Max in Premiere abgenommen (Philip Siefer). Carl-Schluss-Check offen (2026-06-18)
- **Folgenschnitt-XML real bestätigt** — Max hat erstmals seit Langem selbst eine Postproduktion gemacht (Philip Siefer) und die Folgenschnitt-XML „funktioniert super". Erste echte Eigen-Nutzung außerhalb der Smoke-Tests (2026-06-17)
- **Sinnabschnitt-XML in Premiere importierbar + auf Multicam gehoben** — erst fehlten FCP7-Pflichtangaben (Import scheiterte), dann auf Video+Ton+Marker gehoben (siehe Marker-Slice oben). Eigener Codepfad, Keyboardstellen/Pin-1 unberührt (2026-06-17/18)
- **Shot-Dropdown macOS — visuell bestätigt** — nicht-natives Popup + `::item`-Regeln (markierte/überfahrene Zeile blau+weiß), auch die Person-Combos (Kamera + Mic). Max-O-Ton „sah besser aus". Verifiziert per gerendertem PNG + Pixel-Probe (Commits `74a18fc`/`6f0fd55`) (2026-06-17)
- **Crash-Fix Zuordnung** — „Weiter" stürzte ab, wenn eine Kamera einen Personen-Shot (Weit/Nah/Halbnah) OHNE Person hatte (Altbestand v2.10, ValueError im Slot → SIGABRT). Unvollständige Kamera wird jetzt toleriert statt zu crashen (2026-06-17)
- **#77 Strukturteil** — Mix strukturell (mix_track, Schema v4), zentraler Klassifizierer, letzte Inseln vereint (Tasks 0/1/2/3/4/6, Carl-Review grün); Import-UI (7/8) + Strip (5) bewusst geparkt (2026-06-16)
- **Python 3.11 gepinnt** — .python-version + weiche Start-Wache (audioop-Uhr) (2026-06-16)
- **Putzfirma — Repo-Hygiene-Pass** (2026-06-16): toter Code/Importe raus, Doku-Drift gefixt (u.a. `core/audio.py`-Diagramm), 11 Specs + 4 Pläne ins Archiv, CLAUDE.md-Backlog-Block → BACKLOG-Verweis (SSOT durchgezogen), Modell-ID → Opus 4.8, verwaiste Assets weg, develop↔main synchronisiert. **Enthält die frühere „Doku-Entrümpelung".**
- **#76 Wiedergabe-UX** — synchrone Ton+Bild-Vorschau, Scrub-Resume (2026-06-16)
- **Slice B Multi-Track-Folgenschnitt** + **Slice C Audio-Mix-only** (2026-06-15)
- **Daten-Integritäts-Riegel** — DATA-1 atomare Akte · DATA-2 Schema-Policy · KI-2 R2-Riegel · AUD-1a Mix-Hub (2026-06-15)
- **State-of-PeakCut Health-Check** (2026-06-15)
- **#71a Audio-Routing** (2026-05-25) · **#3 Smarte Clip-Grenzen** (2026-05-21) · **LUT hinzufügen** · **Fremdmaterial-Test 1plus1** (2026-06-01) · **Folgenschnitt Stufe 1/2** + generischer Zuordnungs-Schritt
