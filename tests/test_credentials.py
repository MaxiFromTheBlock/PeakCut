"""#3-Revision Task 3 — Credential-Schicht (Spec §11 R3, Carl Task 3).

Sicherheitskritisch: der Key landet NIE in Git/config.json/Log. Tests
gehen NIE an die echte Keychain / kein echtes Anthropic — der
`security`-Aufruf ist injizierbar.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.credentials import (  # noqa: E402
    CredentialStatus, ClaudeCredentialProvider,
    KeychainCredentialProvider, validate_api_key,
    KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, CredentialError,
)
from core.clip_boundary.models import (  # noqa: E402
    BoundaryError, BoundaryInfraError)
from core.clip_boundary.decider import ClaudeBoundaryDecider  # noqa: E402

_GOOD = "sk-ant-api03-" + "a" * 95         # 108 Zeichen, realistisches Format


# --- Validierung (pur) ---------------------------------------------------

def test_validate_trims_and_accepts_clean_key():
    assert validate_api_key(f"  {_GOOD}  ") == _GOOD


def test_validate_rejects_empty_whitespace_nonascii_control_innerspace():
    bad = ["", "   ", "\t\n",
           "sk ant mit space",            # innenliegender Whitespace
           "sk-ant-€uro",                 # nicht-ASCII
           "sk-ant-\x07bell",             # Steuerzeichen
           "sk-ant- nbsp",           # typografischer Whitespace
           "sk-ant-smart“quote"]     # typografisches Zeichen
    for b in bad:
        try:
            validate_api_key(b)
            assert False, f"muss abgelehnt werden: {b!r}"
        except ValueError as e:
            # NIE den Key-Inhalt in der Fehlermeldung (nur sinnvoll
            # prüfbar, wenn überhaupt ein Inhalt da ist).
            if b.strip():
                assert b.strip() not in str(e)


def test_validate_error_never_leaks_key_value():
    try:
        validate_api_key("sk-geheim mit space")
        assert False
    except ValueError as e:
        assert "geheim" not in str(e)


# --- Fake security-CLI ---------------------------------------------------

class _FakeSecurity:
    """Ersetzt den `security`-Aufruf: Rückgabe (returncode, stdout)."""
    def __init__(self, stored=None):
        self.stored = stored
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[0] == "find-generic-password":
            if self.stored is None:
                return (44, "")          # errSecItemNotFound
            return (0, self.stored + "\n")
        if args[0] == "add-generic-password":
            # -w <wert> als letztes Paar
            self.stored = args[args.index("-w") + 1]
            return (0, "")
        return (1, "")


def _provider(stored=None, env=None):
    return KeychainCredentialProvider(
        runner=_FakeSecurity(stored), env=env if env is not None else {})


# --- Provider erfüllt den eingefrorenen Gate-A-Vertrag ------------------

def test_provider_satisfies_frozen_protocol():
    assert isinstance(_provider(), ClaudeCredentialProvider)


# --- Keychain primär -----------------------------------------------------

def test_keychain_hit_returns_key_and_ok_status():
    p = _provider(stored=_GOOD)
    assert p.get_api_key() == _GOOD
    st = p.status()
    assert isinstance(st, CredentialStatus)
    assert st.ok is True and st.reason == "ok"
    assert _GOOD not in st.message            # Status zeigt nie den Key


def test_keychain_missing_is_missing_status_no_key():
    p = _provider(stored=None)
    assert p.get_api_key() is None
    st = p.status()
    assert st.ok is False and st.reason == "missing"


def test_keychain_invalid_value_is_invalid_status_not_returned():
    p = _provider(stored="kaputter key mit space")
    assert p.get_api_key() is None            # ungültig -> nicht ausliefern
    st = p.status()
    assert st.ok is False and st.reason == "invalid"
    assert "space" not in st.message and "kaputter" not in st.message


# --- Env nur Dev-Fallback -----------------------------------------------

def test_env_is_only_dev_fallback_when_keychain_empty():
    p = _provider(stored=None, env={"ANTHROPIC_API_KEY": _GOOD})
    assert p.get_api_key() == _GOOD
    st = p.status()
    assert st.ok is True and st.reason == "env"   # bewusst als Dev markiert


def test_keychain_wins_over_env():
    other = "sk-ant-api03-" + "b" * 95   # auch realistisch lang
    p = _provider(stored=_GOOD, env={"ANTHROPIC_API_KEY": other})
    assert p.get_api_key() == _GOOD


# --- Speichern: validiert, geht in die Keychain, nie in config/log ------

def test_store_validates_then_persists_via_security():
    fake = _FakeSecurity()
    p = KeychainCredentialProvider(runner=fake, env={})
    neuer = "sk-ant-api03-" + "n" * 95     # realistisch lang
    p.store(f"  {neuer}  ")
    assert fake.stored == neuer                       # getrimmt
    add = [c for c in fake.calls if c[0] == "add-generic-password"][0]
    assert "-U" in add                                # -U = update erlaubt
    assert KEYCHAIN_SERVICE in add and KEYCHAIN_ACCOUNT in add
    try:
        p.store("ungueltig mit space")
        assert False, "ungültiger Key darf nicht gespeichert werden"
    except ValueError:
        pass


# --- Decider zieht den Key über den Provider ----------------------------

def test_decider_uses_provider_key_for_client():
    captured = {}

    class _FakeClient:
        def __init__(self, api_key=None):
            captured["key"] = api_key

        class messages:                       # noqa: N801
            @staticmethod
            def create(**kw):
                raise AssertionError("kein echter API-Call im Test")

    dec = ClaudeBoundaryDecider(
        model="claude-x", credential_provider=_provider(stored=_GOOD),
        client_factory=lambda api_key: _FakeClient(api_key=api_key))
    # _call baut den Client mit dem Provider-Key (kein echter Call).
    # Task-4-Update: client-Exceptions werden in BoundaryInfraError
    # gewandelt — der Client wurde aber VORHER mit dem Key gebaut.
    try:
        dec._call("prompt")
    except BoundaryInfraError:
        pass
    assert captured["key"] == _GOOD


# --- Carl-Gegenreview Findings (zwei P2) -------------------------------

def test_store_raises_on_security_failure_without_key_leak():
    # [P2] store() ignorierte den security-Returncode -> Aufrufer sah
    # "ok", obwohl gesperrt/permission/etc.
    class _FailingSec:
        stored = None
        calls = []
        def __call__(self, args):
            self.calls.append(args)
            if args[0] == "add-generic-password":
                return (1, "")            # security schlug fehl
            return (44, "")
    fake = _FailingSec()
    p = KeychainCredentialProvider(runner=fake, env={})
    secret = "sk-ant-api03-secret-" + "X" * 88   # realistisch lang
    try:
        p.store(secret)
        assert False, "muss bei security-Fehler werfen"
    except CredentialError as e:
        assert "secret" not in str(e)         # KEIN Key im Text
        assert "XXXX" not in str(e)
    assert fake.stored is None                 # nichts gespeichert


def test_decider_production_path_has_provider_by_default():
    # [P2] Decider ohne Provider fiel still auf anthropic.Anthropic()
    # zurück (SDK/Env, ohne Validierung/Keychain-Priorität). Im
    # Produktionspfad MUSS ein Provider gesetzt sein.
    dec = ClaudeBoundaryDecider(model="claude-x")
    assert dec._credential_provider is not None
    assert isinstance(dec._credential_provider, ClaudeCredentialProvider)


def test_env_invalid_with_empty_keychain_returns_none_and_invalid_status():
    p = _provider(stored=None, env={"ANTHROPIC_API_KEY": "kaputt mit space"})
    assert p.get_api_key() is None
    st = p.status()
    assert st.ok is False and st.reason == "invalid"
    assert "kaputt" not in st.message and "space" not in st.message


def test_decider_without_key_raises_boundary_error_not_silent():
    dec = ClaudeBoundaryDecider(
        model="claude-x", credential_provider=_provider(stored=None),
        client_factory=lambda api_key: None)
    try:
        dec._call("prompt")
        assert False, "ohne Key muss es laut scheitern"
    except BoundaryError as e:
        assert "key" in str(e).lower()


# === Carl-Verschärfung 2026-05-20: Validator + Hex-Detection ============

def test_validate_rejects_missing_sk_ant_prefix():
    # 108 Zeichen, aber falsches Prefix -> abgelehnt
    bad = "not-ant-" + "a" * 100
    try:
        validate_api_key(bad)
        assert False
    except ValueError as e:
        assert "sk-ant" in str(e).lower() or "form" in str(e).lower()
        # NIE den Key in der Meldung
        assert "aaa" not in str(e).lower()


def test_validate_rejects_too_short_even_with_sk_ant_prefix():
    too_short = "sk-ant-x"                     # 8 Zeichen, weit unter 80
    try:
        validate_api_key(too_short)
        assert False
    except ValueError as e:
        assert "länge" in str(e).lower() or "lange" in str(e).lower()


def test_validate_rejects_too_long():
    too_long = "sk-ant-" + "y" * 300           # weit über 220
    try:
        validate_api_key(too_long)
        assert False
    except ValueError as e:
        assert "länge" in str(e).lower() or "lange" in str(e).lower()
        assert "yyy" not in str(e).lower()


def test_validate_rejects_pure_hex_form_without_sk_ant_prefix():
    # Reine Hex-Repräsentation eines Strings, der NICHT mit sk-ant-
    # beginnt -> abgelehnt (kein versehentliches Anthropic-Aufrufen mit
    # Hex-Code, der eigentlich nur Bytes ist).
    hex_garbage = "73" * 60                    # 120 Hex-Zeichen, nur 's'
    try:
        validate_api_key(hex_garbage)
        assert False
    except ValueError as e:
        # Entweder wegen fehlendem Prefix oder als Hex erkannt
        assert "sk-ant" in str(e).lower() or "form" in str(e).lower() \
            or "hex" in str(e).lower()


# --- _read_keychain Hex-Detection ---

def test_read_keychain_decodes_hex_when_decoded_starts_with_sk_ant():
    # macOS gibt das Passwort als Hex zurück, wenn es non-printable
    # Bytes enthält (z. B. Trailing-Newline). Wenn das Decoded-Form
    # mit sk-ant- beginnt, soll der Reader das automatisch dekodieren.
    real_key = "sk-ant-api03-" + "h" * 95
    # Simuliere "Schlüsselbund enthält real_key + \n" -> security -w
    # liefert das als Hex (genau dasselbe Verhalten wie live gemessen).
    hex_with_newline = (real_key + "\n").encode('utf-8').hex()
    p = _provider(stored=hex_with_newline)
    assert p.get_api_key() == real_key


def test_read_keychain_keeps_hex_when_decoded_is_not_sk_ant():
    # Hex eines Strings, der nicht sk-ant- ist -> Hex bleibt drin,
    # Validator lehnt dann ab (fehlender Prefix).
    other = "not-anthropic-key-" + "x" * 90
    hex_form = other.encode('utf-8').hex()
    p = _provider(stored=hex_form)
    assert p.get_api_key() is None             # validate lehnt ab


def test_read_keychain_passes_plain_text_through():
    real_key = "sk-ant-api03-" + "p" * 95
    p = _provider(stored=real_key)
    assert p.get_api_key() == real_key
