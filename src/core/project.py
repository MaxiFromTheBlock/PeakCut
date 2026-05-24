import os


class PeakCutProject:
    """Knows all files in a project."""

    def __init__(self):
        self.keyboard_track: str | None = None
        self.mic_tracks: list[str] = []
        self.videos: list[str] = []
        self._guest_name: str | None = None
        self._export_dir: str | None = None

    def set_files(self, keyboard: str | None, mics: list[str], videos: list[str]):
        """Manual file assignment (when auto-detection doesn't work)."""
        self.keyboard_track = keyboard
        self.mic_tracks = list(mics)
        self.videos = list(videos)
        self._guest_name = None  # Reset cache

    def get_all_file_paths(self) -> list[str]:
        """Return all known file paths in this project."""
        paths = list(self.mic_tracks) + list(self.videos)
        if self.keyboard_track:
            paths.append(self.keyboard_track)
        return paths

    @property
    def export_dir(self) -> str:
        """Export directory: ~/Downloads/{guest_name} - PeakCut Export/"""
        if self._export_dir is not None:
            return self._export_dir
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        return os.path.join(downloads, f"{self.guest_name} - PeakCut Export")

    @export_dir.setter
    def export_dir(self, value: str):
        """Override default export directory (used in tests)."""
        self._export_dir = value

    @property
    def guest_name(self) -> str:
        """Guest name: user-set or auto-detected from 'mix' filename."""
        if self._guest_name is None:
            from core.guest_name import extract_guest_name
            self._guest_name = extract_guest_name(self.get_all_file_paths())
        return self._guest_name

    @guest_name.setter
    def guest_name(self, value: str):
        """Override auto-detected guest name with user-provided value."""
        self._guest_name = value

    def get_reference_track(self) -> str | None:
        """Find the mix reference track. Delegates to the central
        token-aware heuristic in ``core.audio_routing`` so the
        whole codebase shares one source of truth (#71a, 2026-05-21).
        """
        from .audio_routing import get_mix_track
        return get_mix_track(self)
