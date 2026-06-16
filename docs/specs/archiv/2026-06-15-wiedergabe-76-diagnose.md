# Diagnose — Wiedergabe-UX (#76), Bau-Input für Carls Plan (2026-06-15)

> **Kein Plan, sondern Diagnose.** Faktenlage am Code für den nächsten Slice
> (#76), damit Carl darauf seinen Umsetzungsplan baut (Konstellation: Carl
> plant, Claude baut TDD, Max entscheidet). Reihenfolge-Kontext: #76 ist die
> harte Voraussetzung vor jedem KI-Tuning (#70) — ohne hörbar+sichtbar
> synchrone Vorschau kann Max die Sinnabschnitt-Qualität nicht beurteilen.

## Was Max braucht (Ziel)
Eine Vorschau, die einen Clip (Drücker-Fenster ODER Smart-Sinnabschnitt)
**gleichzeitig in Bild UND Ton synchron** abspielt, vom In- bis zum Out-Punkt,
mit der Mix-Tonspur (nicht Kamera-Ton). Nur so ist ein redaktionelles Urteil
über die Schnittgrenzen möglich.

## Ist-Zustand: ZWEI getrennte Engines, kein gemeinsamer Takt

### Engine 1 — Audio: simpleaudio (`core/playback.py`)
- `play_audio(segment)` (`playback.py:13`): mono, 44.1k, globaler `_current_playback`,
  `sa.stop_all()` vor jedem Start. **Kein Seek, keine Positionsabfrage** außer
  `is_playing()` (`playback.py:25`).
- Gespeist aus `session.play_current()` (`session.py:84`): schneidet einen
  AudioSegment-Ausschnitt (keyboard-Preview ODER Mix via
  `audio_routing.get_speech_audio_segment`) und ruft `play_audio`.
- simpleaudio ist **unmaintainte, ABI-gebundene C-Extension** und laut
  Health-Check NICHT geparkt, sondern load-bearing (DEP-4) — bindet PeakCut
  zusätzlich an Python 3.11.

### Engine 2 — Video: QMediaPlayer, **stummgeschaltet** (`video_preview_peak.py`)
- `QMediaPlayer` + `QAudioOutput` mit `setMuted(True)` (`video_preview_peak.py:293`)
  + `QVideoSink`. Kamera-Ton wird also bewusst nie hörbar.
- `play_from(in_ms, out_ms)` (`:445`): `setPosition(video_in); play()`.
- **Eigener Takt + eigene Clip-Ende-Logik:** `position()` rechnet
  `_video_to_mix_ms(player.position())` (`:497`), `set_position` mappt
  Mix→Video (`:502`), und ein Poll pausiert bei `mix_position >= _clip_out_ms`
  (`:521-526`). Per-Kamera-Offset-Mapping (Mix↔Video) ist hier gekapselt.

### Die drei Wiedergabe-Pfade — keiner liefert Ton+Bild synchron
| Auslöser | Code | Tatsächliches Verhalten |
|---|---|---|
| **▶ / Space** (normal) | `on_play:355` → `session.play_current()` | **Nur Ton** (simpleaudio). Video läuft NICHT mit. |
| **Sinnabschnitt ▶** | `_on_play_sinnabschnitt:752` → `video_preview.play_from()` | **Nur Bild** (stumm). Vorher `stop_playback()` killt den Ton. |
| **Navigation** | `navigate_to_peak` → `video_preview.set_position()` | Statischer Frame, keine Wiedergabe. |

Der Dispatch-Poll `_poll_playback` (`:368`) beobachtet **nur** simpleaudios
`is_playing()` — er weiß nichts vom Video-Takt.

## Wurzel des Problems (CONC-1)
Zwei Engines mit **keinem gemeinsamen Takt**: simpleaudio liefert keine
Position/keinen Seek, QMediaPlayer hat zwar eine Position, ist aber stumm.
Es gibt keine Instanz, die Ton+Bild auf eine Uhr zieht. „Synchron abspielen"
ist mit dem heutigen Aufbau strukturell nicht möglich — nicht nur unverdrahtet.

## Offene Design-Fragen für Carls Plan (NICHT vorentschieden)
1. **Eine Uhr — welche Engine führt?**
   - (A) Zwei QMediaPlayer: einer fürs Video (stumm), einer für die Mix-Audiodatei
     (hörbar); beide auf dieselbe Mix-Position seeken, gemeinsam starten,
     QMediaPlayer-Position als gemeinsame Uhr. Mix muss als Datei vorliegen
     (liegt sie? sonst kurz rendern/cachen).
   - (B) Ein QMediaPlayer fürs Video + Qt-Audio (QAudioSink/QSoundEffect) für
     den Mix-Ausschnitt, ein Play-Dispatcher synchronisiert.
   - (C) simpleaudio behalten, nur Mess-Anker drumherum — vermutlich schwach,
     weil simpleaudio keine Position/Seek hat.
   - **Carl-Hinweis aus dem Review:** prüfen, ob QAudioSink/QSoundEffect die
     simpleaudio-ABI-Fessel (DEP-4) gleich mit eliminiert (PyQt6 6.10 ist da).
2. **Mix-Quelle für die Vorschau:** woher kommt der hörbare Mix-Ausschnitt?
   `audio_routing.get_speech_audio_segment` liefert AudioSegment (RAM) — für
   einen Qt-Audioplayer brauchst du evtl. eine Datei/Puffer. Mix-vorhanden →
   Mix; sonst echte Mics (gleiche #71a-Regel).
3. **Per-Kamera-Offset:** das Mix↔Video-Mapping (`_video_to_mix_ms`) muss
   erhalten bleiben, damit Bild und Ton trotz Kamera-Versatz zusammenpassen.
4. **Clip-Ende:** beide Spuren müssen am selben Out-Punkt stoppen (heute pausiert
   nur das Video bei `_clip_out_ms`).
5. **Drift-Messskript als Pflicht-Gate (Carl-Forderung):** ein Test/Skript, das
   einen bekannten Clip abspielt und die Ton-gegen-Bild-Abweichung über die
   Cliplänge misst und unter einer Schwelle (z.B. ≤ 1 Frame / 40ms) hält.
   Setzt voraus, dass beide Spuren eine abfragbare Position haben (→ spricht
   gegen reine simpleaudio-Lösung).

## Leitplanken
- **Pin-1 bleibt trivial erfüllt:** Wiedergabe fasst keinen Export/XML an —
  das byte-identische Keyboardstellen-XML ist nicht betroffen.
- **Keyboard-Mode-Preview** (kurzer Drücker-Ton) muss weiter funktionieren.
- **Kein Quickfix-Guard:** echte gemeinsame-Uhr-Lösung, nicht „Video zufällig
  mitstarten und hoffen".
- Wenn simpleaudio ersetzt wird: das ist auch ein Schritt gegen die
  Python-3.11-Fessel (DEP-1/DEP-4) — bewusst als Bonus, nicht als Scope-Creep.

## Betroffene Dateien (Erst-Einschätzung, Carl finalisiert)
`gui/video_preview_peak.py` (Player/Takt), `gui/review_page.py` (Dispatch
`on_play`/`_on_play_sinnabschnitt`/`_poll_playback`), `core/playback.py`
(simpleaudio → evtl. Qt-Audio), `core/session.py` (`play_current`),
ggf. `core/audio_routing.py` (Mix-Quelle als Datei/Puffer).
