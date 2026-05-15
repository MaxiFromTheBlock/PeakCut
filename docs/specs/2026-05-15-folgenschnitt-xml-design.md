# Design: Folgenschnitt-XML (Auto-Kameraschnitt)

*Stand: 2026-05-15 · Status: Design, noch nicht implementiert · MVP = Stufe 1*

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

**Sprecher-Erkennung:**
- Pro Mic-Spur wird die Lautstärke über die Zeit gemessen (Fenster-RMS o. ä.).
- "X spricht" = X's Mic ist über Schwellwert.

**Schnitt-Regeln:**
1. Ein Sprecherwechsel wird nur gesetzt, wenn jemand **≥ 5 Sekunden am Stück**
   spricht. Kurze Einwürfe ("mhm", "ja") lösen keinen Wechsel aus.
2. Aktiver Sprecher → seine **Wide**-Kamera. (Gast-Close wird zugeordnet, aber
   in Stufe 1 **nicht** im Schnitt verwendet.)
3. **Vorausschauender Schnitt (Anticipation):** In Sprechpausen wird
   vorausgeschaut, wer als Nächstes ≥5 Sek spricht. Ist es ein anderer als der
   vorherige Sprecher, wird ab der **Mitte der Pause** schon auf dessen Kamera
   geschnitten. Ist es derselbe, bleibt das Bild stehen.
4. Anfang der Folge: ergibt sich automatisch aus Regel 3 (die Folge startet auf
   der Kamera dessen, der zuerst ≥5 Sek spricht).
5. Beide gleichzeitig > 5 Sek (selten bei HM): Bild bleibt beim vorherigen
   Sprecher, kein Hin-und-Her. Der Cutter korrigiert solche Stellen manuell.

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

## Datenfluss (Stufe 1)

```
Import (Mics + Videos)
   │
   ▼
Analyse-Subprozess (bestehend)
   ├── Video-Sync (bestehend) ─────────→ video_offsets
   ├── Peak Detection (bestehend) ─────→ peaks
   └── NEU: Sprecher-Segmentierung ────→ speaker_segments
            (Lautstärke pro Mic-Spur,
             ≥5-Sek-Regel angewandt)
   │
   ▼
Review-Seite
   └── Nutzer setzt Mic→Sprecher + Kamera→Rolle
   │
   ▼
Export
   ├── Keyboardstellen-XML/MP3/TXT (bestehend)
   └── NEU: Folgenschnitt-XML
            (speaker_segments + Kamera-Rollen + offsets
             → Anticipation-Regel → Cut-Liste → XML)
```

---

## Offene technische Punkte (für Reviewer)

Diese Punkte sind im Design noch **nicht entschieden** und gezielt Gegenstand
des externen Reviews:

1. **Mic-Bleed / Übersprechen (größtes Risiko):** Jedes Mikrofon nimmt auch die
   anderen Sprecher auf, nur leiser. Eine naive Regel "MIC2 laut → Gast
   spricht" kann durch eine laute Moderatorstimme im Gast-Mic fehlausgelöst
   werden. Braucht es relativen Pegelvergleich zwischen den Spuren, ein
   Noise-Gate, Cross-Korrelation oder Ducking-Logik? Wie robust muss das für
   einen *Rohschnitt* (Cutter korrigiert eh nach) wirklich sein?

2. **XML-Format:** PeakCut exportiert aktuell FCP7-XML. Reicht das für einen
   kompletten Multicam-Rohschnitt mit vielen harten Schnitten, oder ist
   FCPXML / eine Multicam-Sequenz robuster? Was importiert
   Premiere/DaVinci/FCP am verlässlichsten?

3. **Zustandslogik:** Ist die Kombination aus 5-Sekunden-Mindestdauer +
   vorausschauendem Schnitt frei von Oszillation/Edge-Cases (z. B. schnelle
   Wortwechsel an der 5-Sek-Grenze)?

4. **Architektur-Einbettung:** Sprecher-Segmentierung in den bestehenden
   Analyse-Subprozess integrieren oder als getrennten Pass? Auswirkung auf die
   Analyse-Wartezeit nach jeder Aufnahme (soll gering bleiben).

---

## Erfolgskriterium

Stufe 1 ist erfolgreich, wenn der aus der Folgenschnitt-XML entstehende
Rohschnitt in Premiere "schon vernünftig aussieht" — d. h. die Kamera ist
überwiegend auf der sprechenden Person, ohne nervöses Hin-und-Her, sodass der
Cutter darauf aufbauen statt bei null anfangen kann.
