# Cutter-Feedback Alex — PeakCut (Mai 2026)

> **Was ist das?** Archiv zweier Artefakte von Cutter **Alex**, die Max im Mai 2026
> erreichten und sonst nur auf seinem Desktop lagen. Hier gesichert, damit die
> Erkenntnisse nicht verloren gehen und die Originaldateien gelöscht werden können
> (Alex hat die Originale ohnehin — der Skill ist seiner).
>
> - **A) Sprachnachricht 19.05.2026** — Alex' Take zu PeakCut (Folgenschnitt + Tool-Vision).
> - **B) Skill `hotel-matze-editing-markers`** (datiert 06.05.2026) — Alex' eigenes
>   Claude-Werkzeug für **seinen** Schnitt, NICHT für PeakCut. Wertvoll daran sind nur
>   seine **Marker-Benennungs-Regeln** (redaktionelle Urteils-Schule).
>
> Transkribiert/eingeordnet/archiviert 29.06.2026. Quelle einen Monat alt — der
> Abgleich „was ist seitdem schon passiert" steht unten in der Tabelle.

---

## A) Sprachnachricht (19.05.2026) — Alex' Take zu PeakCut

### Wörtliches Transkript

> Also die Qualität der XML ist sehr gut. Die Frequenz beim Matze ist auch sehr gut.
> Die Schnittfrequenz beim Matze könnte noch etwas höher sein. Also wenn er nur ja
> oder aha oder so sagt, nicht immer, aber so ein paar Mal, könnte er da noch
> reingeschnitten werden.
>
> Und die Kamera des Gastes, die Close-Up des Gastes kann noch häufiger reingeschnitten
> werden. Aktuell ist ja so alle fünf Minuten oder sowas drin, würde ich schätzen, aus
> meinem Gedächtnis her. Aber sie kann ruhig alle zwei Minuten oder einmal die Minute
> fast schon reingeschnitten werden, wenn die Person spricht, sodass es einfach
> generell mehr Dynamik kriegt.
>
> Generell für das Tool, was ich mir vorstelle in Zukunft, was cool wäre, um auch den
> Real-Workflow [Reel-Workflow] mit einzubinden: wenn man mehrere Pages hat, von der UI
> her. Das heißt, auf der Mainpage, wenn man das PeakCut öffnet, hat man die Zuordnung
> der Kameras mit den Personen und auch der Audios mit den Personen etc. Wenn man dann
> weitergeht, hat man die Highlightstellen auf der nächsten Page, so wie jetzt gehabt.
> Auf der nächsten Page hat man dann den Schnitt von der Folge, so wie sie jetzt auch
> ist, nur mit den Anpassungen, die ich gerade genannt habe. Und dann auf der nächsten
> Page sind Reel-Stellen.
>
> Das heißt, wir kriegen immer Stellen, die aber auch mit den Highlightstellen verknüpft
> werden können. Der Kunde sagt beispielsweise: ich hätte gerne Reel-Stelle 5, 9, 13 und
> 15. Wir haben ja bei dem Schnitt der Folge auch das Transkript angehangen, sodass im
> Radius der Reel-Stelle nach einem inhaltlich passenden Reel-Inhalt geschaut wird und
> dieser dann automatisch herausgeklickt wird. Dann in diesem Reel-Abteil kann man auch
> sagen: ich möchte gerne ein Logo einfügen, ich möchte gerne Untertitel in diesem Stil.
> Das muss da auch alles festlegbar sein. Sodass man dann am Ende eine fertige MP4 mit
> Untertiteln im Idealfall — und als SRT eingebrannt, und ein MP4 clean und/oder
> eingebrannt mit Untertiteln — bekommt. Das wäre geil.

### Die vier Punkte

1. **XML-Qualität sehr gut.** (Klares grünes Cutter-Signal.)
2. **Matze-Schnittfrequenz gut, dürfte etwas höher sein** — auf reine „ja/aha"-
   Reaktionen ruhig öfter reinschneiden (nicht immer, aber häufiger).
3. **Gast-Close-up öfter** — aktuell gefühlt alle ~5 Min, dürfte alle 1–2 Min sein,
   wenn der Gast spricht → mehr Dynamik.
4. **Tool-Vision = Tabs/Mehrseiten-Flow:** Zuordnung (Kameras↔Personen, Audios↔Personen)
   → Highlightstellen → Folgenschnitt → **Reel-Seite**: Kunde wählt Reel-Stellen per
   Nummer (verknüpft mit den Highlightstellen), das Tool sucht im Umkreis über das
   angehängte Transkript den passenden Inhalt + Logo + Untertitel-Stil → Output: fertige
   MP4 (eingebrannte Untertitel), sauberes MP4, SRT.

### Abgleich mit heute (29.06.2026 — Quelle war einen Monat alt)

| Alex' Punkt | Status |
|---|---|
| **P4: Tabs/Mehrseiten-UI** (Zuordnung → Highlightstellen → Folgenschnitt) | 🟢 **Genau der Web-Umbau, der gebaut wurde** (Bestätigen → Zuordnung → Keyboardstellen → Folgenschnitt). Alex hat unabhängig die Architektur beschrieben, die jetzt steht — Richtungs-Bestätigung. |
| **P2 + P3: Schnittrhythmus** (öfter auf „ja/aha", Close-up alle 1–2 Min statt ~5) | 🟡 **OFFEN, actionable.** Das sind Tuning-Werte für **Folgenschnitt Stufe 2** (Verdichtung/Kamera-Rotation). Die Mechanik steht, die Kalibrierung in diese Richtung noch nicht. Konkretes Cutter-Kalibrier-Feedback — der eigentliche Grund, diese Notiz zu behalten. |
| **P1: XML gut** | 🟢 Durch echte Eigen-Produktionen (Philip Siefer, Ilka) mehrfach überholt/bestätigt. |
| **P4: „Reel-Seite"** (Logo, Untertitel, SRT, fertige MP4) | 🔵 Das ist das **Social-/Opus-artige Modul** — bewusst **spät** auf der Roadmap. Untertitel/SRT geparkt. Publishing-Nähe, wo der Wettbewerbsvorteil laut Strategie verwässert. |

---

## B) Skill `hotel-matze-editing-markers` — Alex' eigenes Werkzeug

**Wichtig:** Das ist Alex' Tool für **seinen** Schnitt, **kein** PeakCut-Feature und
laut eigener Beschreibung **NICHT** der YouTube-Kapitelmarker-Skill (dafür hat er einen
separaten `hotel-matze-chapter-markers`).

**Was es macht:** nimmt ein Hotel-Matze-Transkript (Word), bündelt das Gespräch in
**15–20 inhaltliche Schnitt-Marker**, schreibt eine **editingtools.io-Excel** (Spalten
`Timecode In` / `Comment`, optional PDF), die Alex in **DaVinci Resolve** importiert. Die
Marker kommen aus dem **Transkript-Inhalt**, ohne Fußpedal-Peaks. (Timecode-Konvention:
erster Marker bei 00:08–00:12, weil das Recording vor dem Gespräch startet → eher
Roh-/Vollmaterial-Timeline.)

**Produkt-Signal:** Alex schneidet in **DaVinci über editingtools.io**, nicht in
Premiere. PeakCut exportiert FCP7-XML (DaVinci kann das lesen); so eine leichte
Marker-Tabelle wäre ein anderer, simplerer Weg — relevant, falls PeakCut Alex als Cutter
direkt bedienen soll.

### Das eigentlich Wertvolle: Alex' Marker-Benennungs-Regeln

Operationalisierte redaktionelle Urteils-Schule — **Vorlage für die
Sinnabschnitt-Benennung und das geparkte Prompt-Tuning (#70).** Vor Übernahme in den
Decider: 4-Augen mit Carl.

- **Inhaltlich, nicht meta.** Was wird gesagt? Welches Bild, Beispiel, Argument?
- **Kurz** — meist 2–6 Wörter. Bei zentralen Fragen darf ein ganzer Satz stehen.
- **Konkret.** Gute Beispiele: „Beispiel Singen", „120 Sorten Grün", „Möhren sähen",
  „Hierarchisches Ordnungssystem 10.000 Jahre", „Spatz in der Hand", „Klo putzen".
- Bilder/Beispiele **mit dem Trägerwort**: „Beispiel <Name>".
- **Verboten:** „Highlight", „interessant", „spannend", „gut", „wichtig", „!!!", „check",
  Werturteile („starke Stelle"), Gast-Name allein („Hüther sagt…" — Person ist klar, es
  geht um den Inhalt), lange Zitate/ganze Sätze aus dem Transkript.
- Faustregel Anzahl: 15–20 über die Episode, nie unter 10 / über 25; ~1 Marker je
  8–12 Min Sprechzeit, aber inhaltsgetrieben (dichter bei Beispielsalven).
- Stil = Substantive ohne Verben, lockerer Ton; bestehende Marker exakt spiegeln.

### Skript-Inhalt (zur Vollständigkeit)

Zwei triviale, generische Bauteile — voll re-derivierbar, kein Wissen geht verloren:
- `build_marker_xlsx.py` — nimmt `[(timecode, comment), …]`, schreibt die
  editingtools.io-Excel (openpyxl, Sheet „Worksheet", Header + 2 Spalten).
- `build_marker_pdf.py` — gleiches Input → A4-PDF mit Tabelle (Header, alternierende
  Zeilenfarbe, Helvetica; reportlab).

---

## Was damit zu tun ist (nichts Dringendes)

- **P2/P3 Schnittrhythmus** → wenn Folgenschnitt-Stufe-2-Tuning drankommt, dieses
  Feedback als Kalibrier-Richtung mitnehmen (mehr Dynamik: öfter auf „ja/aha", Close-up
  dichter). Nicht jetzt — Energie liegt auf dem Import/Web-Umbau.
- **Marker-Stil-Regeln** → Vorlage für #70 / Sinnabschnitt-Benennung, vor Decider-Einsatz
  mit Carl gegenlesen.
- Originaldateien (`hotel-matze-editing-markers.skill`, `WhatsApp Audio …19.5… .opus`)
  können nach dieser Sicherung gelöscht werden.
