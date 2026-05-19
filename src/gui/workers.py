# workers.py - Background workers for analysis and export

import os
import sys
import json
import subprocess
import multiprocessing
import queue
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

import config
from utils import FROZEN, TEMP_DIR
from core.exporters import MP3Exporter, XMLExporter, TXTExporter
from core.media_probe import probe_duration_ms
from core.folgenschnitt_exporter import FolgenschnittXMLExporter
from core.folgenschnitt_pipeline import SKIP_REASON, prepare_folgenschnitt_for_export

_ANALYSIS_TIMEOUT_S = 600  # 10 minutes max


def _analysis_worker_target(config_data, result_queue, progress_queue):
    """Target function for multiprocessing.Process (must be top-level for pickling)."""
    from core.analysis_process import run_analysis, progress as _orig_progress

    # Monkey-patch progress function to use queue instead of stderr
    import core.analysis_process as ap
    ap.progress = lambda msg: progress_queue.put(msg)
    ap.error = lambda msg: progress_queue.put(f"Fehler: {msg}")

    try:
        results = run_analysis(config_data)
        result_queue.put(results)
    except Exception as e:
        result_queue.put({"error": str(e), "peaks": [], "video_offsets": []})


class AnalysisWorker(QThread):
    """Runs analysis in separate process with timeout protection."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session, *,
                 process_factory=multiprocessing.Process,
                 queue_factory=multiprocessing.Queue,
                 popen_factory=subprocess.Popen,
                 monotonic=time.monotonic,
                 analysis_timeout_s=_ANALYSIS_TIMEOUT_S,
                 progress_poll_s=0.2):
        super().__init__()
        self.session = session
        self._process_factory = process_factory
        self._queue_factory = queue_factory
        self._popen_factory = popen_factory
        self._monotonic = monotonic
        self._analysis_timeout_s = analysis_timeout_s
        self._progress_poll_s = progress_poll_s

        self._process_lock = threading.Lock()
        self._process = None
        self._stop_requested = False
        self._timed_out = False

    # --- Prozess-Lebenszyklus (duck-typed: multiprocessing.Process ODER
    # subprocess.Popen). EINZIGE Stelle, die das Handle anfasst. ---

    def _set_process(self, proc):
        with self._process_lock:
            self._process = proc

    def _clear_process(self, proc):
        with self._process_lock:
            if self._process is proc:
                self._process = None

    @staticmethod
    def _is_process_running(proc):
        if proc is None:
            return False
        if hasattr(proc, "is_alive"):
            return proc.is_alive()
        return proc.poll() is None  # subprocess.Popen

    @staticmethod
    def _wait_process(proc, timeout_s):
        if proc is None:
            return
        if hasattr(proc, "join"):          # multiprocessing.Process
            proc.join(timeout=timeout_s)
        elif hasattr(proc, "wait"):        # subprocess.Popen
            try:
                proc.wait(timeout=timeout_s)
            except Exception:
                pass

    def _terminate_process(self, proc, grace_s=2.0):
        if proc is None or not self._is_process_running(proc):
            return
        try:
            proc.terminate()
        except Exception:
            pass
        self._wait_process(proc, grace_s)
        if self._is_process_running(proc):
            try:
                proc.kill()
            except Exception:
                pass
            self._wait_process(proc, grace_s)

    def _terminate_current_process(self):
        with self._process_lock:
            proc = self._process
        self._terminate_process(proc)

    def request_stop(self):
        """Öffentliche Lifecycle-API: beendet den aktuellen Child-Prozess
        (egal ob Subprocess oder Multiprocess). Danach darf niemand mehr
        in _process greifen."""
        with self._process_lock:
            self._stop_requested = True
        self._terminate_current_process()

    def _mark_timeout_and_terminate_current_process(self):
        with self._process_lock:
            self._timed_out = True
        self._terminate_current_process()

    def run(self):
        project = self.session.project

        # Pre-flight: verify all files exist
        all_files = project.get_all_file_paths()
        for f in all_files:
            if not os.path.exists(f):
                self.error.emit(f"Datei nicht gefunden: {os.path.basename(f)}")
                return

        cfg = self.session.config

        guest = (project.guest_name or "").strip()
        guest_person = guest if guest and guest.lower() != "unknown" else "Gast"

        config_data = {
            "keyboard_track": project.keyboard_track,
            "mic_tracks": project.mic_tracks,
            "videos": project.videos,
            "reference_track": project.get_reference_track(),
            "temp_dir": TEMP_DIR,
            "export_dir": project.export_dir,
            "default_people": ["Matze", guest_person],
            "config": cfg
        }

        if FROZEN:
            self._run_multiprocess(config_data)
        else:
            self._run_subprocess(config_data)

    def _run_multiprocess(self, config_data):
        """Run analysis via multiprocessing (for bundled .app)."""
        result_queue = self._queue_factory()
        progress_queue = self._queue_factory()

        proc = self._process_factory(
            target=_analysis_worker_target,
            args=(config_data, result_queue, progress_queue),
        )
        proc.start()
        self._set_process(proc)

        deadline = self._monotonic() + self._analysis_timeout_s

        while self._is_process_running(proc):
            try:
                self.progress.emit(progress_queue.get(
                    timeout=self._progress_poll_s))
            except queue.Empty:
                pass
            if self._monotonic() >= deadline:
                self._mark_timeout_and_terminate_current_process()
                self._clear_process(proc)
                self.error.emit("Analyse abgebrochen: Timeout (>10 Min)")
                return

        # Drain remaining progress messages
        while not progress_queue.empty():
            try:
                self.progress.emit(progress_queue.get_nowait())
            except queue.Empty:
                break

        self._wait_process(proc, 0)
        self._clear_process(proc)

        if self._stop_requested:
            return  # bewusst still beendet
        if proc.exitcode is None:
            self.error.emit("Analyse fehlgeschlagen: Prozessstatus unbekannt")
            return
        if proc.exitcode != 0:
            self.error.emit("Analyse fehlgeschlagen")
            return

        try:
            results = result_queue.get(timeout=5)
            if results.get("error"):
                self.error.emit(results["error"])
            else:
                self.finished.emit(results)
        except queue.Empty:
            self.error.emit("Keine Analyse-Ergebnisse erhalten")

    def _run_subprocess(self, config_data):
        """Run analysis via subprocess (development mode)."""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(script_dir, "core", "analysis_process.py")
        python_exe = sys.executable

        proc = None
        try:
            proc = self._popen_factory(
                [python_exe, script_path, json.dumps(config_data)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=script_dir
            )
            self._set_process(proc)

            # Watchdog über den gemeinsamen Lifecycle-Helfer (kein
            # ungeschützter self._process-Zugriff aus dem Lambda mehr).
            watchdog = threading.Timer(
                self._analysis_timeout_s,
                self._mark_timeout_and_terminate_current_process,
            )
            watchdog.daemon = True
            watchdog.start()

            stdout_queue = queue.Queue()

            def read_stdout(p=proc):
                stdout_queue.put(p.stdout.read())

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()

            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break
                line = line.strip()
                if line.startswith("PROGRESS: "):
                    self.progress.emit(line[10:])
                elif line.startswith("ERROR: "):
                    self.progress.emit(f"Fehler: {line[7:]}")

            watchdog.cancel()
            stdout_thread.join(timeout=10)
            try:
                stdout = stdout_queue.get(timeout=1)
            except queue.Empty:
                stdout = ""

            self._clear_process(proc)

            if self._stop_requested:
                return  # bewusst still beendet
            if self._timed_out:
                self.error.emit("Analyse abgebrochen: Timeout (>10 Min)")
                return
            if proc.returncode != 0:
                self.error.emit(
                    f"Analyse-Prozess beendet mit Code {proc.returncode}")
                return

            try:
                results = json.loads(stdout)
                if results.get("error"):
                    self.error.emit(results["error"])
                else:
                    self.finished.emit(results)
            except json.JSONDecodeError as e:
                self.error.emit(f"Ungültige Analyse-Ergebnisse: {e}")

        except Exception as e:
            self._terminate_process(proc)
            self._clear_process(proc)
            self.error.emit(f"Analyse fehlgeschlagen: {e}")


def _build_exporters(session):
    exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
    if getattr(session, "folgenschnitt_edit_decisions", None):
        exporters.append(FolgenschnittXMLExporter())
    return exporters


class ExportWorker(QThread):
    """Runs export in background thread to keep UI responsive."""
    finished = pyqtSignal(list)   # list of exported file paths
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            # Hard guardrail: Folgenschnitt prep must never break the base
            # (Keyboardstellen) export. Any failure becomes a skip notice.
            try:
                reason = prepare_folgenschnitt_for_export(self.session)
            except Exception:
                self.session.speaker_turns = []
                self.session.folgenschnitt_edit_decisions = []
                self.session.folgenschnitt_skip_reason = SKIP_REASON
                reason = SKIP_REASON
            if reason:
                self.progress.emit(f"Folgenschnitt-XML uebersprungen - {reason}")

            exported = []
            exporters = _build_exporters(self.session)
            for exporter in exporters:
                result = exporter.export(self.session)
                if result:
                    self.progress.emit(f"Exportiert: {os.path.basename(result)}")
                    exported.append(result)

            if exported:
                import datetime
                done_path = os.path.join(
                    self.session.project.export_dir, ".peakcut_done"
                )
                with open(done_path, "w") as f:
                    f.write(datetime.datetime.now().isoformat() + "\n")

            self.finished.emit(exported)
        except Exception as e:
            self.error.emit(str(e))


_TRANSCRIPT_TIMEOUT_S = 1800  # 30 min Default (config-überschreibbar)
# P2 (Carl): expliziter spawn-Context — eine Lebenszyklus-Linie, aber
# KEIN versehentlicher Fork (PyQt/macOS-Historie).
_TRANSCRIPT_MP_CONTEXT = multiprocessing.get_context("spawn")


class TranscriptWorker(QThread):
    """Roadmap #3 Stufe A — Transkription früh & parallel zur Analyse.

    Eigener entkoppelter Job. Schreibt das transcript.json-Sidecar über
    den Gate-A-Besitz-Vertrag (transcript_archive); ruft NIE
    save_project_archive (project.json-Referenz kommt erst durch
    späteres Autosave). HC-2-Lebenszyklus: request_stop() ohne blindes
    wait(). Kein Mix -> kontrollierter Skip. Echtes Whisper nur im
    Child (transcription_process). Bewusst EIN Prozess-Pfad (kein
    Popen-Zweig) — kleinere fragile Fläche als AnalysisWorker.
    """
    finished = pyqtSignal(dict)   # Referenzblock (oder {} bei Skip)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session, *,
                 process_factory=_TRANSCRIPT_MP_CONTEXT.Process,
                 queue_factory=_TRANSCRIPT_MP_CONTEXT.Queue,
                 monotonic=time.monotonic,
                 transcription_timeout_s=_TRANSCRIPT_TIMEOUT_S,
                 progress_poll_s=0.2):
        super().__init__()
        self.session = session
        self._process_factory = process_factory
        self._queue_factory = queue_factory
        self._monotonic = monotonic
        self._timeout_s = transcription_timeout_s
        self._progress_poll_s = progress_poll_s
        self._process_lock = threading.Lock()
        self._process = None
        self._stop_requested = False
        self._timed_out = False

    # --- Lebenszyklus (HC-2-Stil, duck-typed) ---

    def _set_process(self, proc):
        with self._process_lock:
            self._process = proc

    def _clear_process(self, proc):
        with self._process_lock:
            if self._process is proc:
                self._process = None

    @staticmethod
    def _is_process_running(proc):
        if proc is None:
            return False
        if hasattr(proc, "is_alive"):
            return proc.is_alive()
        return proc.poll() is None

    @staticmethod
    def _wait_process(proc, timeout_s):
        if proc is None:
            return
        if hasattr(proc, "join"):
            proc.join(timeout=timeout_s)
        elif hasattr(proc, "wait"):
            try:
                proc.wait(timeout=timeout_s)
            except Exception:
                pass

    def _terminate_process(self, proc, grace_s=2.0):
        if proc is None or not self._is_process_running(proc):
            return
        try:
            proc.terminate()
        except Exception:
            pass
        self._wait_process(proc, grace_s)
        if self._is_process_running(proc):
            try:
                proc.kill()
            except Exception:
                pass
            self._wait_process(proc, grace_s)

    def _terminate_current_process(self):
        with self._process_lock:
            proc = self._process
        self._terminate_process(proc)

    def request_stop(self):
        """Öffentliche Lifecycle-API: beendet den Child-Prozess (kein
        blindes wait())."""
        with self._process_lock:
            self._stop_requested = True
        self._terminate_current_process()

    def _mark_timeout_and_terminate(self):
        with self._process_lock:
            self._timed_out = True
        self._terminate_current_process()

    # --- Run ---

    def _cfg(self, key, default):
        cfg = getattr(self.session, "config", None)
        getter = getattr(cfg, "get", None)
        if getter is None:
            return default
        val = getter(key, default)
        return default if val is None else val

    def run(self):
        # Notbremse-Doppelsicherung (Start-Gate sitzt in MainWindow).
        if not self._cfg("smart_boundary_enabled", True):
            return
        project = self.session.project
        reference = project.get_reference_track()
        if not reference:
            self.progress.emit(
                "Sinnabschnitte: kein Mix gefunden — übersprungen")
            self.finished.emit({})
            return

        # Fallback = config.DEFAULTS (Single Source of Truth) — KEIN
        # zweites Literal mehr (Carl-Gegencheck: Drift DEFAULTS<->Worker
        # strukturell ausgeschlossen).
        _D = config.DEFAULTS
        engine = self._cfg("smart_boundary_whisper_engine",
                           _D["smart_boundary_whisper_engine"])
        model = self._cfg("smart_boundary_whisper_model",
                          _D["smart_boundary_whisper_model"])
        language = self._cfg("smart_boundary_language",
                             _D["smart_boundary_language"])

        # Parent löst Root/Pfad + Referenzblock auf (kein project-
        # Pickling ins Child); das Child schreibt das Sidecar selbst
        # (P1: nicht das volle Transcript durch die Queue).
        from core.transcript_archive import (
            transcript_sidecar_path, build_transcript_ref,
            transcript_root, cache_reusable_ref, alignment_drift)
        ref = build_transcript_ref(
            project, engine=engine, model=model, language=language,
            audio_path=reference)

        # #3-Revision R6 — Cache: passt ein gespeicherter Verweis zum
        # aktuellen Mix (Fingerabdruck + Engine/Modell/Sprache) und ist
        # das Sidecar lesbar -> KEIN Whisper.
        cached = cache_reusable_ref(
            getattr(self.session, "transcript_ref", None),
            current_fingerprint=ref.get("audio_fingerprint"),
            engine=engine, model=model, language=language,
            root=transcript_root(project))
        if cached is not None:
            self.session.transcript = None
            self.session.transcript_ref = cached
            self.session.transcript_error = None
            self.progress.emit(
                "Sinnabschnitte: Transkript aus Cache übernommen — "
                "kein Whisper")
            self.finished.emit(cached)
            return

        req = {
            "audio_path": reference,
            "engine": engine,
            "model": model,
            "language": language,
            "sidecar_path": transcript_sidecar_path(project),
            "transcript_ref": ref,
        }

        from core.transcription_process import _transcribe_worker_target

        result_queue = self._queue_factory()
        progress_queue = self._queue_factory()
        proc = self._process_factory(
            target=_transcribe_worker_target,
            args=(req, result_queue, progress_queue))
        proc.start()
        self._set_process(proc)

        deadline = self._monotonic() + self._timeout_s
        while self._is_process_running(proc):
            try:
                self.progress.emit(progress_queue.get(
                    timeout=self._progress_poll_s))
            except queue.Empty:
                pass
            if self._monotonic() >= deadline:
                self._mark_timeout_and_terminate()
                self._clear_process(proc)
                self.progress.emit(
                    "Sinnabschnitte: Transkription Timeout — übersprungen")
                return

        while not progress_queue.empty():
            try:
                self.progress.emit(progress_queue.get_nowait())
            except queue.Empty:
                break

        self._wait_process(proc, 0)
        self._clear_process(proc)

        if self._stop_requested:
            return  # bewusst still beendet
        exitcode = getattr(proc, "exitcode", 0)
        if exitcode not in (0, None) and exitcode is not None:
            self.progress.emit(
                "Sinnabschnitte: Transkription fehlgeschlagen — übersprungen")
            return

        try:
            result = result_queue.get(timeout=5)
        except queue.Empty:
            self.progress.emit(
                "Sinnabschnitte: kein Transkript erhalten — übersprungen")
            return

        if not isinstance(result, dict) or result.get("error") or \
                "ref" not in result:
            self.progress.emit(
                "Sinnabschnitte: Transkription fehlgeschlagen — übersprungen")
            return

        # Child hat das Sidecar schon geschrieben und gibt nur den
        # kleinen Referenzblock zurück. Besitz-Vertrag: KEIN
        # save_project_archive (project.json-Referenz erst durch
        # späteres Autosave). transcript bleibt None — Stufe B liest
        # laut Spec ohnehin nur das gespeicherte Sidecar.
        final_ref = dict(result["ref"])

        # #3-Revision R2 — Ausricht-Schutz: Text-Gesamtspanne (vom
        # Child) gegen Mix-Dauer (gemeinsamer ffprobe-Helfer). Drift
        # -> LAUTER Hinweis; Sinnabschnitte werden nicht still
        # berechnet (Stufe B konsumiert die Felder).
        duration_ms = probe_duration_ms(reference)
        if duration_ms is not None:
            final_ref["audio_duration_ms"] = duration_ms
        span_ms = final_ref.get("transcript_span_ms")
        tol = self._cfg("smart_boundary_alignment_tolerance_ms",
                        _D["smart_boundary_alignment_tolerance_ms"])
        if duration_ms is None:
            self.progress.emit(
                "Sinnabschnitte: Audiodauer nicht ermittelbar — "
                "Ausrichtung ungeprüft")
        elif span_ms is not None and alignment_drift(span_ms, duration_ms,
                                                     tol):
            self.progress.emit(
                f"Sinnabschnitte: Transkript passt nicht zur Audiodauer "
                f"(Text {int(span_ms) // 1000}s vs Audio "
                f"{duration_ms // 1000}s) — werden NICHT still berechnet")

        self.session.transcript = None
        self.session.transcript_ref = final_ref
        self.session.transcript_error = None
        self.finished.emit(final_ref)


class SmartBoundaryWorker(QThread):
    """Roadmap #3 Stufe B — läuft NACH dem Export-Handoff (Task 8
    hängt ihn ein). Konsumiert nur das gespeicherte Transkript, füllt
    ClipCandidate je Drücker. Kein Subprozess (schnell, da das Schwere
    in Stufe A lief) — kooperativer Abbruch via request_stop()."""
    finished = pyqtSignal(list)   # aktualisierte ClipCandidate-Liste
    progress = pyqtSignal(str)

    def __init__(self, session, decider):
        super().__init__()
        self.session = session
        self._decider = decider
        self._stop = False

    def request_stop(self):
        """Kooperativ: die Pipeline prüft zwischen den Peaks."""
        self._stop = True

    def run(self):
        from core.clip_boundary.pipeline import prepare_smart_boundaries
        try:
            result = prepare_smart_boundaries(
                self.session, self._decider,
                config=getattr(self.session, "config", {}),
                should_stop=lambda: self._stop)
        except Exception as e:  # noqa: BLE001 — nie den Flow brechen
            self.progress.emit(
                f"Sinnabschnitte: übersprungen — {e}")
            result = getattr(self.session, "clip_candidates", [])
        self.finished.emit(result)
