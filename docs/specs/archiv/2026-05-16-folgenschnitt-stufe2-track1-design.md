# Design: Folgenschnitt Stufe 2 / Track 1 — Close & weitere Kameras per Zeitlogik

*Stand: 2026-05-16 · Status: Design, noch NICHT in Umsetzung · Folgefeature zu Folgenschnitt Stufe 1*

---

## Für externe Reviewer: Kontext

PeakCut (Python/PyQt6, macOS) erzeugt für den Podcast „Hotel Matze" einen
automatischen Rohschnitt als FCP7-XML. **Stufe 1** (gebaut, in echter App
validiert, cutter-gelobt: 304 Schnitte „extrem stark") schneidet rein
sprecherbasiert: wer spricht → seine **Weit**-Kamera, reaktiv an
Sprecherwechseln/Einwürfen. Code: `core/folgenschnitt_decisions.py`
(`build_speaker_turns` → `build_edit_decisions`), Datenmodell generisch
(`CameraAssignment(path, shot_type, person|None)`; Shot-Typen
`weit/nah_close/halbnah/totale/unused`). Stufe 1 nutzt nur `SHOT_WIDE`;
Close/Halbnah/Totale werden zugeordnet, aber nie geschnitten.

**Problem:** Redet eine Person lange am Stück, erzeugt Stufe 1 *einen
statischen Block* auf ihrer Weit-Kamera. Der Cutter (Alex) wünscht
ausdrücklich die dritte Kamera im Schnitt. Außerdem: nächste Woche eine
**Nicht-HM-Produktion** mit Totale, die mit PeakCut getestet werden soll —
das Tool muss für *jede* Kamera-Kombination eine valide XML liefern.

---

## Zwei-Gleise-Rahmen (Max-Entscheidung)

- **Track 1 (DIESES Spec): deterministische Zeitlogik.** Schnell,
  testbar, vorhersehbar. Liefert jetzt die Mehr-Kamera-Auflockerung.
- **Track 2 (eigenes späteres Spec): AI/Transkript-Regisseur.** Claude-API
  entscheidet inhaltsgetrieben (Emotion/Spannung/Themen-Tiefe; Totale bei
  schnellem Sprecherwechsel). Läuft parallel, blockiert Track 1 nicht,
  **nicht Teil dieses Spec**.

---

## Ziel

Lange Ein-Personen-Blöcke deterministisch auflockern, indem zwischen den
zugeordneten Kameras gewechselt wird — produktionsunabhängig, für jede
Kamera-Kombination eine valide XML, ohne Stufe 1 zu verändern.

---

## Architektur — Auflockerungs-Schicht + austauschbare Strategie

Track 1 ist **keine Änderung an Stufe 1**, sondern eine Schicht *darüber*:

1. Stufe 1 erzeugt wie bisher die `EditDecision`-Liste (Sprecher → Weit,
   reaktiv). **Unverändert** — die cutter-gelobte 304-Schnitt-Charakteristik
   bleibt exakt erhalten.
2. Eine **Auflockerungs-Strategie** bekommt diese Decisions + die
   `CameraAssignment`s und unterteilt *nur* lange Ein-Personen-Blöcke.
   Kurze Blöcke / Sprecherwechsel bleiben unangetastet.
3. Die Strategie ist hinter einer klaren Schnittstelle gekapselt. Track 1
   liefert die **Zeitlogik-Strategie**. Track 2 (AI) wird später eine zweite
   Strategie hinter *derselben* Schnittstelle — **eingesteckt, nicht
   nachgebaut**.

Eigene Datei (z. B. `core/folgenschnitt_loosening.py`), klar getrennt von
`folgenschnitt_decisions.py`. Schnittfunktion erhält die Stufe-1-Decisions,
gibt eine verfeinerte Decision-Liste zurück.

---

## Zeitlogik-Verhalten (Track 1)

Gilt nur für einen langen Block **derselben sprechenden Person** (aus
Stufe-1-Decision; ein Block = eine Person, eine Kamera, ohne
Sprecherwechsel darin):

- **Rotation** durch die der Person zugeordneten *Einzel-Kameras*
  (`weit`, `nah_close`, `halbnah` mit `person == Sprecher`).
- **Große, ausgewogene Blöcke** — *nicht* „Weit-Basis mit kurzen
  Close-Pops". Close/Halbnah dürfen genauso lange stehen wie Weit.
- **Ruhig beginnend, progressiv etwas dichter:** langer erster Block, danach
  dürfen die Blöcke etwas kürzer werden — **harter Mindest-Block als
  Deckel** (nie kürzer).
- Hat die Person nur **eine** Einzel-Kamera (HM-Matze: nur Weit) → keine
  Rotation, Block bleibt statisch (= heutiges Verhalten).
- Ist der Block kürzer als die Start-Schwelle → unverändert (Stufe 1 reicht).

### Totale (personenunabhängig): Establishing-Block + Fallback

- **Establishing/Atempause:** während langer Stücke klinkt sich die Totale
  periodisch als eigener Block ein (unabhängig vom Sprecher).
- **Fallback:** hat eine sprechende Person *keine* Einzel-Kamera, läuft ihr
  Block auf die Totale. Garantiert: jede Kombination → valide XML.
- Die *inhaltsgetriebene* Totale-Nutzung (z. B. „schneller Sprecherwechsel →
  Totale") ist **Track 2**, nicht hier.

---

## Generalitäts-Garantie

Track 1 erzeugt für **jede** Kamera-Zuordnung eine valide XML:

- nur Totale + Mics → alles Totale
- Totale + Weit → Weit-Block + periodische Totale
- Weit + Close (+ Halbnah) → Rotation + ggf. Totale
- nur eine Einzel-Kamera → statisch (wie heute)
- gar keine schneidbare Kamera → Folgenschnitt entfällt sauber (bestehende
  Leitplanke), **Keyboardstellen-Export bricht NIE** wegen Folgenschnitt.

---

## v1-Parameter & Tuning-Loop

Mechanismus jetzt; konkrete Zahlen als **tunebare v1-Defaults**, bewusst
provisorisch. Benannte Parameter:

| Parameter | Bedeutung |
|---|---|
| `min_block_to_loosen_ms` | ab welcher Block-Länge überhaupt rotiert wird |
| `first_block_ms` | Länge des ruhigen ersten Blocks vor dem ersten Wechsel |
| `target_block_ms` | typische Block-Länge danach |
| `densify_factor` | wie stark „progressiv dichter" (Richtung `min_block_ms`) |
| `min_block_ms` | **harter** Mindest-Block (Deckel) |
| `totale_interval_ms` / `totale_block_ms` | Takt & Länge der Establishing-Totale |
| `rotation_order` | bei ≥3 Einzel-Kameras: Reihenfolge **— offen, s. u.** |

Werte werden fundiert aus einer **Premiere-Final-Cut-Pro-XML einer
fertigen Folge** (Alex, ersatzweise Lukas) abgeleitet — Carl-Urteil:
genauer als alles andere und exakt PeakCuts Zielformat. Daraus: Cliplängen
Video-Track 1, Cuts/Min, Median/P25/P75, Verlauf pro 5-Min-Bucket, optional
Kamerawechsel-Matrix (falls Clipnamen/Tracks die Kamera erkennen lassen).
EDL nur als Backup (simpler, weniger Metadaten). yt-dlp+ffmpeg-Szenenanalyse
**verworfen** (YouTube PO-Token-Sackgasse, ungenau — nicht investieren).
Final justiert über einen **Cutter-Fragenkatalog**, der mit der ersten
Track-1-XML an Alex geht. Der Mechanismus liefert v1-Defaults aus; Tuning
ändert nur Zahlen, nicht die Logik.

---

## Tests

- Deterministische Zeitlogik → strikt TDD, reine Funktionen.
- **Stufe-1-Regressions-Wächter:** wo nichts aufzulockern ist (kein langer
  Ein-Personen-Block; nur eine Kamera; reine Weit-Zuordnung), muss die
  Decision-Liste **identisch** zu heute bleiben (die cutter-gelobten 304
  Schnitte dürfen sich nicht verschieben).
- Generalitäts-Tests: jede Kamera-Kombi → nicht-leere, valide Decisions
  bzw. saubere Leitplanke.

---

## Bewusst NICHT in diesem Spec

- Track 2 / AI: inhaltsgetriebene Schnitte (Emotion/Spannung/Themen-Tiefe),
  Totale bei schnellem Sprecherwechsel, Transkript-Pipeline, Claude-API.
- Kamera-*Identität* aus dem Video erkennen.
- Änderungen an Stufe-1-Logik, Datenmodell oder Leitplanke.
- UX-Gesamtumbau, Resolve-Relink.

---

## Offene Punkte für Carl / nächste Runde

- **`rotation_order` bei ≥3 Einzel-Kameras:** stur reihum
  (Weit→Close→Halbnah→…) oder Weit als „Anker" zwischen den anderen? In der
  Abnahme gestellt, von Max noch nicht entschieden — als Parameter offen
  halten, Default-Vorschlag mit den v1-Zahlen.
- Konkrete v1-Zahlen: ausstehend bis EDL/ffmpeg-Analyse vorliegt.
- Wie genau ein „langer Ein-Personen-Block" aus den Stufe-1-Decisions
  erkannt wird (Schwelle, Umgang mit knapp aufeinanderfolgenden gleichen
  Sprechern) — Plan-Detail für Carl.

---

## Erfolgskriterium

Aus der App kommt für eine lange Gast-Passage eine XML, in der sich Weit/
Close (/Halbnah) in großen, ausgewogenen Blöcken abwechseln + periodische
Totale, während kurze Passagen/Sprecherwechsel exakt wie die gelobte
Stufe-1-Version bleiben — und jede beliebige Kamera-Kombination (inkl. reine
Totale der Fremdproduktion) liefert eine valide XML, ohne dass die
Keyboardstellen je gefährdet sind.
