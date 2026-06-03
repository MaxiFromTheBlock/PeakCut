# Multi-Track-Folgenschnitt-XML (Slice B) — Design

**Status:** Design, abgenommen 2026-06-03 (Max). Carl-Plan folgt.
**Slot in Roadmap:** Slice A (Cross-Talk-Totale) und B (dieser hier) sind
unabhängig. Max-Reihenfolge 2026-06-03: B zuerst, weil isoliert und mit
bewiesener Hack-Vorlage. A erst sobald Material-Markierung steht.

---

## Hintergrund

Fremdmaterial-Test 2026-06-01 mit „1plus1" (Tim Mälzer / Jan Ullrich,
zwei Folgen-Teile à ~57 min + ~46 min) hat die Produktions-
unabhängigkeit des Folgenschnitts real bestätigt. Max-Sichtung in
Premiere: Sprecher-Wechsel überzeugend.

Aber zwei strukturelle Layout-Wünsche entstanden aus der Sichtung:

1. **Kameras auf eigenen Spuren statt alle auf V1.** Cutter (HM:
   Alex/Lukas, fremde Cutter analog) sollen pro Kamera separat
   editieren können. Heute schreibt `FolgenschnittXMLExporter` eine
   einzige Video-Spur mit nahtlosen Cuts zwischen den
   Kamera-Files.
2. **Audio nur Mix.** Heute exportiert PeakCut alle drei Audio-Spuren
   (Mic A, Mic B, Mix) in die Folgenschnitt-XML. Carl-Hinweis
   2026-06-01: drei aktive Audio-Spuren in der NLE-Timeline holen
   dasselbe Phasing wie #71a in der App zurück — nur eine Ebene höher.

Ein Postprocess-Skript (`~/Desktop/Fremdproduktion/multitrack_postprocess.py`,
argparse-generisch) erzeugt das gewünschte Layout bereits **außerhalb
des Repos** als Stand-In; der Premiere-Import an echtem Material
funktioniert (2026-06-01 / 2026-06-02). Dieser Slice ersetzt den
Skript-Stand-In durch saubere Exporter-Logik im PeakCut-Code.

**Autocut-Recherche-Hinweis (Max 2026-06-03):** Das vergleichbare Tool
„Autocut" hat genau diesen Layout-Toggle als Industrie-Standard unter
dem Namen „Handling Unused Clips: Disable / Remove". Wir übernehmen
die Begriffe. Wesentlicher Unterschied: Autocut nutzt Premiere-eigenes
Multicam-Feature („Multi-Camera editing") — wir bleiben bei
unabhängigem Multi-Track-XML, weil universeller (Resolve, FCP X,
fremde NLEs später).

---

## Ziel

`FolgenschnittXMLExporter` produziert Multi-Track-XML mit:

- **Eine Video-Spur pro Kamera.** Funktioniert für jedes Setup
  (Anzahl Personen × Kameras pro Person, mit/ohne Totale-Kamera).
- **Audio = nur Mix.** Wenn Mix vorhanden in der Decision-Quelle.
  Fallback auf echte Mics nur wenn kein Mix vorhanden.
- **Toggle „Unused Clips" auf der Zuordnungs-Seite:** *Remove* (Lücken)
  oder *Disable* (Clips bleiben, aber `enabled=FALSE` für nicht-aktive
  Decisions). Vom Cutter pro Folge wählbar.
- **Pin-1 weiter:** Keyboardstellen-XML byte-identisch — anderer
  Exporter, nicht von dieser Spec berührt.

---

## Nicht-Ziel (bewusst ausgeklammert)

- **Cross-Talk-Totale** (= Slice A). Wird unabhängig spezifiziert
  sobald Material-Markierung steht.
- **Per-Produktion-Profile** (Roadmap-Pkt 4). Tuning-Defaults für
  Stufe-2-Loosening etc. bleiben im Code/Config wie heute.
- **Premiere-eigenes Multicam** wie bei Autocut. Wir bauen vendor-
  neutrales FCP7-Multi-Track.
- **Single-Track-Fallback-Toggle.** Es gibt keinen Schalter „lieber
  altes Single-Track-Layout zurück" — Multi-Track ist der einzige
  Modus ab Slice-Merge. Begründung Max+Carl: ein klarer Flow ist
  wartbarer als zwei parallele.

---

## Design-Entscheidungen (Max, 2026-06-03)

### 1. Spuren-Verteilung (universell)

**Regel:** Eine Video-Spur pro unterschiedlicher Kamera-Datei in den
Decisions. Reihenfolge im XML:

- **V1 (unten in Premiere) = Totale-Kamera** (`shot_type == "totale"`),
  **wenn vorhanden**. Dient als Fallback-Schicht.
- **V2..VN = Person-Kameras** (in der Reihenfolge der
  `camera_assignments`, also der Reihenfolge aus dem Zuordnungs-Schritt).

**Wichtig:** Da pro Decision exakt eine Kamera aktiv ist (auch nach
Stufe-2-Loosening, das nur die `camera_path` einer Decision setzt),
gibt es **keine Überlappung** zwischen den Person-Spuren V2..VN. Die
Reihenfolge V2..VN ist also visuell irrelevant — Premiere zeigt
immer die einzig-aktive Person-Spur.

V1-Totale ist die einzige Spur, deren Position kritisch ist (Premiere-
Logik „oberste sichtbare gewinnt" — V1 muss unten sein, damit V2..VN
sie ggf. überdecken können).

**Setup-Beispiele:**

| Setup | Spuren-Verteilung |
|-------|-------------------|
| 1plus1 (Jan weit, Tim weit, Totale) | V1=Totale, V2=Jan, V3=Tim |
| HM heute (Matze weit, Gast weit, Gast close, keine Totale) | V1=Matze weit, V2=Gast weit, V3=Gast close |
| HM in Zukunft mit Totale | V1=Totale, V2=Matze weit, V3=Gast weit, V4=Gast close |
| 3 Personen, 1 Kamera/Person, keine Totale | V1=Person A, V2=Person B, V3=Person C |
| 1 Person solo, 1 Kamera | V1=Person — funktioniert klaglos, Multi-Track ist degeneriert zu Single |

### 2. Toggle „Unused Clips" (Disable vs. Remove)

Auf der **Zuordnungs-Seite** (eine Option pro Folge, vom Cutter
wählbar) erscheint:

```
Layout für nicht-aktive Kameras:  ( ) Remove   ( ) Disable
```

- **Remove-Modus (= Lücken):**
  Nur die in der Decision aktive Spur hat einen Clip; alle anderen
  Person-Spuren sind an dieser Position Gap. V1-Totale (falls
  vorhanden) hat in beiden Modi durchgehend Clips an JEDER
  Decision-Position (Fallback-Schicht). Visuell sauber, weniger
  Cutter-Information. Entspricht Hack-Skript-Output 2026-06-02.

- **Disable-Modus (= Deactivated Clips):**
  **Jede** Person-Spur hat für jede Decision einen Clip, aber nur die
  in der Decision aktive ist `enabled=TRUE`; die anderen sind
  `enabled=FALSE`. V1-Totale ist immer `enabled=TRUE`. Cutter sieht
  alle möglichen Kameras pro Schnittstelle und kann mit einem Klick
  umschalten — eine Art Multicam-Look ohne Premiere-Multicam-Feature.

**Default-Vorschlag:** *Disable.* Begründung:
- Autocut-Industriestandard ist Disable (orange Default-Button im
  Autocut-Screenshot 2026-05-31).
- Cutter-Workflow-freundlicher: zusätzliche Information, kein Verlust.
- Remove ist trivial draus erzeugbar (alle disabled-Clips löschen),
  umgekehrt nicht.

Max-Entscheidung zu Default offen (kann jetzt oder im Carl-Review
gesetzt werden).

### 3. Audio

**Regel:** Wenn Mix in den Source-Tracks vorhanden ist (über
`core/audio_routing.get_mix_track` aus #71a), enthält die
Folgenschnitt-XML **genau eine Audio-Spur mit dem Mix** — als ein
durchgehender Clip von 0 bis Sequence-Ende.

**Fallback:** Wenn kein Mix vorhanden ist (z.B. fremde Produktion
ohne Mix-Datei), enthält die XML die echten Mic-Spuren wie heute
(mehrere Audio-Tracks). Das verschiebt das Phasing-Risiko zwar zurück,
ist aber unvermeidbar wenn kein Mix da ist. Cutter-Warnung dafür:
optional als Hinweis im Export-Status („Folgenschnitt-XML enthält
Mic-Spuren statt Mix — Phasing möglich, Mix-Datei fehlt").

**Pin-3 (Audio-Routing-Helper):** Multi-Track-Exporter nutzt den
zentralen `core/audio_routing`-Helper — keine neue Mix-Heuristik.

### 4. Persistenz

Der Toggle-Wert wandert ins `.peakcut`-Schema. Schema-Version steigt
auf **v3** mit additiver Erweiterung:

```json
{
  "schema_version": 3,
  ...
  "assignments": {
    "folgenschnitt_assignment_applied": true,
    "folgenschnitt_mic_assignments": [...],
    "folgenschnitt_camera_assignments": [...],
    "folgenschnitt_unused_clips_mode": "disable"   // ← neu
  }
}
```

Backwards-Kompat: v1/v2-Akten ohne `folgenschnitt_unused_clips_mode`
nehmen den Default (= „disable" oder was Max entscheidet).
v3-Akten in altem PeakCut-Code: tolerieren („unbekanntes Feld
ignorieren"), kein Fail.

### 5. Pin-1 Keyboardstellen-XML byte-identisch

Diese Spec ändert **nur** `FolgenschnittXMLExporter`. Der existierende
`XMLExporter` (Keyboardstellen) bleibt unangetastet. Pin-1-Tests
laufen weiter.

---

## UI-Verhalten im Detail

### Zuordnungs-Seite

Am Ende der Zuordnungs-Page (unter den Kamera-/Mic-Zuordnungs-Zeilen,
vor dem „Weiter"-Button) erscheint:

```
─────────────────────────────────────────────────────
Layout für nicht-aktive Kameras
( ) Remove (Lücken)   ( ) Disable (deaktivierte Clips)
─────────────────────────────────────────────────────
```

Tooltip oder Help-Text klein darunter:
- *Remove:* nur die ausgewählte Kamera-Spur hat Clips, andere sind
  Lücken. Sauberer Schnitt-Look, weniger Multicam-Optionen.
- *Disable:* alle Kameras haben Clips, aber nur die ausgewählte ist
  aktiv. Andere liegen daneben und können mit einem Klick aktiviert
  werden. Multicam-Look ohne Premiere-Multicam-Feature.

Default beim ersten Öffnen einer neuen Akte = `disable` (s. oben).
Bei Re-Open einer existierenden `.peakcut`-Akte: gespeicherter Wert.

### Export-Statusbar

Nach dem Export erscheint die Folgenschnitt-XML wie heute. Bei
Mic-Fallback (kein Mix vorhanden) zusätzliche Statuszeile:

> „Folgenschnitt-XML enthält Mic-Spuren statt Mix — Phasing möglich,
> Mix-Datei fehlt."

### Review-Page

**Unverändert.** Multi-Track betrifft nur den Export-Output, nicht
die Wiedergabe in PeakCut.

---

## Architektur-Skizze

### Was bleibt unverändert

- `core/folgenschnitt_pipeline.py` (Pipeline-Logik, Speaker-Turns,
  Skip-Reason etc.)
- `core/folgenschnitt_decisions.py` (Sprecher-Turn-Bau)
- `core/folgenschnitt_loosening.py` (Stufe-2-Rotation, `_insert_totale`)
- `core/folgenschnitt_models.py` (Datenmodell)
- `core/audio_routing.py` (#71a-Helper, wird nur genutzt)
- `core/exporters.py` (Keyboardstellen-MP3/XML/TXT — Pin-1)
- Sync-Logik, Decision-Erstellung — vollständig unberührt

### Was sich ändert

- **`core/folgenschnitt_exporter.py`** — Hauptchange. `FolgenschnittXMLExporter.export(session)`:
  - Liest `session.folgenschnitt_unused_clips_mode` (neu)
  - Baut N Video-Tracks statt 1
  - Baut 1 Audio-Track (Mix) statt N
  - File-Defs nur beim ersten Vorkommen einer file_id (FCP7-Pattern)
  - DOCTYPE + Sequence-Header + alle FCP7-Pflicht-Elemente
    unverändert beibehalten

- **`gui/assignment_page.py`** — Toggle-UI hinzufügen. Stores in
  `session.folgenschnitt_unused_clips_mode`.

- **`core/session.py`** — Neues Attribut `folgenschnitt_unused_clips_mode`
  mit Default `"disable"`. Property+Setter.

- **`core/project_archive.py`** — Schema-v3 Erweiterung. v1/v2-Akten
  bootstrappen mit Default, v3-Akten lesen das Feld. v3-Akten in
  altem Code (rare Backwards-Path) → ignorieren das Feld.

- **`gui/main_window.py`** — Wenn AssignmentPage `unused_clips_mode`
  liefert, an `session` weitergeben vor Export.

### Technisches Risiko

**FCP7-Multi-Track-Compliance** — der Postprocess-Hack hat bewiesen,
dass Multi-Track-XML in Premiere importiert. Die Pflicht-Elemente
sind dokumentiert (DOCTYPE, sequence/timecode, sequence/format,
audio/format mit samplerate+depth, sourcetrack für Audio-Clips).
Risiko hier minimal.

**`enabled=FALSE` in FCP7-XML** — Standard-Attribut, Premiere
respektiert es. Resolve und FCP X verhalten sich ähnlich (zu
verifizieren in den Tests, aber kein Blocker).

**Schema-Migration v2 → v3** — additiv, kein Bruch. Risiko minimal
solange der Default-Wert konsistent ist.

**Audio-Mic-Fallback ohne Mix** — Kann Phasing in der NLE
reproduzieren. Status-Hinweis ist die Abmilderung; saubere Lösung
wäre Auto-Mix-Erzeugung (= eigener Roadmap-Punkt, Out-of-Scope hier).

---

## Tests-Plan (Vorschlag; Carl-Plan kann verfeinern)

### Multi-Track-XML-Struktur
- 1plus1-Setup (2 Personen × 1 Kamera + Totale) → 3 Video-Tracks
- HM-Setup (Matze weit + Gast weit + Gast close, keine Totale) →
  3 Video-Tracks, V1 = Matze weit (keine Totale-Fallback)
- HM-Setup mit hypothetischer Totale → 4 Video-Tracks
- 1 Person solo → 1 Video-Track (degenerierter Fall)

### Toggle-Modi
- **Remove-Modus** auf 1plus1-Setup: V1=Totale 243 Clips
  (durchgehend), V2=Jan ~121 Clips mit Lücken, V3=Tim ~122 Clips
  mit Lücken. KEIN `<enabled>FALSE</enabled>` im XML.
- **Disable-Modus** auf 1plus1-Setup: V1=Totale 243 Clips
  (durchgehend, enabled=TRUE), V2=Jan 243 Clips (121 enabled=TRUE,
  122 enabled=FALSE), V3=Tim 243 Clips (122 enabled=TRUE, 121
  enabled=FALSE). KEINE Lücken.

### Audio
- Mix vorhanden: 1 Audio-Track mit Mix als durchgehender Clip
- Mix nicht vorhanden: N Audio-Tracks mit Mics (heutiges Fallback-
  Verhalten, regression-locked)

### Pin-1 Schutz
- Keyboardstellen-XML byte-identisch vor/nach Slice (SHA-256-Hash
  als Pin)

### Persistenz
- Save/Load Roundtrip mit Schema-v3 inkl. `unused_clips_mode`
- v2-Akte laden → bootstrappt mit Default-Mode
- v3-Akte mit unbekanntem Mode-Wert → fallback auf Default + Warning

### Premiere-Verifikation (Akzeptanz, kein Unit-Test)
- 1plus1-Folge mit Multi-Track-Exporter neu generieren
- Vergleich zum Postprocess-Hack-Output von 2026-06-02 (sollte
  inhaltlich identisches Layout produzieren, evtl. mit kleinen
  Strukturunterschieden)
- Import in Premiere am echten Mac
- Max-Sichtung: Layout korrekt, V1-Totale-Fallback funktioniert,
  Audio sauber

---

## Carl-Briefing (für Max zum Weiterleiten)

Übergabe analog zu vorigen Specs:
1. Diese Spec lesen.
2. Plan im Stil der vorigen Carl-Pläne (Tasks, Files, Steps, TDD-Gate).
3. Besonderes Augenmerk:
   - **Pin-1 (Keyboardstellen-XML byte-identisch) explizit als Pin.**
   - **Schema-v3-Migration** sauber additiv, v1/v2-Akten weiter
     ladbar.
   - **`enabled=FALSE`-Spec-Konformität** für Disable-Modus —
     verifiziere FCP7-DTD-Sicht oder dokumentiere Premiere-
     Verhalten.
   - **Default-Mode-Entscheidung** vor Bauphase (Max-Entscheidung).
4. Plan zurück an Max → Claude verifiziert gegen Code → TDD-Bau Task-
   für-Task mit Carl-Gates.

---

*Spec-Pfad:* `docs/specs/2026-06-03-multitrack-folgenschnitt-xml-design.md`
