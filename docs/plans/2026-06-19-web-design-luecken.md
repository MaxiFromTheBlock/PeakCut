# Web-Design — Funktions-Lücken (lebende Liste)

> Funktionen, die die App braucht, die der Design-Handoff (noch) NICHT zeigt — weil
> der Designer sie nicht kannte. Claude flaggt; Max entscheidet, was wirklich rein muss.
> Bei jedem Screen-Bau die zugehörigen Punkte abarbeiten/bestätigen.
> Quelle: grep über die `.dc.html` (2026-06-19) + Abgleich mit dem PyQt-Verhalten (CLAUDE.md).

## Sicher fehlend (im Entwurf nicht vorhanden, App braucht es)
- **Export-Name / Gastname korrigieren.** Der Entwurf ZEIGT den Gastnamen (Analyse-Seite),
  aber es gibt KEIN Feld zum Eintippen/Korrigieren. Die App rät den Namen aus dem
  Mix-Dateinamen und lässt ihn im PyQt per Dialog bestätigen/ändern; er bestimmt den
  Export-Dateinamen („Keyboardstellen - {Gast}"). → Eingabe-/Korrektur-Feld nötig
  (Import oder Analyse). *(Max' Beispiel, bestätigt.)*
- **Export-Optionen „deaktivierte vs. entfernte Clips" (Disable/Remove)** auf der
  Zuordnung. grep im Entwurf: nicht vorhanden. PyQt hat den Umschalter
  (`folgenschnitt_unused_clips_mode`, Default disable). → muss in die Web-Zuordnung.
- **Fehler-/Leerzustände.** Der Entwurf zeigt nur den Schönwetter-Fall. Es fehlen:
  „keine Peaks gefunden" (PyQt: 0-Peaks-Guard), unvollständiger/kaputter Import,
  ungültige Datei. → Zustände definieren.

## Wahrscheinlich fehlend / zu klären
- **Marker-/Keyboard-Spur von Hand wählen**, falls die Auto-Erkennung danebenliegt
  (PyQt hat einen Fallback-Dialog). Im Entwurf nur als Dropzone-Hinweis „Keyboard-Spur".
  → Randfall, bestätigen.
- **Transkript-Quelle/Import** für die KI-Sinnabschnitte (Whisper automatisch ODER
  Descript-`.docx`-Import). Im Entwurf nicht gezeigt. → woher kommt das Transkript im Web?
- **Analyse-Live-Zahlen (ETA / Peak-Zähler).** Der Entwurf verspricht sie; ob der
  Analyse-Lauf sie LAUFEND liefert, ist offen (CLAUDE.md: Zeitschätzung ungenau,
  Analyse läuft als Subprozess und meldet eher am Ende). → echte Live-Daten oder Spinner.

## Größere offene Fragen
- **CheckIn-Aufruf-Modus.** Heute startet CheckIn die PyQt-App mit `--guest` + `--export-dir`
  (Export-Ordner + Gastname kommen von außen, schreibt `.peakcut_done`). Wie ruft CheckIn
  später die Web-App? → eigene Integrations-Entscheidung.
- **Einstellungen** (Erkennungs-Schwelle, min_gap, Bildrate/fps, TTS-Stimme, LUT-Pfad).
  Kein Einstellungs-Screen im Entwurf. → klären, ob ein Settings-Bereich nötig ist.

## Neue Wünsche / Entscheidungen aus der Nutzung (2026-06-20)
- **Begriff „Keyboard" → „Marker" ÜBERALL (Max-Entscheid 2026-06-20).** Gerät ist seit 2
  Folgen eine Kickdrum, nicht mehr Keyboard → geräteunabhängiger Begriff. **Marker** (nicht
  Peak) in UI, Export (XML-Sequenz-/Dateinamen „Keyboardstellen…" → „Marker…"), Datei-
  Erkennung (heute `keyboard/keys/klavier`), Doku. Eigener Slice mit Carl: **Pin-1 neu
  einfrieren** (XML-Bytes ändern sich bewusst), Erkennung vom Marker-Gerät lösen, Alex' XMLs.
  Im Web-Frontend ab sofort „Marker". → gehört auch in `App/BACKLOG.md`.
- **Folgenschnitt-Kamerawechsel in der Review-Vorschau sehen (Feature).** Zwei Wege:
  (a) live mitschalten — Player springt beim Abspielen auf die laut Folgenschnitt-XML aktive
  Kamera (leicht, kann bei vielen Schnitten haken); (b) Multicam-Schnitt einmal als EINE
  Datei rendern (butterweich, aber Render-Schritt). Braucht die Schnitt-Daten (wer-wann) aus
  der Engine. Direkt nach dem manuellen Kamera-Durchklicken; Weg-Entscheidung dann Max.
- **Manuelles Kamera-Durchklicken in der Review (in Arbeit 2026-06-20).** Pro Kamera ein
  gemuxter Proxy (Bild+Mix, jeweiliger Versatz, faststart); Kamera-Wähler schaltet Quelle,
  Position bleibt. (Player auf EINE gemuxte Datei = Sync per Bauart steht bereits.)

## Erledigt
- (noch nichts)
