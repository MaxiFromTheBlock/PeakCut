import os


class PeakCutProject:
    """Knows all files in a project."""

    def __init__(self):
        self._marker_track: str | None = None
        self.mic_tracks: list[str] = []
        self.mix_track: str | None = None
        self.transcript_path: str | None = None
        self.videos: list[str] = []
        self._guest_name: str | None = None
        self._export_dir: str | None = None

    @property
    def marker_track(self) -> str | None:
        """Canonical #77 marker slot."""
        return self._marker_track

    @marker_track.setter
    def marker_track(self, value: str | None):
        self._marker_track = value

    @property
    def keyboard_track(self) -> str | None:
        """Backward-compatible alias for marker_track."""
        return self._marker_track

    @keyboard_track.setter
    def keyboard_track(self, value: str | None):
        self._marker_track = value

    def set_files(
        self,
        keyboard: str | None,
        mics: list[str],
        videos: list[str],
        mix: str | None = None,
        transcript: str | None = None,
    ):
        """Manual file assignment (when auto-detection doesn't work)."""
        from .import_classifier import is_mix_track

        legacy_mix = next((p for p in (mics or []) if is_mix_track(p)), None)
        self.marker_track = keyboard
        self.mic_tracks = list(mics)
        self.mix_track = mix or legacy_mix
        self.transcript_path = transcript
        self.videos = list(videos)
        self._guest_name = None  # Reset cache

    def get_all_file_paths(self) -> list[str]:
        """Return all known file paths in this project."""
        paths = []
        for path in (
            list(self.mic_tracks)
            + ([self.mix_track] if self.mix_track else [])
            + list(self.videos)
            + ([self.marker_track] if self.marker_track else [])
            + ([self.transcript_path] if self.transcript_path else [])
        ):
            if path and path not in paths:
                paths.append(path)
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
        """Find the mix reference track.

        #77 Task 2: prefer the structural mix slot before legacy scans.
        This is Pin-1-relevant because XMLExporter probes this path for
        audio metadata (sample rate / bit depth / channel count).
        """
        if self.mix_track:
            return self.mix_track
        from .audio_routing import get_mix_track
        return get_mix_track(self)
