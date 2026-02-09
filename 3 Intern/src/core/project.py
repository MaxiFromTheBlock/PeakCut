import os


class PeakCutProject:
    """Knows all files in a project."""

    def __init__(self, material_dir: str, export_dir: str):
        self.material_dir = material_dir
        self.export_dir = export_dir
        self.keyboard_track: str | None = None
        self.mic_tracks: list[str] = []
        self.videos: list[str] = []

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
