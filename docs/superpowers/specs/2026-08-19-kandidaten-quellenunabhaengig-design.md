# Stellen quellenunabhängig machen — Design

> Status: **Gate A durch (Carl, 2026-08-19)**, Vertrag unten ist die Bau-Grundlage.
> Gate B = Vertragsfreeze nach Task 4. Danach erst Producer.
> Beteiligt: Max (Entscheider), Carl (Gates), Claude (TDD-Bau).

## Warum

PeakCut hat heute **genau einen Weg, einen Moment zu finden**: Matze tritt aufs Pedal.
Daran hängt alles — Review-Navigation, Screenshots, Sinnabschnitte. Folgen:

- Fremdproduktionen ohne Pedal liefern nichts Sinnvolles.
- Max' parallel entstehendes Werkzeug zur automatischen Clip-Findung müsste ein
  zweites Produkt neben PeakCut bleiben statt eine Quelle darin.
- Der Rückkanal „welche Stelle wurde wirklich benutzt" (= die Datengrundlage für den
  lernenden Score 2) ist an das Pedal gekettet.

## Max-Entscheide (2026-08-17/19)

1. **Der Fußtritt ist künftig nur EINE Quelle.** Weitere: transkriptweiter Finder,
   automatische Clip-Findung, von Hand im Review gesetzt.
2. **Eine Liste, Herkunft als sichtbares Etikett, filterbar.** Kein Zusammenlegen naher
   Stellen, kein „Automatik füllt nur Lücken" — Max will den Vergleich sehen
   (*hätte die Automatik dieselbe Stelle gefunden wie Matze?*).
3. **Automatische Vorschläge laufen immer bei der Analyse mit** (Entscheid trotz
   Kostenhinweis: ~Opus-Größenordnung je Folge).
4. **Die neue Oberfläche soll die PyQt-App ersetzen** (17.08.) — der Vertrag muss
   also für beide Oberflächen taugen, nicht nur für PyQt.

## Architektur

### Zwei Listen, getrennte Aufgaben

| Liste | Rolle |
|---|---|
| `session.peaks` | **unverändert**: ausschließlich Marker-/Pedaltritte |
| `session.clip_candidates` | **die allgemeine Stellen-Liste**, aus allen Quellen |

Das Review navigiert künftig über die Kandidatenliste, nicht über `peaks`.

### Warum Pin-1 dabei strukturell nicht betroffen ist

- `core/exporters.py` (Keyboardstellen MP3/TXT/XML) geht über
  `session.get_active_peaks()` → liest `session.peaks`. Unberührt.
- `core/folgenschnitt_exporter.py` fasst weder `peaks` noch `clip_candidates` an
  (arbeitet über Sprecher-Aktivität + Zuordnung). Unberührt.
- **Ausnahme, die einen echten Riegel braucht:** `core/sinnabschnitt_exporter.py` liest
  über `xml_sequence_helpers.active_smart_candidates` sehr wohl Kandidaten. Siehe unten.

Es braucht also für zwei von drei Exportern **keine Filterregel, die richtig
geschrieben sein muss** — die Liste, aus der exportiert wird, wird nicht angefasst.

## Datenvertrag (Carl-Gate A)

```python
ClipCandidate(
    candidate_id: str,          # eigenständige, stabile Identität
    origin: str,                # Entdeckungsquelle
    anchor_ms: int,             # Position, an die das Review springt
    peak_id: int | None,        # nur optionale Rückreferenz für markergebundene
    boundary: ClipBoundary,
    status: str,
    transcript_excerpt: str,
    reason: str,
    score: float | None,
)
```

### `anchor_ms` — warum eigenes Feld

`boundary.start_ms` darf **nicht still zum Navigationsanker werden**. Bei einer
Marker-Stelle sitzt der eigentliche Tritt häufig **mitten** in der Grenze (Matze tritt,
*nachdem* etwas Gutes gesagt wurde). Ohne eigenes Feld spränge die Review-Navigation
bei allen bestehenden Folgen an die falsche Stelle — eine sofort sichtbare Regression.

### `origin` — Werte und eine wichtige Abgrenzung

`marker` · `transcript` · `auto` · `manual`

- **Datenbegriff `marker`, nicht `pedal`:** Das Gerät hat bereits gewechselt (seit zwei
  Folgen Kickdrum statt Keyboard). Das UI-Label darf „Pedal" heißen; der Datenbegriff
  bleibt geräteunabhängig. Deckt sich mit Max' Entscheid vom 2026-06-20
  („Keyboard" → „Marker" überall).
- **Die heutige Smart-Grenzen-Berechnung erzeugt KEINEN `transcript`-Origin.** Sie
  verbessert nur die `boundary` eines Marker-Kandidaten. Origin bleibt `marker`.
  Erst ein **transkriptweiter, eigenständiger Finder** erzeugt `origin="transcript"`.
- **Bewusst nicht `source`:** Das Wort ist in `PeakDecision.source` belegt und bedeutet
  dort „**wer** hat entschieden" (`manual` vs. automatisch). Andere Bedeutung —
  Doppelbelegung, die in einem halben Jahr niemand mehr auseinanderhält.

### Identitätsraum

Eigener Kandidatenraum ist Pflicht:

| Herkunft | `candidate_id` |
|---|---|
| Altbestand / Marker | `marker:<peak_id>` |
| Manuell | UUID bzw. persistent erzeugte ID |
| Auto / Transkript | stabile detektor-eigene ID |

**Nicht aus der `boundary` hashen** — eine Grenzkorrektur darf die Identität nicht
ändern. **Gleicher Zeitpunkt aus zwei Quellen ergibt zwei Kandidaten**; genau das ist
der von Max gewünschte Vergleich.

### `CandidateDecision` (ersetzt `PeakDecision`)

`transition()` schreibt heute zwingend `candidate.peak_id` in die Decision
(`clip_candidates.py:126`) — das funktioniert für Nicht-Marker-Kandidaten nicht.

- Decision trägt künftig `candidate_id`.
- `source` bleibt der **Entscheider/Akteur** (unverändert in Bedeutung).
- Klasse perspektivisch `CandidateDecision`.
- Akten v1–v5 werden beim Laden migriert: `peak_id` → `candidate_id = marker:<peak_id>`.

### Sinnabschnitt-Riegel (die eine echte Leck-Stelle)

`xml_sequence_helpers.active_smart_candidates` filtert heute:

```python
status != DISCARDED and score is not None and peak_id in number_map
```

Fremdquellen fallen also **nur zufällig** raus — weil ihre `peak_id` nicht in der aus
`peaks` gebauten Nummernkarte steht. Bei ungünstiger Nummernvergabe kollidieren die IDs
und Fremdquellen lecken in die Sinnabschnitt-XML. Künftig ausdrücklich:

```python
c.origin == ORIGIN_MARKER
and c.peak_id is not None
and c.peak_id in number_map
and c.score is not None
and c.status != DISCARDED
```

**Kollisionstest (Pflicht):** einem `auto`-Kandidaten absichtlich dieselbe Legacy-
`peak_id` wie einem aktiven Peak geben und beweisen, dass er **nicht** in
„Keyboardstellen smart" landet. Der Filter schützt die Export-Bedeutung,
`candidate_id` schützt die allgemeine Datenintegrität — beides, nicht eins davon.

## Fehlerfälle

- Eine Quelle, die scheitert, darf die Analyse **nicht** beenden — dasselbe Muster wie
  die Sprecher-Analyse heute (`try/except`, degradieren statt abbrechen).
- Jede Quelle meldet ihren eigenen Zustand über `results["skipped_steps"]`
  (Schritt → Grund), damit die Oberfläche ehrlich sein kann
  („Vorschläge nicht verfügbar: kein Transkript").
- Die **Wahrheit über Fähigkeiten** bleibt `core/project_capabilities.py`.
  `skipped_steps` ist ein flüchtiger Laufbericht und wird **nicht** persistiert.

## Projektakte

Schema **v5 → v6**, additiv. Alte Akten lesen sich unverändert (Migration siehe
`CandidateDecision`). Wandert **sofort auf alle drei Zweige** — die v4/v5-Falle vom
17.08. darf sich nicht wiederholen.

## Bau-Reihenfolge (Carl)

| Task | Inhalt |
|---|---|
| 0 | Pin-1, bestehende Smart-XML und v5-Roundtrip verriegeln (Netz VOR dem Umbau) |
| 1 | `candidate_id`, `origin`, `anchor_ms`, optionales `peak_id` |
| 2 | `CandidateDecision` + v1–v5-Migration |
| 3 | Schema v6 + vollständiger Nicht-Marker-Roundtrip |
| 4 | Expliziter Origin-Riegel im Smart-Exporter + Kollisionstest |
| **Gate B** | **Vertragsfreeze** |

Danach getrennt und je mit eigenem Entwurf: manueller Producer, Auto-Finder,
transkriptweiter Finder. **Zuletzt** die Review-Navigation von Peak-Index auf
`candidate_id` umstellen.

## Test-Anforderung an Gate A

Das Fundament darf **nicht nur theoretisch** getestet werden. Ein synthetischer bzw.
manueller Nicht-Marker-Kandidat muss den vollständigen Datenweg durchlaufen:

1. erzeugen
2. nach `anchor_ms` sortieren
3. Statusübergang über `candidate_id`
4. v6 Speichern/Laden exakt
5. Origin-Filter greift
6. **keine Leckage** in Keyboardstellen- und Sinnabschnitt-XML
7. Pin-1 unverändert

## Ausdrücklich NICHT in diesem Slice

- **Transkriptweites Finden.** Die heutige Pipeline stürzt bei null Peaks nicht ab
  (`clip_boundary/pipeline.py:98` steigt sauber aus), erzeugt aber auch nichts.
  Transkriptweites Finden ist echte neue Produktlogik → eigener Slice.
- **Review-Fenster ohne Marker** (Oberfläche) und **Reel-/Clip-Fenster**
  (`Design/redesign_handoff_2026-06-18/Reel & Overlays.dc.html`, inkl. Marken-Profil
  und editierbarem XML-Export) — eigene Teilprojekte, hängen an diesem Fundament.
- **Desktop/Web öffnen.** Der Desktop stoppt bei null Stellen, die Web-Oberfläche
  blockiert im Preflight. Beides bewusst noch zu.
