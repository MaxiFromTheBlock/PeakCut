# Plan: Web-Design-Gerüst (Fundament fürs Web-Frontend)

Status: Entwurf zur Carl-Plan-Review. Vier-Augen: Carl = Plan-Review + Gate, Claude = TDD-Bau, Max = Entscheider.
Datum: 2026-06-19

## 1. Ziel & Scope

Bevor irgendein Screen mit Leben gefüllt wird, kommt das **Fundament**: die Optik des
Redesigns + die App-Struktur als leere Hüllen ins Web-Frontend. Danach geht jeder echte
Screen schnell UND sieht sofort richtig aus.

**In Scope:**
- Zentrales **Design-System-Modul** (Farben/Schriften/Radien/Schatten/Abstände) aus dem
  Handoff sauber nachgebaut.
- **App-Shell**: Titelleiste + Navigation + die vier Seiten als leere Hüllen
  (Willkommen / Analyse / Zuordnung / Review) im Design-Look.
- Die bestehende, bewiesene **Read-only-Review** (Player + Audio-Master-Sync) in die
  Review-Hülle umziehen — nicht wegwerfen.

**Bewusst NICHT in Scope (eigene Pläne danach):** jede Screen-Fachlogik — Zuordnung
speichern, Review-v2-Smart-Panel, Untertitel, SRT, Reel/Overlay. Das Gerüst trägt noch
keine Produktlogik.

## 2. Design-Quelle

Handoff: `Design/redesign_handoff_2026-06-18/.../*.dc.html` + `support.js`. Das sind
**React-basierte Prototypen** auf einer Wegwerf-Laufzeit (`dc-runtime`, `window.React`).
Optik (CSS-Tokens, Layout, Struktur) ist die Wahrheit und überträgt sich sehr direkt auf
unser React-Web-Frontend. **Wir bauen die Komponenten sauber neu** (Tokens + Struktur als
Referenz), wir importieren NICHT die Prototyp-Laufzeit. Die Alt/Neu-Karte des Designers
(README §6) + die offenen Entscheidungen (DECISIONS A/I/J) sind die Spezifikation.

> Der Web-Schwenk löst die Designer-Frage „Fusion vs. nativer Mac-Stil" (DECISIONS §A)
> komplett auf — das war ein reines PyQt-Dropdown-Problem, im Web existiert es nicht.

## 3. Stack (Technik-Entscheidung — Claude legt fest, Carl prüft; NICHT Max)

Empfehlung: **Electron + React + TypeScript + Vite** (Carls geplanter Stack). Begründung:
das Design ist React-nah (direkte Übertragung), TypeScript fängt Verkabelungsfehler früh,
Vite ist schneller Standard. Alternative wäre, beim jetzigen Vanilla-JS zu bleiben — würde
aber bei jedem echten Screen Mehrarbeit + späteren Umbau bedeuten.

## 4. Harte Constraints (übernommen)

1. **Komplett offline** — Engine nur auf `127.0.0.1`, kein externer Call.
2. **Engine wird nur aufgerufen, nicht angefasst** — `web/engine/` bleibt unverändert.
3. **Pin-1** — Export läuft weiter über die unveränderten Python-Exporter; das Gerüst
   berührt keinen Export-Pfad.
4. **PyQt bleibt parallel lauffähig** — kein Abschalten in diesem Plan.
5. **TDD** — für das Frontend: Render-/Struktur-/Navigationstests + der bestehende
   selbst-verifizierende Review-Check; getrennte Test- und Commit-Schritte.

## 5. Slices (klein, je grün vor Commit)

- **G0 — App-Skelett:** Electron + React + TS + Vite neben der bestehenden Engine
  aufsetzen; `web/app` (Vanilla) behutsam dorthin überführen; dev-Start + Offline-Build
  laufen; ein Render-Smoke-Test ist grün.
- **G1 — Design-System-Modul:** Tokens (Farben/Schrift-Stacks/Radien/Schatten/Abstände)
  aus den `.dc.html` zentral als Theme; ein sichtbarer Token-Showcase zum Sicht-Abgleich;
  Test, der die Kern-Tokens (z. B. Azure `#0A6FE0`) prüft.
- **G2 — App-Shell + 4 leere Hüllen:** Titelleiste + Navigation + Willkommen/Analyse/
  Zuordnung/Review als leere Seiten im Design-Look; Navigationstest (Seitenwechsel),
  noch ohne Fachlogik.
- **G3 — Read-only-Review einhängen:** der bewiesene Player + Audio-Master-Sync zieht in
  die Review-Hülle; der bestehende Selbst-Check (review-report.json) bleibt grün.

## 6. Offene Punkte

**Technik — Claude entschieden, Carl prüft (nicht Max):**
- Stack: React + TS + Vite in Electron.
- Optik sauber **nachbauen** statt Prototyp-Laufzeit importieren.
- `web/app` **evolvieren** statt neuem Ordner.

**Produkt — Max entscheidet (erst nach dem Gerüst):**
- Reihenfolge der echten Screens: Review v2 (Kern/Wert) vs. Zuordnung
  (Migrations-Schleife).

## 7. Pfade & Repo (Carl-Gate #2)

| Was | Pfad |
|---|---|
| Python-App (PeakCut-Repo-Root) | `App/` (Remote `MaxiFromTheBlock/PeakCut`, Branch `feature/redesign`) |
| Web-App (Frontend) | `web/app/` |
| Engine (FastAPI-Brücke) | `web/engine/` |
| Design-Handoff | `Design/redesign_handoff_2026-06-18/...` |
| Pläne | `App/docs/plans/...` |

**Offener Punkt (Carl, technisch): `web/` ist aktuell NICHT versioniert.** Das
PeakCut-Repo wurzelt in `App/`; `web/` liegt als Geschwister außerhalb. Carls Gate
#4 (package-lock committed) braucht ein Repo für `web/`. Optionen: (a) `web/` als
eigenes Git-Repo (schnell, reversibel), (b) Monorepo — Repo-Root nach `PeakCut/`
heben bzw. `web/` ins App-Repo holen (ändert die in CLAUDE.md dokumentierte
Topologie). **Empfehlung: (a) jetzt, Konsolidierung zu (b) später möglich.**
Vor G0-Bau von Carl bestätigen lassen.

## 8. Carl-Gate-Schärfungen (verbindlich, P1)

1. **Legacy zuerst verriegeln:** vor dem React-Umbau muss der Vanilla-Selbstcheck
   grün stehen — `review-report.json`: `pass===true`, `drift_p95_ms<=100`,
   `peaks_loaded>0`, `mix_ok===true`. Der bewiesene Sync-Code wird als isoliertes
   Modul portiert (`src/review/syncController.ts`), nicht frei neu erfunden.
2. **Pfade explizit** (siehe §7).
3. **Electron-Sicherheit von Anfang an:** `contextIsolation:true`,
   `nodeIntegration:false`, `preload.ts`, kleine benannte Bridge-API. NICHT die
   Spike-Einstellungen (`nodeIntegration:true`) übernehmen.
4. **Dependency-Gate:** `package.json` mit Scripts `dev`/`build`/`test`/
   `test:render`/`verify:review`; `package-lock.json` committed; `node_modules` ist
   KEIN Liefer-Artefakt; später `npm ci` als reproduzierbarer Install. Offline =
   Laufzeit offline; Build-Abhängigkeiten dürfen existieren, müssen reproduzierbar sein.
5. **Tokens als Code:** `src/design/tokens.ts` + `tokens.css` + `DesignTokenShowcase`
   + Token-Test für Accent, Ink, Secondary, Border, App-BG, Card-BG, Card-Radius,
   Control-Radius, Mono-Font. `.dc.html` = Referenz, keine Abhängigkeit.
6. **Export/Engine/PyQt-Kern unberührt (Wand):** keine Änderung an
   `App/src/core/exporters.py`, `App/src/core/sinnabschnitt_exporter.py`,
   `App/src/gui/workers.py`, `App/src/core/session.py`; `web/engine/` unverändert.
7. **G3 = Player beweist sich erneut:** fertig erst, wenn der Review-Selbstcheck in
   der neuen Hülle grün bleibt — nicht „sieht eingebettet aus".

## 9. Definition of Done

G0–G3 grün (Frontend-Tests + Offline-Build + Review-Selbst-Check in der neuen Hülle);
alle Gates aus §8 erfüllt; Export/Engine/PyQt-Kern nachweislich unberührt; offline;
PyQt weiter lauffähig; Carl-Schluss-Review; Max sieht die 4 Hüllen im Design-Look +
die Review läuft synchron darin.
