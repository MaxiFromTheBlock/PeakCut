# Roadmap #2 — ClipCandidate + Rückweg-Modell (Spec)

**Status: Spec/Design — noch NICHT in Umsetzung. Bau-Basis ist Carls
Umsetzungsplan, nicht diese Spec.**

**Herkunft:** Festgeschriebene Produkt-Strategie & Roadmap (Carl/Claude-
2-Pass-Konsens, Max-abgenommen), Punkt 2 — direkt auf dem fertigen
HC-4-Fundament (`.peakcut`-Projektakte). Ersetzt die alte HC-5-
Nummerierung; maßgeblich ist die Roadmap in CLAUDE.md.

## Problem (Warum)

Heute ist jeder Keyboard-Peak nur „Position + ±15 s starres Fenster".
Der echte redaktionelle Weg ist: nicht jede Stelle wird produziert —
jemand wählt aus, daraus werden Clips, manche veröffentlicht, manche
laufen gut. Dieses Wissen (welche Stelle → was wurde draus → wie lief
es) hat PeakCut nirgends. Carl + Claude unabhängig: genau dieser
**Rückkanal aus echter redaktioneller Auswahl** ist der Burggraben,
den Opus-artige Tools strukturell nicht haben. HC-4 gab das Gedächtnis;
hier kommt das erste echte Produktobjekt hinein, das darin lebt.

## Ziel (Was)

Ein **ClipCandidate** als erstklassiges, persistentes Objekt mit
Status-Lebenszyklus, plus ein **peak_decisions**-Rückkanal — beides
additiv in der `.peakcut`-Akte. Damit kann PeakCut künftig (spätere
Roadmap-Punkte) sinnvolle Grenzen vorschlagen (#3), Profile anwenden
(#4) und einen Score lernen — aber *hier* wird nur das Datenmodell +
der Lebenszyklus + die Persistenz gebaut, nichts davon.

## Andockpunkt (verifiziert, de-riskt den Plan)

`project_archive.py` (HC-4): Pflichtsektionen sind nur
`project/analysis_results/assignments`; `parse_archive_payload`
**ignoriert unbekannte Sektionen** (Task-0-Test bewiesen) und toleriert
Schema-Versionen vor/rückwärts. → ClipCandidate dockt als **neue
additive Top-Level-Sektion** an (`clip_candidates`, optional
`peak_decisions`-CSV/JSON-Referenz analog `speaker_activity_csv`),
`CURRENT_SCHEMA_VERSION` 1→2. Alte Akten ohne die Sektion: ClipCandidates
werden aus den Peaks gebootstrappt. Keine HC-4-Vertragsänderung, nur
additive Erweiterung — genau wofür die Versionierung gebaut wurde.

## Datenmodell

`ClipCandidate` (frozen dataclass, `core/`):
- `peak_id: int` — = Peak.index (in der Akte eingefroren, stabil)
- `boundary: {start_ms:int, end_ms:int}` — v1 = die in/out-Punkte des
  Peaks (smarte/KI-Grenzen sind Roadmap #3, hier NICHT)
- `transcript_excerpt: str = ""` — leer in v1 (#3 füllt)
- `reason: str = ""` — leer in v1
- `score: float | None = None` — None in v1 (Score braucht Minibar-
  Feedback, späterer Roadmap-Punkt)
- `status: str` — Enum-artig: `proposed` → `selected` → `produced`
  → `published` → `discarded`
- `to_dict`/`from_dict` (Round-Trip-exakt, wie Peak/Assignment)

Bootstrap: pro nicht-ignoriertem Peak ein ClipCandidate `proposed`;
ignorierte Peaks → `discarded` (oder kein Candidate — Carl entscheidet
im Plan, s. Schwierigkeiten).

`peak_decisions`: append-only Log redaktioneller Entscheidungen
(peak_id, neuer Status, Zeitstempel) — der Rückkanal-Rohstoff. v1
schreibt nur die Status-Übergänge mit; Performance-Daten (Views etc.)
sind ein **späterer** Roadmap-Punkt, hier NICHT.

Pure Status-API in `core/` (legale Übergänge erzwungen), Qt-frei.

## Umfang / Nicht-Ziele

- **In Scope:** ClipCandidate-Datenmodell + Status-Lebenszyklus (pure,
  legale Übergänge), Persistenz additiv in `.peakcut` (schema v2,
  vor/rückwärts-tolerant), Bootstrap aus Peaks, `peak_decisions`-Log
  der Status-Übergänge, Round-Trip-exakt, Save/Load über die HC-4-
  Mechanik.
- **Nicht-Ziel (= spätere Roadmap-Punkte, eigene Specs):** smarte/KI-
  Clip-Grenzen (#3 — boundary bleibt = Peak in/out), Virality-Score-
  Modell + Minibar/Performance-Ingestion (braucht Feedback, später),
  jegliches UI/Hub (#6), Profile (#4).
- **Nicht-Ziel:** keine Änderung an Analyse, Folgenschnitt-Pipeline,
  Exporter, cutter-validierter Ausgabe, Leitplanke.

## Harte Randbedingungen

1. **Additiv & risikolos:** ohne `clip_candidates`-Sektion verhält
   sich PeakCut exakt wie heute; alte `.peakcut` (schema 1) laden
   weiter (Bootstrap). Leitplanke unangetastet.
2. **HC-4 Gate F bleibt:** Keyboardstellen-XML byte-identisch nach
   Save/Load — ClipCandidate ist Metadaten, **darf den Export nicht
   beeinflussen** (Regressionswächter grün).
3. **Round-Trip-Exaktheit:** gespeicherte + neu geladene ClipCandidates
   (peak_id, boundary, status, decisions) bit-genau zurück.
4. **Schema-Migration tolerant:** v1-Akte ohne Sektion → sauberer
   Bootstrap; v2-Akte in älterem Code → kein Crash (HC-4-Mechanik).
5. Qt-frei bleibt Qt-frei (`core/`).

## Akzeptanzkriterien

- Frische Analyse → pro nicht-ignoriertem Peak ein ClipCandidate
  `proposed`; Status-Übergang (z. B. → `selected`) wird im
  `peak_decisions`-Log festgehalten.
- Save → Load → ClipCandidates + decisions bit-identisch; illegaler
  Status-Übergang wird abgelehnt.
- Alte `.peakcut` (schema 1, ohne Sektion) lädt, ClipCandidates werden
  aus Peaks gebootstrappt; neue Akte ist schema 2.
- Keyboardstellen-XML byte-identisch vor/nach (HC-4 Gate F unverändert
  grün); volle Suite grün.

## Bekannte Schwierigkeiten (Carl im Plan adressieren)

- **peak_id-Stabilität:** = Peak.index. Innerhalb einer Akte
  eingefroren (HC-4), aber bei *Neu-Analyse desselben Materials* könnten
  Indizes wandern. Strategie benennen (an Akte gebunden? Re-Analyse =
  neue Candidates?).
- **Bootstrap-Policy ignorierter Peaks:** `discarded`-Candidate vs.
  kein Candidate — Konsistenz mit Folgenschnitt/Export bedenken.
- **peak_decisions Speicherort/-form:** inline JSON vs. referenzierte
  Datei (analog `speaker_activity_csv`); append-only-Semantik.
- **Legale Status-Übergänge:** welche Übergänge erlaubt/rückgängig
  (z. B. `published` → `discarded`?), wie im Plan testen.

## 4-Augen-Prozess

Spec (Claude) → **Max-Read-Gate** (i. d. R. an Claude delegiert:
Selbst-Gate-Review + Flag) → Carl schreibt den Umsetzungsplan
(Bau-Basis) → Claude verifiziert Carls Plan gegen den echten Code +
baut TDD → Gates wie von Carl gesetzt → Max entscheidet Merge. Kein Bau
vor Carls Plan.
