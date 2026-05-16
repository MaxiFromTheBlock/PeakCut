import inspect

from gui.main_window import MainWindow, default_import_folder


def test_default_import_folder_is_always_desktop():
    assert default_import_folder().endswith("/Desktop")


def test_on_import_no_longer_reads_or_writes_last_folder():
    source = inspect.getsource(MainWindow._on_import)

    assert "last_folder" not in source
    assert "setValue" not in source
