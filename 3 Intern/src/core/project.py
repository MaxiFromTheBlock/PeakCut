import os


class PeakCutProject:
    """Knows all files in a project."""

    def __init__(self, material_dir: str, export_dir: str):
        self.material_dir = material_dir
        self.export_dir = export_dir
        self.keyboard_track: str | None = None
        self.mic_tracks: list[str] = []
        self.videos: list[str] = []

    def scan(self):
        """Scan material_dir and categorize files."""
        self.keyboard_track = None
        self.mic_tracks = []
        self.videos = []

        if not os.path.exists(self.material_dir):
            return

        audio_files = []

        for f in os.listdir(self.material_dir):
            fl = f.lower()
            filepath = os.path.join(self.material_dir, f)

            if fl.endswith(('.mp4', '.mov')):
                self.videos.append(filepath)
            elif fl.endswith(('.wav', '.mp3')):
                audio_files.append(filepath)
                if any(kw in fl for kw in ["keyboard", "keys", "klavier"]):
                    self.keyboard_track = filepath

        # Everything that's not the keyboard track is a mic track
        self.mic_tracks = [f for f in audio_files if f != self.keyboard_track]

    def set_files(self, keyboard: str | None, mics: list[str], videos: list[str]):
        """Manual file assignment (when auto-detection doesn't work)."""
        self.keyboard_track = keyboard
        self.mic_tracks = list(mics)
        self.videos = list(videos)

    def get_reference_track(self) -> str | None:
        """Find the 'mix' reference track for video sync."""
        for f in self.mic_tracks:
            if 'mix' in os.path.basename(f).lower():
                return f
        return None
