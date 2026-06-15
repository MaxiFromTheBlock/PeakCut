# PeakCut — Backlog (Single Source of Truth)

> **Die EINE Todo-Wahrheit für PeakCut.** Neue Todos NUR hier eintragen.
> Specs/Pläne beschreiben das *Wie* eines Punktes, duplizieren aber nie diese Liste.
> Memory/Notion bleiben todo-frei und verweisen hierher.
>
> **„#76", „#77", „G1", „ARCH-1" usw. sind nur Namen/Label — KEINE Aufgabenzahl.**
>
> Stand: 2026-06-16 · ~22 offene Punkte · Quelle: ultracode-Sweep (Repo-Docs,
> Code-Kommentare, GitHub-Issues=0, Memory, Notion=0), dedupliziert.
>
> Je Punkt: **[Aufwand S/M/L/XL]** · **braucht:** Carl-Plan / Max-Entscheidung / Max-Material / nichts.

---

## 🐛 Bugs
- **Shot-Auswahl-Dropdown auf macOS schlecht lesbar** `[S]` · braucht: Carl-Plan
  Natives macOS-Popup färbt die markierte Zeile teils unlesbar (weiß auf hellgrau);
  Stylesheet greift nicht → nicht-native Liste mit festen Farben nötig.

## 🔧 Funktions-Ausbau (nächste Features)
- **Import-Umbau: feste Slots statt Namensraten** (#37/#77) `[XL]` · braucht: Carl-Plan — **NÄCHSTER SLICE**
  Marker/Mics/Mix/Transkript/Kameras bekommen echte Plätze beim Import; eigenes
  Mix-Feld statt Mix-in-mic_tracks, Schema v3 rückwärtskompatibel. Zieht die letzte
  Klassifizierer-Insel mit (siehe Fundament).
- **Prompt-Tuning für die KI-Clip-Grenzen** (#70) `[L]` · braucht: Max-Material
  Few-Shot-Beispiele + Anti-Muster + HM-Stilprofil, messbar über A/B-Vergleich.
  Gate (jetzt erfüllt): erst nach #76 Wiedergabe.
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
- **Python 3.11 maschinell pinnen** (.python-version + CI + Start-Wache) `[S]` · braucht: nichts
  Tickende Uhr: pydub hängt am stdlib-`audioop`, das in Python 3.13 wegfällt; Pin
  steht nur in der Doku, nirgends erzwungen.
- **Doku-Entrümpelung** `[S]` · braucht: nichts
  Abgeschlossene Specs als solche markieren; totes Modul-Diagramm in CLAUDE.md fixen
  (nennt gelöschtes `core/audio.py`).
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
- **Competitor-Recherche** `[S]` · nichts — autocut.com, Resolve Scene-Cut, GitHub. Geparkt.

---

## ✅ Erledigt (Historie, Kurzform)
- **#76 Wiedergabe-UX** — synchrone Ton+Bild-Vorschau, Scrub-Resume (2026-06-16)
- **Slice B Multi-Track-Folgenschnitt** + **Slice C Audio-Mix-only** (2026-06-15)
- **Daten-Integritäts-Riegel** — DATA-1 atomare Akte · DATA-2 Schema-Policy · KI-2 R2-Riegel · AUD-1a Mix-Hub (2026-06-15)
- **State-of-PeakCut Health-Check** (2026-06-15)
- **#71a Audio-Routing** (2026-05-25) · **#3 Smarte Clip-Grenzen** (2026-05-21) · **LUT hinzufügen** · **Fremdmaterial-Test 1plus1** (2026-06-01) · **Folgenschnitt Stufe 1/2** + generischer Zuordnungs-Schritt
