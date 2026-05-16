# Design: Generischer Zuordnungs-Schritt (Folgenschnitt produktiv machen)

*Stand: 2026-05-16 · Status: Design, noch NICHT in Umsetzung · Folgefeature zu Folgenschnitt Stufe 1*

---

## Für externe Reviewer: Kontext

PeakCut ist eine Python/PyQt6-Desktop-App (macOS) für die Postproduktion des
Podcasts "Hotel Matze". Ablauf: **Welcome → Import → Analyse → Review**.

Das Feature **Folgenschnitt** (Stufe 1, bereits gebaut, 123 Tests grün, Spec:
`docs/specs/2026-05-15-folgenschnitt-xml-design.md`) erzeugt aus der
Sprecher-Aktivität einen Rohschnitt-Vorschlag als zweite FCP7-XML ("wer
spricht → seine Weit-Kamera"). Es ist **noch nicht produktiv nutzbar**: Die
nötige Zuordnung *welche Kamera = welche Rolle, welches Mic = wer* existiert
nur in einem Ad-hoc-Skript, nicht in der App. Ohne sie bleiben
`session.folgenschnitt_edit_decisions` leer und der `FolgenschnittXMLExporter`
wird nie ausgelöst (siehe `gui/workers.py:_build_exporters`).

Zusätzliches Problem: Das gebaute Stufe-1-Datenmodell ist **Hotel-Matze-fest
verdrahtet**. `core/folgenschnitt_models.py` hat `SpeakerId` (Enum:
MATZE/GUEST/UNKNOWN) und `CameraRole` (Enum: MATZE_WIDE/GUEST_WIDE/
GUEST_CLOSE/UNUSED). PeakCut bekommt aber auch Material von Fremdproduktionen
mit anderen Personen, Kameranamen und Setups.

---

## Ziel

Folgenschnitt in der App produktiv nutzbar machen — über einen **eigenen,
gekapselten Zuordnungs-Schritt** — und dabei das Datenmodell von
HM-spezifisch auf **produktionsunabhängig** generalisieren.

---

## Generisches Datenmodell

Pro Kamera-Datei: **voller Dateiname** (sichtbar, nicht aus dem Namen
geratenes Kürzel) + **Shot-Typ** + ggf. **Person**.

- **Shot-Typ** — Auswahlliste mit Freitext-Erweiterung:
  `Weit · Nah/Close · Halbnah · Totale · Eigene… (Freitext, wiederverwendbar) · — nicht nutzen`
- **Personenbezug hängt am Shot-Typ:**
  - personenbezogen (Weit, Nah/Close, Halbnah) → **Person** erforderlich
  - personenunabhängig (Totale, Eigene-Sonderfälle) → **keine Person**
  - "— nicht nutzen" → Kamera ist kein Schnittmaterial (z. B. Nachdreh)
- **Person** — frei eingebbar, einmal Eingegebenes ist bei weiteren Kameras
  wiederverwählbar (man tippt "Matze" einmal, danach auswählbar). Kein
  Personenname ist hartcodiert.
- **Mic → Person** — vorbelegt mit Konvention (MIC1 = Matze/Moderator,
  MIC2 = Gast), in der Zuordnung überschreibbar. Auch hier sind die Namen
  frei, nicht fix.

**Generalisierung gegenüber Bestand (Kern der Tragweite):** `SpeakerId`-Enum
→ freier Personen-String. `CameraRole`-Enum → Kombination
`(shot_type, person | None)`. "Wer spricht → seine Weit-Kamera" wird zu:
Mic liefert Person-String → gesuchte Kamera = die mit `shot_type == "weit"`
und passender Person. Das Konzept "kein eindeutiger Sprecher" (bisher
`SpeakerId.UNKNOWN`) bleibt erhalten, nur nicht mehr als Enum-Wert.

---

## Zuordnungs-Schritt (eigene, gekapselte Ansicht)

Neue Ansicht **zwischen Analyse und Review**: Welcome → Import → Analyse →
**Zuordnung** → Review.

- Kompakte Tabelle aller importierten Kamera-Dateien: *voller Dateiname →
  Shot-Typ → Person*, mit **kleinen Vorschaubildern** je Kamera (damit der
  Nutzer sieht, welche Datei welche Perspektive zeigt).
- Personen-Feld wird nur aktiv, wenn der gewählte Shot-Typ personenbezogen
  ist; bei Totale/Eigene/—nicht-nutzen ausgegraut.
- Mic→Person-Zuordnung darunter (vorbelegt, überschreibbar).
- "Weiter" → Review-Screen **unverändert** wie bisher.

**Bewusst gekapselt:** eigene Ansicht/Komponente, minimal verflochten mit dem
Review-Screen — damit das spätere, separat geplante UX-Gesamtredesign sie
leicht herauslösen/verschieben kann. Der überladene Review-Screen wird durch
dieses Feature **nicht** voller.

---

## Stufe-1-Anbindung

Beim Export (bestehender Export-Knopf): aus der bereits vorhandenen
`session.speaker_activity` + der Zuordnung werden
`speaker_turns` → `edit_decisions` berechnet (bestehende Logik in
`core/folgenschnitt_decisions.py`, generalisiert auf Person-Strings), das
füllt `session.folgenschnitt_edit_decisions`, der `FolgenschnittXMLExporter`
greift dann automatisch.

- Geschnitten wird nur auf **personenbezogene Weit-Kameras** ("wer spricht →
  seine Weit"). Nah/Close/Totale/Sonder werden zugeordnet, aber von Stufe 1
  **nicht geschnitten** (Close = Stufe 2, Totale ggf. später Fallback).
- **Leitplanke:** Keyboardstellen-Export läuft immer. Fehlt/unvollständig die
  Zuordnung (mind. zwei personenbezogene Weit-Kameras + Mic→Person nötig) →
  Folgenschnitt-XML entfällt, Keyboardstellen normal, **kurzer Hinweis**
  ("Folgenschnitt-XML übersprungen — Zuordnung unvollständig").

---

## Tragweite / betroffene Module (für Carls Plan)

Kein reines UI-Feature. Die Generalisierung der HM-Enums zieht durch bereits
gebauten, getesteten Code:

- `core/folgenschnitt_models.py` — `SpeakerId`/`CameraRole`-Enums → generische
  Struktur (Person-String, Shot-Typ, optional Person). Serialisierung
  anpassen.
- `core/speaker_activity.py` — `build_default_mic_assignments` liefert aktuell
  `SpeakerId.MATZE/GUEST` → generische Person-Strings.
- `core/folgenschnitt_decisions.py` — `_speaker_wide_camera_map` /
  `build_edit_decisions` nutzen `CameraRole.*_WIDE` / `SpeakerId` → generische
  Logik (Person → ihre Weit-Kamera).
- `core/session.py`, `core/analysis_process.py` — Felder/JSON, die Modelle
  transportieren.
- `gui/` — neue Zuordnungs-Ansicht + Einhängung in den Flow nach der Analyse.
- Alle `tests/test_folgenschnitt_*` — Erwartungen auf das generische Modell
  umstellen.

Reihenfolge/Schnitt ist Carls Plan-Domäne (analog Folgenschnitt-Plan:
Contracts zuerst, Risiko früh, TDD, Tests mitziehen).

---

## Bewusst NICHT in diesem Feature

- Gesamt-UX-Redesign (Welcome/Analyse/Review/Screenshots/Keyboardstellen/
  Transkription neu strukturieren) — eigenes Großthema, später.
- Selektiver Export (Screenshots/Folgen-XML/Keyboardstellen einzeln oder per
  Checkout-Auswahl) — geparkte Zukunftsidee.
- Folgenschnitt Stufe 2 (Close-Auflockerung) / Stufe 3 (AI).
- Resolve-Relink (separates geparktes Thema, betrifft beide Exporter).

---

## Offene Punkte für die nächste Reviewer-Runde (Carl)

- Generalisierungs-Schnitt im Datenmodell: Wie genau ersetzt man `SpeakerId`/
  `CameraRole` ohne die bestehende Decision-Logik zu zerreißen? Eigener
  Refactor-Task vor dem UI-Teil?
- Vorschaubilder im Zuordnungs-Schritt: vorhandene Frame-Extraktion (ffmpeg,
  wie bei Screenshots) wiederverwenden — Performance bei mehreren Kameras?
- Persistenz: Zuordnung pro Folge frisch (kein Speichern über Folgen hinweg) —
  bestätigen.

---

## Revision 2026-05-16 (nach erster manueller Abnahme durch Max)

Zwei Punkte aus der Abnahme, von Max entschieden. Ändern den
Zuordnungs-Schritt (Carl-Plan Task 6), nicht das Datenmodell:

1. **Kamera-Felder starten neutral, nicht vorbelegt.** Eine ausgefüllt
   *aussehende*, aber durch reine Reihenfolge geratene Vorbelegung ist
   sicherheitskritisch schlecht: ein falscher Default rutscht unbemerkt in
   den Schnitt. Deshalb starten alle Kamera-Zeilen auf einem neutralen
   Zustand („— bitte zuordnen —"), Person bleibt leer/inaktiv bis ein
   personenbezogener Shot-Typ gewählt ist. Eine Kamera im neutralen Zustand
   erzeugt **keine** `CameraAssignment` (wird übersprungen) → die bestehende
   Leitplanke meldet sauber „Zuordnung unvollständig", bis genug gesetzt
   ist. **Mics behalten ihre Vorbelegung** (MIC1/MIC2-Konvention ist
   zuverlässig und war in der Abnahme korrekt).
2. **Hörprobe pro Mic-Zeile.** Ohne Abspielmöglichkeit kann Mic→Person in
   PeakCut nicht verifiziert werden (man müsste die Datei im Finder suchen).
   Pro Mic-Zeile ein „▶ Hörprobe"-Knopf, der eine kurze Probe (~5 s) der
   Mic-Spur abspielt. Wiedergabe off-main-thread (kein UI-Freeze), nutzt
   vorhandene Audio-Infrastruktur; nur ein kurzer Ausschnitt wird dekodiert
   (kein Vollladen großer Spuren). Reine Verifikations-Hilfe, ändert keine
   Daten.

Unverändert: Datenmodell, gekapselte Architektur, Leitplanke, Stufe-1-Logik,
Scope-Grenzen.

## Erfolgskriterium

Folgenschnitt ist in der App **ohne Hilfsskript** nutzbar: Nutzer importiert,
Analyse läuft, ordnet im Zuordnungs-Schritt Kameras/Mics zu (auch bei
Fremdproduktionen mit anderen Namen/Setups), klickt Export — Keyboardstellen
*und* eine korrekte Folgenschnitt-XML kommen raus. Das HM-feste Vokabular ist
aus dem Datenmodell verschwunden.
