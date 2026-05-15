from core.guest_name import extract_guest_name


class TestExtractGuestName:

    def test_name_from_mix_file(self):
        files = ["/any/path/Podcast - Paul Ronzheimer mix.wav"]
        assert extract_guest_name(files) == "Paul Ronzheimer"

    def test_name_from_external_paths(self):
        """Files imported from external location (not in material_dir)."""
        files = [
            "/Users/editor/Desktop/recordings/keys.wav",
            "/Volumes/SSD/audio/Hotel Matze - Sarah Connor mix.wav",
            "/Volumes/SSD/audio/Hotel Matze - Sarah Connor mic1.wav",
        ]
        assert extract_guest_name(files) == "Sarah Connor"

    def test_no_mix_file_returns_unknown(self):
        files = ["/path/keyboard.wav", "/path/mic1.wav"]
        assert extract_guest_name(files) == "Unknown"

    def test_empty_list_returns_unknown(self):
        assert extract_guest_name([]) == "Unknown"

    def test_name_with_parentheses_stripped(self):
        files = ["/path/Podcast - Max Mustermann (final) mix.wav"]
        assert extract_guest_name(files) == "Max Mustermann"

    def test_case_insensitive_mix_detection(self):
        files = ["/path/Podcast - Jane Doe MIX.wav"]
        assert extract_guest_name(files) == "Jane Doe"

    def test_no_material_dir_parameter(self):
        """Function signature should only have file_paths, not material_dir."""
        import inspect
        sig = inspect.signature(extract_guest_name)
        param_names = list(sig.parameters.keys())
        assert "material_dir" not in param_names
        assert "file_paths" in param_names
