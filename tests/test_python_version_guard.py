"""Hygiene — weiche Python-3.11-Versions-Wache.

Tickende Uhr: pydub hängt am stdlib-``audioop``, das in Python 3.13 wegfällt.
Die Wache WARNT nur (gibt einen Text zurück), blockiert NIE — der produktive
Launcher in /Applications darf an einer falschen Python-Version nicht still
stehen bleiben (sonst legt eine Fehlkonfiguration die App lahm).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils import REQUIRED_PYTHON, python_version_warning  # noqa: E402


def test_required_python_is_311():
    assert REQUIRED_PYTHON == (3, 11)


def test_no_warning_on_311():
    assert python_version_warning((3, 11, 9)) is None


def test_warning_on_313_names_both_versions():
    msg = python_version_warning((3, 13, 0))
    assert msg is not None
    assert "3.11" in msg and "3.13" in msg


def test_warning_on_310():
    assert python_version_warning((3, 10, 5)) is not None


def test_uses_running_interpreter_by_default():
    # Ohne Argument greift sys.version_info — diese Suite LÄUFT auf 3.11,
    # also darf der Default keine Warnung erzeugen.
    assert python_version_warning() is None
