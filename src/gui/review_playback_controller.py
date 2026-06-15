"""#76 Task 5 — Qt Playback Controller (Carl-Plan 2026-06-15).

Gemeinsame, messbare Uhr für die synchrone Ton+Bild-Vorschau:
- Audio (eigener QMediaPlayer) = MASTER.
- Video (PeakVideoPreview, stumm) folgt; bei Drift > Toleranz wird das Bild
  auf die Audio-Timeline korrigiert.

Drei Schärfungen (Claude-Cross-Review, von Carl eingearbeitet):
1. Readiness-Gate: gemeinsamer Start erst, wenn BEIDE Medien geladen sind
   (Timeout -> kontrollierter Fehler, kein hängender Play-Button).
2. Harter Lifecycle (stop/cleanup, idempotent) — schließt CONC-3 mit
   (zweiter QMediaPlayer wird sauber heruntergefahren).
3. Drift-Bremse alle tick_ms; Audio-Position -> Mix-Timeline gemappt.

Voll mit Fake-Playern testbar (audio_player_factory / audio_ready_states).
"""

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal


class ReviewPlaybackController(QObject):
    finished = pyqtSignal()
    drift_updated = pyqtSignal(int)   # POST-Korrektur-Restdrift (Gate-Wert)
    corrected = pyqtSignal()          # separate Diagnose: eine Korrektur
    error = pyqtSignal(str)

    def __init__(self, video_preview, *, tolerance_ms=40, ready_timeout_ms=5000,
                 tick_ms=100, audio_player_factory=None, audio_ready_states=None):
        super().__init__()
        self._video = video_preview
        self._tolerance = tolerance_ms
        self._window = None
        self._source = None
        self._started = False
        self._active = False

        if audio_player_factory is None:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._audio = QMediaPlayer()
            self._audio_out = QAudioOutput()
            self._audio.setAudioOutput(self._audio_out)
            if audio_ready_states is None:
                audio_ready_states = {QMediaPlayer.MediaStatus.LoadedMedia,
                                      QMediaPlayer.MediaStatus.BufferedMedia}
        else:
            self._audio = audio_player_factory()
            self._audio_out = None
        self._ready_states = set(audio_ready_states or ())

        self._tick = QTimer(self)
        self._tick.setInterval(tick_ms)
        self._tick.timeout.connect(self._on_tick)

        self._ready_timer = QTimer(self)
        self._ready_timer.setSingleShot(True)
        self._ready_timer.setInterval(ready_timeout_ms)
        self._ready_timer.timeout.connect(self._on_ready_timeout)

        # Async-Readiness: erneut versuchen, sobald Audio ODER Video lädt.
        # (P1 Carl-Gate-E: nur auf Audio zu warten lief in den Timeout, wenn
        # das Video seine Duration erst nach dem Audio meldet.)
        for sig in (getattr(self._audio, "mediaStatusChanged", None),
                    getattr(self._video, "duration_changed", None)):
            if sig is not None and hasattr(sig, "connect"):
                try:
                    sig.connect(lambda *a: self._try_begin())
                except (TypeError, RuntimeError):
                    pass

    # --- öffentliche API ---

    def is_playing(self):
        return self._active

    def play(self, window, source):
        self.stop()
        if getattr(source, "disabled", False):
            self.error.emit(getattr(source, "disabled_reason",
                                    "Keine Audioquelle."))
            self.finished.emit()
            return
        self._window = window
        self._source = source
        self._started = False
        self._active = True
        self._video.prepare_clip(window.start_ms, window.end_ms)
        self._audio.setSource(QUrl.fromLocalFile(source.path))
        self._ready_timer.start()
        self._try_begin()

    def stop(self):
        self._tick.stop()
        self._ready_timer.stop()
        if self._active or self._started:
            self._safe_stop_players()
        self._active = False
        self._started = False

    def cleanup(self):
        self.stop()
        for obj in (self._audio, self._audio_out):
            if obj is not None and hasattr(obj, "deleteLater"):
                try:
                    obj.deleteLater()
                except RuntimeError:
                    pass

    # --- intern ---

    def _audio_ready(self):
        return self._audio.mediaStatus() in self._ready_states

    def _video_ready(self):
        return self._video.get_duration() > 0

    def _try_begin(self):
        if self._started or not self._active:
            return False
        if not (self._audio_ready() and self._video_ready()):
            return False
        self._begin()
        return True

    def _begin(self):
        self._started = True
        self._ready_timer.stop()
        self._audio.setPosition(self._source.media_start_ms)
        self._video.play_prepared()
        self._audio.play()
        self._tick.start()

    def _audio_timeline_ms(self):
        s = self._source
        return s.timeline_start_ms + (self._audio.position() - s.media_start_ms)

    def _on_tick(self):
        if not (self._active and self._started):
            return
        audio_t = self._audio_timeline_ms()
        if audio_t >= self._window.end_ms:
            self._finish()
            return
        video_t = self._video.current_mix_position()
        drift = abs(video_t - audio_t)
        # P1 Carl-Gate-E: bei Drift > Toleranz Bild auf die Audio-Timeline
        # schnappen; gemeldet wird der RESTdrift (Gate-Wert), nicht der
        # Vor-Korrektur-Wert. Korrekturen separat zählen (Diagnose).
        if drift > self._tolerance:
            self._video.set_position(audio_t)
            self.corrected.emit()
            residual = 0
        else:
            residual = drift
        self.drift_updated.emit(int(residual))

    def _finish(self):
        self._tick.stop()
        self._safe_stop_players()
        self._active = False
        self._started = False
        self.finished.emit()

    def _on_ready_timeout(self):
        if self._started or not self._active:
            return
        self.error.emit("Wiedergabe konnte nicht starten — Medien nicht bereit.")
        self.stop()
        self.finished.emit()

    def _safe_stop_players(self):
        out = self._window.end_ms if self._window else None
        try:
            self._audio.stop()
        except RuntimeError:
            pass
        try:
            self._video.stop_clip_at(out)
        except (RuntimeError, AttributeError):
            pass
