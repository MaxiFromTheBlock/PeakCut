from core.project import PeakCutProject


class TestPeakCutProject:

    def test_no_material_dir_attribute(self):
        project = PeakCutProject("/tmp/export")
        assert not hasattr(project, "material_dir")

    def test_get_all_file_paths(self):
        project = PeakCutProject("/tmp/export")
        project.set_files(
            keyboard="/path/keys.wav",
            mics=["/path/mix.wav", "/path/mic1.wav"],
            videos=["/path/cam.mp4"],
        )
        paths = project.get_all_file_paths()
        assert "/path/keys.wav" in paths
        assert "/path/mix.wav" in paths
        assert "/path/mic1.wav" in paths
        assert "/path/cam.mp4" in paths
        assert len(paths) == 4

    def test_get_all_file_paths_no_keyboard(self):
        project = PeakCutProject("/tmp/export")
        project.set_files(keyboard=None, mics=["/path/mic1.wav"], videos=[])
        paths = project.get_all_file_paths()
        assert len(paths) == 1

    def test_get_reference_track(self):
        project = PeakCutProject("/tmp/export")
        project.set_files(
            keyboard="/path/keys.wav",
            mics=["/path/Hotel Matze - Gast mix.wav", "/path/mic1.wav"],
            videos=[],
        )
        assert project.get_reference_track() == "/path/Hotel Matze - Gast mix.wav"

    def test_get_reference_track_none(self):
        project = PeakCutProject("/tmp/export")
        project.set_files(keyboard="/path/keys.wav", mics=["/path/mic1.wav"], videos=[])
        assert project.get_reference_track() is None
