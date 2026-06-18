# PeakCut — Backlog (Single Source of Truth)

> **Die EINE Todo-Wahrheit für PeakCut.** Neue Todos NUR hier eintragen.
> Specs/Pläne beschreiben das *Wie* eines Punktes, duplizieren aber nie diese Liste.
> Memory/Notion bleiben todo-frei und verweisen hierher.
>
> **„#76", „#77", „G1", „ARCH-1" usw. sind nur Namen/Label — KEINE Aufgabenzahl.**
>
> Stand: 2026-06-18 · ~21 offene Punkte · Quelle: ultracode-Sweep (Repo-Docs,
> Code-Kommentare, GitHub-Issues=0, Memory, Notion=0), dedupliziert.
> (Putzfirma-Hygiene-Pass 2026-06-16: Doku-Entrümpelung erledigt — siehe unten.)
>
> Je Punkt: **[Aufwand S/M/L/XL]** · **braucht:** Carl-Plan / Max-Entscheidung / Max-Material / nichts.

---

## 🐛 Bugs
- _(aktuell keine offenen)_

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
- **Import-Umbau: feste Slots statt Namensraten** (#37/#77) `[XL]` · braucht: Carl-Plan — **STRUKTURTEIL ERLEDIGT, ruht**
  Eigenes Mix-Feld statt Mix-in-mic_tracks, Schema v4 rückwärtskompatibel, ein
  zentraler Klassifizierer (letzte Insel eingesammelt). Strukturteil fertig +
  Carl-Review grün: Task 0/1/2/3/4/6 (756 Tests, Pin-1 stabil). **Task 5 „Mix aus
  mic_tracks strippen" geparkt** (Pin-1-riskant + kosmetisch, weil XMLExporter die
  Audiospuren noch direkt aus mic_tracks baut), **Import-UI (Task 7) + Transcript
  (Task 8) pausiert** bis die Produkt-/Kunden-Richtung klar ist (Marker-Pflicht?
  Erkennung per Audio-Inhalt? für wen?). Scope-Entscheidung 2026-06-16 im Plan.
  Nächste Energie → Produkt-Validierung (#70 + Cutter-Sign-off).
- **Prompt-Tuning für die KI-Clip-Grenzen** (#70) `[L]` · braucht: Max-Material
  Few-Shot-Beispiele + Anti-Muster + HM-Stilprofil, messbar über A/B-Vergleich.
  Beinhaltet die **Aufhänger-Wahl** (welcher Satz ist der beste Einstieg — z. B.
  Stelle 7: Frage „Woher kommt das?" vs. die Erklärung). Gate (erfüllt): nach #76.
- **Totale bei schnellem Dialog/Cross-Talk** (Slice A) `[L]` · braucht: Max-Material
  Heute nur in Monolog-Blöcken ≥90s; soll bei Cross-Talk kommen, aber NICHT bei
  humorvollem Schlagabtausch. Wartet auf Max' Material-Markierung aus 1plus1.

## 🏗️ Fundament & Architektur
- **Export-Steuerung aus der Oberfläche in den Kern holen** (ARCH-1) `[M]` · braucht: Carl-Plan
  Folgenschnitt-Leitplanke lebt nur im GUI-Code; ein zentraler `run_export`-Kern
  garantiert sie überall (nötig vor NAS/Headless).
- **Internes Timeline-Modell statt handgeschriebener XML-Strings** (G1) `[XL]` · braucht: Carl-Plan
  Löst Frame-Drift bei negativem Offset, dreifach kopiertes XML-Gerüst und den
  Resolve-/FCPXML-Schmerz an der Wurzel. Logik-Schicht ist ~80% schon da.
- **Projekt-Speichern/Laden + Undo** (G2) `[L]` · braucht: Carl-Plan
  Persistenz (.peakcut) ist gelandet; **Undo fehlt** — V3-Voraussetzung, kein nice-to-have.
- **Threading-/Lebenszyklus-Härtung + echte Thread-Tests** `[L]` · braucht: Carl-Plan
  Worker-Handle-Disziplin (Neustart ohne sauberen Abbau), echte QThread-Tests
  (TEST-1). Durch #76 teilweise entschärft, Rest offen.
- **Letzte Klassifizierer-Insel zusammenführen** (AUD-1) `[S]` · braucht: nichts
  „Ist das Mix/Keyboard/Mic?" wird noch an mehreren Stellen unterschiedlich
  beantwortet. *Kann im Import-Umbau (#77) aufgehen.*

## 🧹 Hygiene & Wartung
- **Versions-Drift in build.sh / PeakCut.spec** (stehen auf 2.9.0, App ist 2.11) `[S]` · braucht: Max-Entscheidung
  Vor Wiederbelebung des macOS-Bundles beide aktualisieren.
- **Sammel-Tech-Schulden** `[L]` · braucht: nichts — geparkt
  Type Hints systematisch, FCPXML-Export, Drop-Frame 29.97, simpleaudio ersetzen,
  ffmpeg-Versionspin. Loser „irgendwann"-Sammelposten.

## ✔️ Abnahme & Validierung
- **Cutter-Sign-off** `[S]` · braucht: Max-Material
  1 sauberen, vollständig zugeordneten Folgenschnitt-Export von Alex abnehmen lassen.
  Reine Bestätigung, kein Blocker (XML frame-identisch zur gelobten Version verriegelt).

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
