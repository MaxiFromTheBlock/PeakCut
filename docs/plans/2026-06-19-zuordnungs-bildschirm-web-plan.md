# Plan: Web-Zuordnungs-Bildschirm fuer PeakCut

Status: Entwurf zur Carl-Plan-Review. Vier-Augen: Carl = Plan-Review + Gate-Reviews, Claude = TDD-Bau, Max = Entscheider.
Datum: 2026-06-19

## 1. Ziel und Scope

Der Zuordnungs-Schritt ('Schritt 3': Kamera -> Shot-Typ + Person, Mic -> Person, plus Export-Layout-Toggle) existiert heute nur in der PyQt-App (`App/src/gui/assignment_page.py`). Der Web-Spike (`web/`) ist bisher nur ein Read-only-Review. Dieser Plan baut den Zuordnungs-Schritt als zweiten Web-Screen, der den bestehenden, Qt-freien Python-Kern **nur aufruft** — keine zweite Validierungs-/Vollstaendigkeits-/Persistenz-Wahrheit.

**In Scope:** Zustand anzeigen, live validieren, in die `.peakcut` speichern, Hoerprobe, wachsende Personen-Liste.
**Bewusst NICHT in Scope (Neubau/Max-Entscheidungen, keine Ports):** Clip-Grenzen-Editor, Vorschlag annehmen/verwerfen (proposed->selected), Smart-Boundary-Edit, '<- Zurueck'-Navigation, Peak-Kategorien.

## 2. Ansatz-Wahl

Aggregierte Jury-Rangfolge: 'Zuordnung als zweiter Web-Screen' (114) > '1:1-Port' (109) = 'Premium' (109). Gewaehlt als Fundament, weil er die Cutter-Alltags-Linse und die Produkt-Reife-Linse gewinnt: echte Standbilder ueber den bereits bewiesenen `/frame`-Dienst bei kleinster Fehlerflaeche, rein additiv auf vier verifiziert direkt-uebernehmbaren Bausteinen (project_state, /frame, Audio-Master-Sync, Peak-Liste).

**Grafts:**
- Aus dem 1:1-Port: Invariante 'Web ruft nur'; PyQt als benanntes Sicherheitsnetz; der am Code verifizierte Produktiv-Titel `Kamera- & Mikrofon-Zuordnung` (NICHT die Mockup-Frage — zwei Entwuerfe lagen hier falsch); die exakten Status-Strings.
- Aus dem Premium-Entwurf: Personen-Chip-Leiste und Hover-Scrub — als spaetere, optionale Stufen HINTER dem nutzbaren Fundament.
- Aus allen: die scharfe Sicherheits-Risiko-Liste als verbindliche Slice-0-Haertung.

## 3. Harte Constraints

1. **Pin-1:** Keyboardstellen-XML byte-identisch. Exporter (`core/exporters.py`, `core/sinnabschnitt_exporter.py`, `core/folgenschnitt_exporter.py`, `gui/workers.py`) NICHT anfassen. Web-Export laeuft ueber das bestehende `run_exports`. Pin-1-Test bleibt `test_keyboardstellen_xml_byte_identical_with_mix_in_mic_list` (`App/tests/test_audio_routing_safety.py`).
2. **Offline:** FastAPI nur `127.0.0.1`, im Code gepinnt (Slice 0). Keine externen Calls.
3. **PyQt parallel:** PyQt bleibt lauffaehig und ist das Sicherheitsnetz, bis der Produktionslauf (Slice 6) gruen ist. PyQt-Abschaltung ist NICHT Teil dieses Plans.
4. **TDD:** rot-gruen, getrennte Test- und Commit-Schritte; Test-Lauf selbst verifizieren vor Commit; nur bei gruen committen.
5. Kern + Exporter werden NUR aufgerufen, nicht neu geschrieben.

## 4. Verifizierte Code-Realitaet (gegengeprueft am 2026-06-19)

- `web/engine/app.py`: nur `/health`, GET `/project`, POST `/export`, GET `/frame`. Keine Mutation, keine Pfad-Whitelist, alle Exceptions -> 500, `_sessions` RAM-only ohne Lock, `host=127.0.0.1` nicht im Code, kein web-pytest-Ordner.
- `build_assignment_state` (assignment_page.py:209) und `preview_start_s_for_mic` (assignment_page.py:110) sind Qt-frei, liegen aber im `gui`-Modul (Import von dort fuer Slice 1 ok; sauberer Move nach `core/` optional in Slice 6).
- `to_camera_assignments` (assignment_page.py:183-200): Crash-Schutz (Personen-Shot ohne Person uebersprungen) — serverseitig erhalten.
- `save_project_archive(session, root=None)` (project_archive.py:280): bei `root=None` Wurzel-Raten aus Medienpfaden -> im Web-Schreibpfad `root` EXPLIZIT auf Akte-Parent setzen.
- `speaker_activity` wird beim Laden aus CSV rehydriert (project_archive.py:396-402) -> Hoerprobe funktioniert fuer geladene Akten.
- `build_mic_preview_command` (gui/mic_preview_worker.py): Qt-freies ffmpeg-WAV-zu-stdout-Kommando, direkt in der Engine nutzbar (kein simpleaudio).
- Produktiv-Titel: `Kamera- & Mikrofon-Zuordnung` (assignment_page.py:295). Status-Strings: 'Zuordnung vollstaendig — Folgenschnitt-XML wird erzeugt.' / 'Folgenschnitt-Zuordnung unvollstaendig — Keyboardstellen werden trotzdem exportiert.' (assignment_page.py:610-616).

## 5. Engine-Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/assignment?path=` | Zuordnungs-Zustand (cameras/mics/people/mode/applied), gebaut ueber `build_assignment_state` + `preview_start_s_for_mic`. Felder leer. |
| POST | `/assignment/validate?path=` | Live-Vollstaendigkeit ohne Persistenz; exakte zwei Status-Strings; Crash-Schutz. |
| POST | `/assignment?path=` | Speichern (= 'Weiter'): vier `folgenschnitt_*`-Felder + applied=true; atomar via `save_project_archive(session, root=Akte-Parent)`; nie wegen Unvollstaendigkeit brechen; Per-Akte-Lock; Pin-1-Regressionstest. |
| GET | `/mic_preview?path=&track=` | 5s-WAV ab `preview_start_s_for_mic` via `build_mic_preview_command`. |
| GET | `/frame?video=&t=&w=` | BESTEHT. Kamera-Standbilder + spaeter Hover-Scrub. Erbt Whitelist (Slice 0). |
| POST | `/export?path=&out=` | BESTEHT. `run_exports` -> unveraenderte Exporter. Erbt Whitelist (Slice 0). |

Request/Response-Vertraege je Endpunkt sind im Strukturteil dieses Plans (engine_endpoints) ausformuliert.

## 6. Slices (TDD, rot-gruen)

- **Slice 0 — Engine-Haertung + Web-TDD-Fundament** (Vorbedingung, kein UI-Wert): host-Pin im Code, Pfad-Whitelist, Per-Akte-Lock, 4xx-statt-500-Mapping, web-pytest-Ordner. MUSS vor jedem Schreib-Endpunkt.
- **Slice 1 — GET /assignment** (erster Nutzwert): Screen mit echten Kamera-Standbildern ueber /frame.
- **Slice 2 — POST /assignment/validate**: Live-Status mit exakten Strings, Crash-Schutz.
- **Slice 3 — POST /assignment**: Speichern in .peakcut + Pin-1-Regressionstest. Ab hier produktiv.
- **Slice 4 — GET /mic_preview**: Hoerprobe ohne simpleaudio.
- **Slice 5 — Wachsende Personen-Liste** (Datalist-Semantik, kein Klobbern).
- **Slice 6 — Produktionslauf-Gate**: Web vs. PyQt verifizieren, gruener Selbstcheck-Report vor Max-Test.
- **Slice 7 (Premium, optional)** — Personen-Chip-Leiste.
- **Slice 8 (Premium, optional, Max-Entscheid + Proxy-Pipeline)** — Hover-Scrub.

Jede Slice: Tests, Engine-Aenderungen, Frontend-Aenderungen, Abhaengigkeit — siehe Strukturteil (slices).

## 7. Erhaltene Verhaltensweisen (nicht verlieren)

Felder starten leer/neutral; geteilter wachsender Personen-Pool ohne Klobbern; Person-Feld disabled bei personlosem/neutralem Shot; Crash-Schutz Personen-Shot-ohne-Person; Mix-Spur gefiltert; Hoerprobe ab laengstem aktivem Block; Disable/Remove-Toggle Default disable; Live-Vollstaendigkeit (>=2 Personen, je auf Basiskamera); harte Leitplanke (Keyboardstellen-Export laeuft IMMER); Speichern setzt die vier `folgenschnitt_*`-Felder + atomares .peakcut; Wiedereinstieg applied=true ueberspringt die Zuordnung.

## 8. Offene Fragen (nur Max)

Pool persistieren ja/nein; Per-Kamera-Proxy-Quelle fuer Hover-Scrub; Chip-Interaktion; '<- Zurueck' jetzt oder spaeter (Hub-Schritt); Peak-Kategorien; Wellenform ja/nein; ob Web schon Alex' Primaerweg wird. Details im Strukturteil (open_questions_for_max).

## 9. Risiken

Pfad-Traversal/Datenverlust ohne Slice 0 (Schreib-Endpunkt zuerst absichern); Concurrency ohne Lock; uvicorn-Host nur am Start gepinnt; 4xx-vs-500; Pin-1-Bruch falls Exporter beruehrt werden (verboten); Premium-Hover-Scrub ohne Per-Kamera-Proxy ist tot; Drift Web<->PyQt falls Kern nicht nur aufgerufen, sondern nachgebaut wird (Invariante 'Web ruft nur').

## 10. Definition of Done

Slices 0-6 gruen (Web-pytest + Pin-1 + Produktionslauf-Vergleich Web vs. PyQt); kein Exporter beruehrt; offline gepinnt; PyQt weiter lauffaehig; Carl-Schluss-Review; Max-Abnahme an echter Akte.


---

## Anhang A — Detaillierte Slices

### Slice 0 — Engine-Haertung + Web-TDD-Fundament (VOR jedem Schreib-Endpunkt)
*Abhaengigkeit:* keine (erster Slice)

**Ziel:** Die heute ungesicherte Engine schreibfest machen und einen echten Python-Test-Ordner fuer web/ etablieren. Ohne diesen Slice ist jeder spaetere Schreib-Endpunkt ein Pfad-Traversal-/Datenverlust-Risiko. Kein UI-Wert, aber harte Vorbedingung.

**Engine:** web/engine/app.py: zentralen Bind auf host=127.0.0.1 im Code festschreiben. Pfad-Whitelist-Helper einfuehren (erlaubte Wurzel = Ordner der geoeffneten Akte bzw. eine konfigurierte Material-Root; alle path/video-Query-Params dagegen pruefen, normpath + Praefix-Check). Exception-Mapping verfeinern: ProjectArchiveError/Schema-Zukunft -> 409/422, ClipCandidateError/ValueError aus Validierung -> 422, FileNotFound -> 404, Rest -> 500. Per-Akte-Lock-Dict (threading.Lock je Akten-Pfad) um _sessions-Zugriff. NEU: web/engine/tests/ + conftest.py, pytest.ini/Marker, der den App/src-Pfad einbindet wie engine_core.py (sys.path).

**Frontend:** Keine. Reiner Engine-/Test-Slice.

**Tests:**
- test_engine_binds_localhost_only: uvicorn-Konfiguration/Start pinnt host=127.0.0.1 im Code (nicht nur Start-Kommando) — Assertion auf die im Code gesetzte host-Variable bzw. einen zentralen Bind-Helper.
- test_path_outside_whitelist_rejected_404_or_403: GET /project?path=<pfad ausserhalb erlaubter Wurzel> liefert 4xx, nicht 200 und nicht 500.
- test_path_traversal_rejected: path mit ../-Segmenten oder absolutem Fremdpfad wird vor jedem Dateizugriff abgewiesen.
- test_clipcandidate_illegal_transition_maps_to_4xx: ein simulierter illegaler Statusuebergang (z.B. published->selected) ergibt 409/422, NICHT 500 (Faenger uebersetzt ClipCandidateError/ValueError differenziert).
- test_per_akte_lock_serializes_writes: zwei gleichzeitige (sequenziell getestete) mutierende Calls auf dieselbe Akte verlieren keinen State (Lock pro Akten-Pfad vorhanden, analog FrameService._lock).
- test_web_pytest_runs: ein triviale conftest + ein gruener Smoke-Test beweisen, dass der web/-Test-Ordner mit dem Engine-venv laeuft.

### Slice 1 — GET /assignment: Zuordnungs-Zustand serialisieren (read-only, sofort sichtbar)
*Abhaengigkeit:* Slice 0 (Whitelist/Lock muessen stehen, auch wenn GET noch nicht schreibt — gleiche Pfad-Pruefung)

**Ziel:** Den kompletten Zuordnungs-Aufbau aus dem Kern ausstellen, damit das Frontend Kameras/Mics/Pool/Mode/applied-Flag anzeigen kann. Erster echter Nutzwert: der Cutter sieht den Screen mit echten Kamera-Standbildern (ueber den bestehenden /frame-Dienst) statt Platzhalter — auch ohne Speichern.

**Engine:** engine_core.py: neue Funktion assignment_state(session) die build_assignment_state(session, session.project.videos) ruft, preview_start_s_for_mic pro Mic aufruft und alles serialisiert (inkl. unused_clips_mode via normalize_unused_clips_mode, assignment_applied). app.py: GET /assignment?path= mit Whitelist + Session-Cache (wie /project), nutzt assignment_state. WICHTIG: build_assignment_state/preview_start_s_for_mic liegen heute in gui/assignment_page.py — sie sind Qt-frei (Zeile 110/209), aber im gui-Modul. Engine importiert sie von dort ODER (sauberer, mit Max abklaeren) Carl hebt sie in ein core/-Modul; fuer diesen Slice reicht der Import aus gui, da rein funktional und Qt-frei.

**Frontend:** Neuer Web-Screen (eigene Route/Seite vor dem bestehenden Read-only-Review). Header mit Kicker 'SCHRITT 3 · ZUORDNUNG' + Produktiv-Titel 'Kamera- & Mikrofon-Zuordnung' + Erklaer-Hinweis. Kamera-Karten-Grid (16:9-Standbild via bestehendem GET /frame?video=<path>&t=<peak_in_s>, voller Dateiname, Shot-Dropdown mit 6 Optionen, Person-Dropdown). Mic-Zeilen (Dateiname, Person-Dropdown, Hoerprobe-Button noch inaktiv). Export-Options-Block (Disable/Remove, Default Disable) ueber dem Footer. Status noch statisch. Alles read-only/anzeigend — kein Speichern, kein POST.

**Tests:**
- test_assignment_state_serialized_from_core: GET /assignment liefert cameras[] (path/filename/shot_type=null/person=null), mics[] (track_index/path/filename/person=''/speaker_key/preview_start_ms), people[], unused_clips_mode='disable', assignment_applied=false fuer eine frische Akte — gebaut ueber build_assignment_state(session, project.videos), NICHT neu.
- test_mix_track_filtered_from_mics: die Mix-Spur taucht in mics[] NICHT auf (is_mix_track-Filter aus build_assignment_state geerbt).
- test_preview_start_ms_matches_core: preview_start_ms pro Mic == preview_start_s_for_mic(session, speaker_key)*1000 (gerundet) — Start-Logik aus dem Kern, nicht im Frontend.
- test_applied_archive_returns_persisted_assignments: bei einer Akte mit assignment_applied=true liefert GET /assignment die persistierten folgenschnitt_*-Werte zum Pruefen (shot_type/person gefuellt).
- test_fields_start_empty_no_guessed_default: kein Kamera-shot_type und keine Person ist in einer frischen Akte vorbefuellt.

### Slice 2 — POST /assignment/validate: Live-Vollstaendigkeits-Status (ohne Persistenz)
*Abhaengigkeit:* Slice 1 (Screen + Felder existieren)

**Ziel:** Die Live-Statuszeile mit den exakten zwei Strings treiben, ohne staendig zu speichern. Der Cutter sieht bei jeder Aenderung, ob die Zuordnung vollstaendig ist und dass Keyboardstellen trotzdem exportiert werden.

**Engine:** engine_core.py: validate_assignment(session, body) baut transient einen AssignmentState aus dem Body (cameras/mics/unused_clips_mode), ruft to_camera_assignments()/to_mic_assignments() (Crash-Schutz inklusive) und has_minimum_folgenschnitt_assignment, gibt {is_complete, status_text} mit den exakten Strings zurueck. app.py: POST /assignment/validate?path= (Whitelist, kein Save). KEINE Mutation des gecachten Session-State (transienter State-Build).

**Frontend:** Live-Statuszeile + Tally ('N Kameras · M Mics zugeordnet') im Footer. Bei jeder Feld-Aenderung (debounced) POST /assignment/validate und Status/Tally aktualisieren. Person-Feld grau/deaktiviert bei neutralem/personlosem Shot (clientseitig gespiegelt aus SHOT_CHOICES/PERSONLESS — Werte muessen aus der Engine kommen oder als Konstanten geteilt werden, nicht hartkodiert geraten).

**Tests:**
- test_validate_complete_two_persons_base_camera: ein Body mit >=2 Personen, je auf Basiskamera aufloesbar, ergibt {is_complete:true, status_text:'Zuordnung vollstaendig — Folgenschnitt-XML wird erzeugt.'}.
- test_validate_incomplete_returns_guardrail_string: unvollstaendiger Body ergibt is_complete:false + exakt 'Folgenschnitt-Zuordnung unvollstaendig — Keyboardstellen werden trotzdem exportiert.'
- test_validate_person_shot_without_person_no_500: ein Personen-Shot (Weit/Nah/Halbnah) OHNE Person im Body crasht NICHT (uebersprungen via to_camera_assignments-Crash-Schutz), liefert 200 + is_complete entsprechend.
- test_validate_does_not_persist: nach /validate ist die .peakcut-Akte unveraendert (kein Save-Aufruf).

### Slice 3 — POST /assignment: Speichern in die .peakcut (das 'Weiter'-Aequivalent)
*Abhaengigkeit:* Slice 1 + Slice 2 (Zustand + Validierung), Slice 0 (Schreib-Sicherheit zwingend)

**Ziel:** Der zentrale Schreib-Endpunkt. 'Weiter zur Review' speichert die komplette Zuordnung atomar in die .peakcut, setzt applied=true und routet zum bestehenden Read-only-Review. Ab hier ist der Screen produktiv nutzbar (Zuordnung machen + dauerhaft sichern + zur Review).

**Engine:** engine_core.py: apply_assignment(session, body, root) baut AssignmentState aus dem Body, schreibt die vier folgenschnitt_*-Felder in die Session (apply_to_session-Aequivalent), ruft save_project_archive(session, root=<Akte-Parent>) mit EXPLIZITEM root (nie root=None raten lassen — Sicherheit/Determinismus). Gibt neuen assignment_state + is_complete zurueck. app.py: POST /assignment?path= (Whitelist, Per-Akte-Lock, 4xx-Mapping fuer Schema-Zukunft via _assert_archive_write_allowed).

**Frontend:** 'Weiter zur Review →'-Button im Footer sammelt UI-Stand (cameras[], mics[], unused_clips_mode), POSTet an /assignment, bei Erfolg Wechsel zur bestehenden Read-only-Review. Routing-Logik: beim Oeffnen einer Akte mit assignment_applied=true direkt Review zeigen, sonst Zuordnung (main_window.py:288-299 als Vorbild). Export-Options-Toggle und Live-Status sind jetzt voll funktional verdrahtet.

**Tests:**
- test_apply_writes_four_session_fields: POST /assignment setzt folgenschnitt_mic_assignments, folgenschnitt_camera_assignments, folgenschnitt_unused_clips_mode, folgenschnitt_assignment_applied=true (exakt apply_to_session-Semantik).
- test_apply_persists_archive_atomically: nach POST liegt .peakcut/project.json (Schema v4) mit den Assignments vor; Save lief ueber save_project_archive mit explizit gesetztem root (Akte-Parent), nicht ueber Pfad-Raten.
- test_apply_person_shot_without_person_skipped_not_500: Personen-Shot ohne Person wird beim Speichern uebersprungen statt ValueError/500 (Crash-Schutz serverseitig).
- test_apply_never_fails_on_empty_assignment: eine komplett leere Zuordnung speichert erfolgreich (harte Leitplanke — Speichern bricht nie wegen Unvollstaendigkeit).
- test_pin1_keyboardstellen_xml_byte_identical_after_web_apply: nach POST /assignment + anschliessendem /export ist die Keyboardstellen-XML byte-identisch (gleicher SHA-256 wie test_keyboardstellen_xml_byte_identical_with_mix_in_mic_list) — der Web-Schreibpfad veraendert den Keyboardstellen-Export NICHT.
- test_apply_serialized_per_akte: zwei Saves auf dieselbe Akte laufen ueber den Per-Akte-Lock, kein verlorener State.
- test_apply_round_trip_reload: nach POST + erneutem GET /assignment kommen exakt die gespeicherten Werte zurueck (relative Pfade korrekt rehydriert).

### Slice 4 — GET /mic_preview: Hoerprobe pro Mic (Kern-Logik in die Engine)
*Abhaengigkeit:* Slice 1 (Mic-Zeilen existieren)

**Ziel:** Die Hoerprobe (5s ab dem laengsten aktiven Sprecher-Block) im Web ermoeglichen, ohne die PyQt/simpleaudio-Bindung. Der Cutter kann pro Mic kurz reinhoeren, um die Person zu identifizieren.

**Engine:** engine_core.py: mic_preview(session, track_index_or_speaker_key) berechnet preview_start_s_for_mic serverseitig und ruft build_mic_preview_command(path, 5.0, start_s) (aus gui/mic_preview_worker.py — das Kommando ist Qt-frei, nur die QThread-Huelle ist Qt) ueber subprocess, gibt die WAV-Bytes zurueck. app.py: GET /mic_preview?path=&track= (Whitelist). speaker_activity ist nach load_project_archive bereits hydriert (project_archive.py:396-402 liest die CSV), also steht preview_start_s_for_mic zur Verfuegung.

**Frontend:** Hoerprobe-▶-Button pro Mic-Zeile aktiv: holt /mic_preview und spielt den WAV-Stream im Browser (HTML-Audio). Kein simpleaudio.

**Tests:**
- test_mic_preview_start_matches_core: der gelieferte Ausschnitt startet bei preview_start_s_for_mic(session, speaker_key) (gleiche Logik wie Desktop, nicht neu erfunden).
- test_mic_preview_returns_audio_stream: GET /mic_preview liefert einen ~5s WAV-Stream mit korrektem media_type, gebaut ueber build_mic_preview_command (ffmpeg fast-seek, das bestehende Kommando).
- test_mic_preview_path_whitelisted: der Mic-Pfad wird gegen die Whitelist geprueft, Fremdpfad -> 4xx.
- test_mic_preview_no_speaker_activity_fallback: ohne speaker_activity-Daten startet der Ausschnitt bei 0.0 (Kern-Fallback).

### Slice 5 — Wachsende Personen-Liste (Datalist-Semantik, seitenweit)
*Abhaengigkeit:* Slice 1 (Person-Felder existieren)

**Ziel:** Das subtile UX-Verhalten reproduzieren: ein einmal getippter Name wird ueberall auswaehlbar, ohne belegte Felder zu ueberschreiben. Beschleunigt das Befuellen mehrerer Felder.

**Engine:** Keine. Der Pool ist clientseitig pro Sitzung (wie heute in-memory im PyQt) und wird beim Speichern implizit aus den Assignments abgeleitet. Bewusst NICHT als neues Persistenz-Feld erfinden (Schema-Drift vermeiden) ohne Max-Entscheid.

**Frontend:** Jedes Person-Feld als <input list> + gemeinsame <datalist>, gespeist aus allen bisher vergebenen Namen. Commit bei Blur (editingFinished-Aequivalent). Beim Hinzufuegen eines Namens andere Felder nicht ueberschreiben.

**Tests:**
- test_typed_name_appears_in_all_person_fields: ein in ein Person-Feld getippter Name erscheint danach als Auswahl in allen anderen Person-Feldern (Frontend-Verhaltenstest, reproduzierbar).
- test_typed_name_does_not_clobber_filled_fields: das Hinzufuegen eines neuen Namens veraendert bereits belegte Person-Felder NICHT (Spiegel von _commit_person_name-Semantik, assignment_page.py:276-289).
- test_pool_dedupe_trim: doppelte/whitespace-Namen werden dedupliziert/getrimmt wie im Kern.

### Slice 6 — Produktionslauf-Gate: voller Web-Flow vs. PyQt verifizieren
*Abhaengigkeit:* Slice 3 + Slice 4 (voller Flow inkl. Speichern + Hoerprobe)

**Ziel:** Beweisen, dass der Web-Zuordnungs-Flow an echtem Material dasselbe Ergebnis erzeugt wie PyQt, BEVOR irgendwer von 'fertig' spricht. PyQt bleibt parallel das Sicherheitsnetz.

**Engine:** Ggf. kleine Test-Helfer; keine produktive Logikaenderung. Falls Slice 1 die Funktionen aus gui importiert hat und Carl/Max entscheiden, sie nach core zu heben: hier der saubere Move (rein mechanisch, Qt-frei, mit Test-Abdeckung).

**Frontend:** Keine neuen Features; ggf. ein Verify-Harness im web/-Ordner (analog dem bestehenden review-report.json-Selbstcheck) fuer den Voll-Flow.

**Tests:**
- test_web_vs_pyqt_same_session_fields: gleiche Zuordnung ueber Web-POST vs. PyQt apply_to_session erzeugt identische folgenschnitt_*-Session-Felder (gleiche CameraAssignment/MicAssignment-Listen).
- test_web_export_matches_pyqt_export: nach Web-Apply + /export sind alle vier Artefakte (Keyboardstellen-XML/TXT, Folgenschnitt-XML, Sinnabschnitt-XML) gleichwertig zum PyQt-Pfad (Pin-1 byte-identisch, andere strukturell gleich).
- Selbst-verifizierender Reproduktions-Check an EINER echten Akte (Skript, das Web-Apply fahrt, exportiert und gegen einen PyQt-Referenz-Export difft) — gruener PASS/FAIL-Report, bevor Max es anfasst.

### Slice 7 (Premium-Stufe, optional) — Personen-Chip-Leiste
*Abhaengigkeit:* Slice 5 (Pool-Semantik steht)

**Ziel:** Den wachsenden Pool als sichtbare schwarze Pill-Chips im Header darstellen (Graft aus Ansatz 2), schnelleres Befuellen. Reine UX-Verpackung der bereits bewiesenen Pool-Semantik.

**Engine:** Keine.

**Frontend:** Header-Chip-Leiste (Pills #1D1D1F, weisser Text, Radius 999px) + '+ hinzufuegen'-Chip. Azure-Akzent-Semantik (#0A6FE0) bewusst uebernehmen. Datalist aus Slice 5 bleibt als Eingabemechanik bestehen.

**Tests:**
- test_chip_added_on_new_name: neuer Name -> neuer Chip im Header + seitenweit waehlbar.
- test_chip_click_focuses_or_fills: definierte Chip-Interaktion (Max entscheidet: Klick fokussiert vs. fuellt aktives Feld) verhaelt sich konsistent, ueberschreibt keine belegten Felder.
- test_no_clobber_invariant_holds: dieselbe Nicht-Ueberschreib-Invariante wie Slice 5 bleibt erfuellt.

### Slice 8 (Premium-Stufe, optional, Max-Entscheid + Proxy-Pipeline noetig) — Hover-Scrub auf Kamera-Karten
*Abhaengigkeit:* Slice 1 (Kamera-Karten + /frame), Max-Entscheid zur Proxy-Pipeline

**Ziel:** Proxy-Frame live beim Ziehen ueber die Kamera-Karte (Graft aus Ansatz 2): schnelles 'wer ist auf dieser Kamera' ohne Player-Start. NUR sinnvoll, wenn die Per-Kamera-Proxy-Frage geloest ist.

**Engine:** /frame besteht bereits. Offen (Max/Carl): woher kommt pro Kamera ein scrubbbarer Proxy — Original direkt (schwerer) oder generierte 1080p-Proxies (neue Pipeline). Diese Entscheidung blockt den Slice; nicht raten.

**Frontend:** Hover-Scrub-Streifen unter dem Kamera-Thumbnail; Ziehen tauscht den Frame live ueber /frame (debounced). Kein 4K-Versprechen — bewusst Proxy-Scrub.

**Tests:**
- test_scrub_debounced_frame_requests: Ziehen loest debounced (~30ms) GET /frame-Requests aus, kein Request-Sturm.
- test_scrub_resolves_camera_proxy_path: der Frame-Request nutzt den korrekten Per-Kamera-Pfad (Proxy oder Original aus project_state.videos), NICHT einen Hardcode-Ordner.
- test_frame_path_whitelisted: /frame-Pfade unter Whitelist (Slice 0 erbt hierher).

---

## Anhang B — Endpunkt-Vertraege

### GET /assignment?path={akte}
Liefert den Zuordnungs-Zustand fuers Frontend, gebaut ueber build_assignment_state(session, project.videos) + preview_start_s_for_mic (Kern, nicht neu erfunden). Bei applied-Akte die persistierten folgenschnitt_*-Werte zum Pruefen. Felder starten bewusst leer.

- **Request:** Query: path=<absoluter .peakcut-Akten- oder Ordnerpfad, gegen Whitelist geprueft>. Kein Body.
- **Response:** 200 JSON: {guest_name, cameras:[{path, filename, shot_type:null|str, person:null|str}], mics:[{track_index, path, filename, person:str, speaker_key, preview_start_ms:int}], people:[str], unused_clips_mode:'disable'|'remove', assignment_applied:bool, shot_choices:[{label,value}]}. 404 Akte nicht gefunden, 403/422 Pfad ausserhalb Whitelist.

### POST /assignment/validate?path={akte}
Reiner Vollstaendigkeits-Check ohne Persistenz fuer die Live-Statuszeile. Baut transient einen AssignmentState, ruft to_camera/mic_assignments (Crash-Schutz) + has_minimum_folgenschnitt_assignment. Liefert die EXAKTEN zwei Status-Strings.

- **Request:** Query: path=. Body JSON: {cameras:[{path, shot_type:null|str, person:null|str}], mics:[{track_index, path, person:str, speaker_key}], unused_clips_mode:'disable'|'remove'}.
- **Response:** 200 JSON: {is_complete:bool, status_text:str (exakt einer der zwei Strings), cameras_assigned:int, mics_assigned:int}. 200 auch bei Personen-Shot-ohne-Person (uebersprungen, kein 500). 422 nur bei strukturell kaputtem Body.

### POST /assignment?path={akte}
Speichert die komplette Zuordnung (= 'Weiter'). Setzt die vier folgenschnitt_*-Felder (apply_to_session-Semantik) inkl. assignment_applied=true, persistiert atomar via save_project_archive mit EXPLIZITEM root (Akte-Parent). Bricht nie wegen leerer/unvollstaendiger Zuordnung (harte Leitplanke). Per-Akte-Lock.

- **Request:** Query: path=. Body JSON: {cameras:[{path, shot_type:null|str, person:null|str}], mics:[{track_index, path, person:str, speaker_key}], unused_clips_mode:'disable'|'remove'}.
- **Response:** 200 JSON: {assignment:<gleiche Form wie GET /assignment>, is_complete:bool}. 404 Akte fehlt, 403/422 Pfad-Whitelist, 409/422 Schema-Zukunft (Akte zu neu, _assert_archive_write_allowed). Personen-Shot-ohne-Person -> uebersprungen, KEIN 500.

### GET /mic_preview?path={akte}&track={track_index}
Hoerprobe: 5s-Audio-Ausschnitt ab preview_start_s_for_mic(session, speaker_key) als WAV-Stream. Ersetzt den PyQt/simpleaudio-MicPreviewWorker; nutzt das bestehende, Qt-freie build_mic_preview_command (ffmpeg fast-seek). Pfad-Whitelist.

- **Request:** Query: path=, track=<track_index des Mics> (oder speaker_key). Kein Body.
- **Response:** 200 WAV-Bytes (media_type audio/wav), ~5s ab dem laengsten aktiven Sprecher-Block (~0.5s davor). 403/422 Pfad-Whitelist, 404 Mic/Akte fehlt.

### GET /frame?video={path}&t={sec}&w={px}
BESTEHT BEREITS (warmer av-Container, ~110ms). Unveraendert wiederverwendet fuer Kamera-Standbilder (Slice 1) und spaeter Hover-Scrub (Slice 8). Erbt in Slice 0 die Pfad-Whitelist.

- **Request:** Query: video=<Kamerapfad, Whitelist>, t=<Sekunden>, w=<Zielbreite px, optional>. Kein Body.
- **Response:** 200 image/jpeg (frame-genaues Standbild). 403/422 Pfad-Whitelist (neu ab Slice 0), 500 nur bei echtem Dekodier-Fehler.

### POST /export?path={akte}&out={dir}
BESTEHT BEREITS (run_exports -> unveraenderte Python-Exporter). Der Pin-1-erhaltende Weg: kein XML wird im Web geschrieben. Aus dem Review aufgerufen. Keine Aenderung noetig ausser Whitelist-Erbe (Slice 0) auf path UND out.

- **Request:** Query: path=<Akte, Whitelist>, out=<Ausgabeordner, Whitelist>. Kein Body.
- **Response:** 200 JSON: {keyboardstellen_xml, keyboardstellen_txt, folgenschnitt_xml, sinnabschnitt_xml} je Pfad oder 'ERROR: ...'-String pro Exporter (bestehendes Verhalten).

---

## Anhang C — Offene Fragen (nur Max entscheidet)

- Personen-Pool persistieren oder nicht? Heute lebt der Pool nur in-memory pro Sitzung (geht beim Neuladen vor 'Weiter' verloren — genau wie PyQt). Soll der Web-Pool in die .peakcut geschrieben werden (neues Feld, Schema-Drift-Risiko) oder bewusst sitzungsfluechtig bleiben wie im Desktop? Default-Vorschlag: sitzungsfluechtig (kein Schema-Drift), aber das ist eine Produktentscheidung.
- Hover-Scrub (Slice 8, Premium): Woher kommt pro Kamera ein scrubbbarer Proxy? Direkt das Original-Video (schwerer, aber keine neue Pipeline) oder generierte 1080p-Per-Kamera-Proxies (neue, nicht-triviale Pipeline; heute zeigt der Spike auf EINEN Hardcode-Proxy, NICHT die Akten-Videos)? Ohne diese Entscheidung bleibt das zentrale Premium-Feature unbaubar.
- Personen-Chip-Interaktion (Slice 7): Was macht ein Klick auf einen Chip — das aktive Person-Feld fuellen, oder nur fokussieren/filtern? Und soll '+ hinzufuegen' einen leeren Chip-Eingabemodus oeffnen oder nur ein Hinweis sein?
- '<- Zurueck'-Navigation: Im PyQt-Backend gibt es nur continue_clicked, KEIN back_clicked (verifiziert assignment_page.py:250). Ein sauberer Rueckweg ist laut Roadmap der eigentliche Hub-Schritt (Zuordnung re-hydratisieren + Review konsistent neu aufsetzen) und nicht trivial. Soll der Web-Screen vorerst OHNE Zurueck gebaut werden (Korrektur via Akte-neu-oeffnen), oder ist der saubere Rueckweg jetzt Scope? Vorschlag: erst ohne, Hub-Rueckweg als eigener Slice spaeter.
- Peak-Kategorien (Anekdote/Pointe): Im Design-Mockup sind das Dummy-Labels, das Backend hat KEINE Kategorien. Weglassen (Vorschlag) oder ist ein Kategorie-Feld ein gewuenschtes neues Produkt-Feature (dann eigener Plan, kein Port)?
- Aktivitaets-Wellenform pro Mic (Premium-Politur): nur visuelle Hilfe — bauen oder als unnoetige Komplexitaet weglassen? Sie darf den fachlich wichtigen preview_start_s nie verfaelschen.
- Soll der Web-Zuordnungs-Screen schon jetzt der primaere Weg fuer Alex' XML-Tests werden, oder bleibt PyQt bis zum gruenen Produktionslauf (Slice 6) der einzige produktive Weg und das Web laeuft parallel als Beweis? (Beeinflusst, wie hart Slice 6 als Gate gilt.)
