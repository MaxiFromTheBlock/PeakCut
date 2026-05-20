#!/bin/bash
# Setup-Workflow für den Claude-Key im macOS-Schlüsselbund.
# Carl-Vorschlag 2026-05-20 nach Sheila-Smoke (Unicode-Spoofing +
# macOS-Hex-Output-Quirk live durchgekommen).
#
# Ablauf:
#   1. alten Eintrag löschen (clean state)
#   2. Key verdeckt einlesen (read -s, nie in Shell-History/argv)
#   3. lokal validieren (PeakCut-Validator: sk-ant-, ASCII, Länge 80-220)
#   4. in Schlüsselbund speichern
#   5. wieder lesen + nochmal validieren (gegen Hex-Quirk)
#   6. echter Mini-Test-Call gegen Anthropic-API
#
# Der Key wird NIE geprintet, NIE geloggt, NIE in argv übergeben.

set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO_ROOT/venv311/bin/python"
SERVICE="PeakCut Anthropic"
ACCOUNT="default"

echo "=== Claude-Key Setup für PeakCut ==="
echo
echo "Quelle: https://console.anthropic.com → Settings → API Keys"
echo "Key direkt aus der Konsole hier eingeben — Eingabe wird NICHT angezeigt."
echo "(Bei Problemen mit Copy-Paste: lieber per Hand tippen)."
echo
read -rs -p "Key: " KEY
echo
if [ -z "${KEY:-}" ]; then
  echo "Kein Key — abbruch."
  exit 1
fi

# --- 1) alten Eintrag löschen (clean state) ---
echo
echo "1) Alten Eintrag löschen …"
security delete-generic-password -s "$SERVICE" -a "$ACCOUNT" 2>/dev/null \
  && echo "   ✓ alter Eintrag gelöscht" \
  || echo "   (kein alter Eintrag — neu anlegen)"

# --- 2-5) Validieren + Speichern + Re-Lesen + Re-Validieren ---
echo
echo "2-5) Validieren → Speichern → Re-Lesen → Re-Validieren …"

# Pipe-Übergabe an Python — Key landet NICHT in argv (ps-safe).
echo "$KEY" | "$PY" - << 'PY'
import sys, subprocess
sys.path.insert(0, "/Users/max/Desktop/MF/Vibecoding/PeakCut/App/src")
from core.credentials import (
    validate_api_key, default_credential_provider,
    KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)

key_input = sys.stdin.read().rstrip('\n')

# Form-Diagnose VOR Validierung (ohne Key-Wert zu printen)
print(f"   Eingabe-Form: Länge={len(key_input)}, "
      f"ASCII-only={key_input.isascii()}, "
      f"Prefix={key_input[:7]!r}, Suffix=…{key_input[-4:]!r}")
non_ascii = [(i, c, ord(c)) for i, c in enumerate(key_input) if ord(c) > 127]
if non_ascii:
    print(f"   ⚠️  {len(non_ascii)} Non-ASCII-Zeichen (Unicode-Spoofing?):")
    for i, c, o in non_ascii[:5]:
        print(f"      Pos {i}: {c!r} (U+{o:04X})")

# 2) Validieren
try:
    cleaned = validate_api_key(key_input)
    print(f"   ✓ lokale Validierung OK (Länge {len(cleaned)})")
except ValueError as e:
    print(f"   ✗ lokale Validierung FAILED: {e}")
    print()
    print("   → Key wurde NICHT gespeichert. Bitte Key-Quelle prüfen")
    print("     (Browser-Render hat eventuell Doppelgänger-Zeichen")
    print("     eingeschleust). Lieber per Hand tippen, nicht copy-paste.")
    sys.exit(1)

# 3) Speichern
provider = default_credential_provider()
try:
    provider.store(cleaned)
    print(f"   ✓ in Schlüsselbund gespeichert")
except Exception as e:
    print(f"   ✗ store fehlgeschlagen: {type(e).__name__}: {e}")
    sys.exit(1)

# 4) Wieder lesen
roundtrip = provider.get_api_key()
if not roundtrip:
    print(f"   ✗ Re-Read aus Schlüsselbund liefert nichts.")
    sys.exit(1)

if roundtrip != cleaned:
    print(f"   ⚠️  Re-Read-Wert weicht ab "
          f"(re-read Länge {len(roundtrip)}, Original {len(cleaned)})")
    sys.exit(1)
print(f"   ✓ Re-Read OK (identisch zu Eingabe nach strip)")

# 5) Status semantisch plausibel?
st = provider.status()
print(f"   Provider-Status: ok={st.ok}, reason={st.reason}")
if not st.ok:
    print(f"   ✗ Provider hält den Wert für nicht plausibel: {st.message}")
    sys.exit(1)

# --- 6) echter Test-Call gegen Anthropic ---
print()
print("6) Mini-Test-Call gegen Anthropic …")
try:
    import anthropic
    client = anthropic.Anthropic(api_key=cleaned)
    r = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10, temperature=0,
        messages=[{"role": "user", "content": "say only the word ok"}])
    text = r.content[0].text if r.content else "(leer)"
    print(f"   ✓ ERFOLGREICH — Anthropic-Antwort: {text!r}")
    print()
    print("=" * 50)
    print("FERTIG. Key liegt sauber im Schlüsselbund + funktioniert live.")
    print("PeakCut kann jetzt mit Smart-Boundary gestartet werden.")
except anthropic.AuthenticationError as e:
    print(f"   ✗ AuthenticationError: {e}")
    print()
    print("   Lokal valid, aber Anthropic lehnt ab — möglich:")
    print("   - Key bei Anthropic widerrufen/abgelaufen.")
    print("   - Tippfehler trotz Validierung (extrem subtil).")
    sys.exit(1)
except Exception as e:
    print(f"   ? Anderer Fehler: {type(e).__name__}: {e}")
    sys.exit(1)
PY

EXIT=$?
unset KEY
exit $EXIT
