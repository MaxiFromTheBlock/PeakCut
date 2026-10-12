from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_claude_key_setup_uses_checkout_instead_of_user_path():
    script = (ROOT / "scripts" / "setup_claude_key.sh").read_text()
    assert 'os.environ["REPO_ROOT"]' in script
    assert "/Users/max/" not in script


def test_launcher_is_checkout_relative_and_refuses_overwrite():
    script = (ROOT / "scripts" / "install_launcher.sh").read_text()
    assert 'REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"' in script
    assert 'if [[ -e "$TARGET" ]]' in script
    assert "/Users/max/" not in script


def test_real_smoke_requires_explicit_akte_instead_of_user_path():
    script = (ROOT / "scripts" / "smoke_multitrack_export.py").read_text()
    assert "PEAKCUT_SMOKE_AKTE" in script
    assert "/Users/max/" not in script
