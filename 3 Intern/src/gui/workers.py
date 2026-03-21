# workers.py - Background workers for analysis and export

import os
import sys
import json
import subprocess
import queue
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from utils import TEMP_DIR
from core.exporters import MP3Exporter, XMLExporter, TXTExporter

_ANALYSIS_TIMEOUT_S = 600  # 10 minutes max


class AnalysisWorker(QThread):
    """Runs analysis in separate process with timeout protection."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self._process = None

    def run(self):
        project = self.session.project

        # Pre-flight: verify all files exist
        all_files = project.get_all_file_paths()
        for f in all_files:
            if not os.path.exists(f):
                self.error.emit(f"Datei nicht gefunden: {os.path.basename(f)}")
                return

        cfg = self.session.config

        config_data = {
            "keyboard_track": project.keyboard_track,
            "mic_tracks": project.mic_tracks,
            "videos": project.videos,
            "reference_track": project.get_reference_track(),
            "temp_dir": TEMP_DIR,
            "export_dir": project.export_dir,
            "config": cfg
        }

        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(script_dir, "core", "analysis_process.py")
        python_exe = sys.executable

        try:
            self._process = subprocess.Popen(
                [python_exe, script_path, json.dumps(config_data)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=script_dir
            )

            # Watchdog: kill process if analysis takes too long
            watchdog = threading.Timer(
                _ANALYSIS_TIMEOUT_S,
                lambda: self._process.kill() if self._process and self._process.poll() is None else None
            )
            watchdog.daemon = True
            watchdog.start()

            stdout_queue = queue.Queue()

            def read_stdout():
                stdout_data = self._process.stdout.read()
                stdout_queue.put(stdout_data)

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stdout_thread.start()

            while True:
                line = self._process.stderr.readline()
                if not line and self._process.poll() is not None:
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

            if self._process.returncode != 0:
                if self._process.returncode == -9:
                    self.error.emit("Analyse abgebrochen: Timeout (>10 Min)")
                else:
                    self.error.emit(f"Analyse-Prozess beendet mit Code {self._process.returncode}")
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
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except Exception:
                    self._process.kill()
            self.error.emit(f"Analyse fehlgeschlagen: {e}")


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
            exported = []
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter()]
            for exporter in exporters:
                result = exporter.export(self.session)
                if result:
                    self.progress.emit(f"Exportiert: {os.path.basename(result)}")
                    exported.append(result)
            self.finished.emit(exported)
        except Exception as e:
            self.error.emit(str(e))
