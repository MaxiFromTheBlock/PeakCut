import os
from unittest.mock import MagicMock, patch

from core.exporters import TXTExporter, XMLExporter


class TestTXTExporter:
    """TXT export needs no audio files — only peaks + config."""

    def test_export_creates_file_with_guest_name(self, sample_project, sample_config, sample_peaks):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = []
        session.get_active_peaks.return_value = [(1, sample_peaks[0]), (2, sample_peaks[2])]

        result = TXTExporter().export(session)

        assert "Max Mustermann" in os.path.basename(result)
        assert result.endswith(".txt")
        assert os.path.exists(result)

    def test_export_contains_peak_data(self, sample_project, sample_config, sample_peaks):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = []
        session.get_active_peaks.return_value = [(1, sample_peaks[0]), (2, sample_peaks[2])]

        result = TXTExporter().export(session)

        with open(result) as f:
            content = f.read()
        assert "PEAK 1" in content
        assert "PEAK 2" in content

    def test_export_empty_peaks_returns_empty(self, sample_project, sample_config):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = []
        session.get_active_peaks.return_value = []

        assert TXTExporter().export(session) == ""


class TestXMLExporter:
    """XML export needs no real files — only ffprobe calls need mocking."""

    @patch("core.exporters._probe_video_info", return_value=(1920, 1080))
    @patch("core.exporters._probe_audio_info", return_value=(48000, 16, 2))
    def test_export_creates_xml_with_guest_name(self, _mock_audio, _mock_video,
                                                 sample_project, sample_config, sample_peaks):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = [("CAM_A.mp4", "00:00:01:00")]
        session.get_active_peaks.return_value = [(1, sample_peaks[0]), (2, sample_peaks[2])]

        result = XMLExporter().export(session)

        assert "Max Mustermann" in os.path.basename(result)
        assert result.endswith(".xml")
        assert os.path.exists(result)

    @patch("core.exporters._probe_video_info", return_value=(1920, 1080))
    @patch("core.exporters._probe_audio_info", return_value=(48000, 16, 2))
    def test_xml_contains_video_tracks(self, _mock_audio, _mock_video,
                                        sample_project, sample_config, sample_peaks):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = [("CAM_A.mp4", "00:00:01:00")]
        session.get_active_peaks.return_value = [(1, sample_peaks[0]), (2, sample_peaks[2])]

        result = XMLExporter().export(session)

        with open(result) as f:
            content = f.read()
        # Video track references the actual external path
        assert "CAM_A.mp4" in content
        assert "/external/recordings/CAM_A.mp4" in content

    @patch("core.exporters._probe_video_info", return_value=(1920, 1080))
    @patch("core.exporters._probe_audio_info", return_value=(48000, 16, 2))
    def test_xml_contains_audio_tracks(self, _mock_audio, _mock_video,
                                        sample_project, sample_config, sample_peaks):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = []
        session.get_active_peaks.return_value = [(1, sample_peaks[0])]

        result = XMLExporter().export(session)

        with open(result) as f:
            content = f.read()
        # Audio tracks reference the actual mic files
        assert "Podcast - Max Mustermann mix" in content
        assert "Podcast - Max Mustermann mic1" in content

    @patch("core.exporters._probe_video_info", return_value=(1920, 1080))
    @patch("core.exporters._probe_audio_info", return_value=(48000, 16, 2))
    def test_export_empty_peaks_returns_empty(self, _mock_audio, _mock_video,
                                              sample_project, sample_config):
        session = MagicMock()
        session.project = sample_project
        session.config = sample_config
        session.video_offsets = []
        session.get_active_peaks.return_value = []

        assert XMLExporter().export(session) == ""
