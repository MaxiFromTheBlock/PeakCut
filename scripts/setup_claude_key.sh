#!/bin/bash
# Setup-Workflow für den Claude-Key im macOS-Schlüsselbund.
# Carl-Vorschlag 2026-05-20 + Hardening nach 1. Smoke-Versuch:
# Multi-Line-Paste-Bruch (read -s liest bis zum ersten Newline) ist
# unsicher. Default-Modus liest jetzt aus der Zwischenablage (pbpaste,
# schluckt Newlines/Whitespace), zeigt Form-Diagnose VOR dem Speichern,
# fragt um Bestätigung, säubert die Zwischenablage am Ende.
#
# Der Key wird NIE geprintet, NIE geloggt, NIE in argv übergeben.

set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO_ROOT/venv311/bin/python"
SERVICE="PeakCut Anthropic"
ACCOUNT="default"

echo "=== Claude-Key Setup für PeakCut ==="
echo
echo "Anleitung:"
echo "  1. https://console.anthropic.com → Settings → API Keys"
echo "  2. Neuen Key erstellen (oder vorhandenen kopieren)"
echo "  3. Mit Cmd+C in die Zwischenablage kopieren"
echo "  4. Hier Enter drücken, ich hole den Key per pbpaste."
echo
echo "Tipp: anderer Browser als beim letzten Mal probieren, falls der"
echo "letzte Versuch Unicode-Spoofing zeigte (Safari statt Chrome o. ä.)."
echo
read -r -p "Bereit? Enter drücken: " _

# pbpaste liest die System-Zwischenablage als Text. Newlines/Whitespace
# werden in der Python-Stufe weggestrippt.
RAW_KEY="$(pbpaste 2>/dev/null || true)"
if [ -z "$RAW_KEY" ]; then
  echo "✗ Zwischenablage ist leer. Kopier den Key (Cmd+C) und starte"
  echo "  das Skript nochmal."
  exit 1
fi

# --- Diagnose VOR jedem Schreibvorgang ---
echo
echo "Form-Diagnose (Key-Wert wird NIE geprintet):"
RAW_KEY="$RAW_KEY" "$PY" - << 'PY'
import os, sys
raw = os.environ.get('RAW_KEY', '')
# Reines Strip — Newlines/leading/trailing Whitespace weg.
key = raw.strip()
# Interne Newlines / Tabs ebenfalls entfernen (falls Paste mehrzeilig)
key = ''.join(c for c in key if c not in '\r\n')
print(f"  Rohlänge in Zwischenablage:  {len(raw)} Zeichen")
print(f"  Nach Whitespace-Säuberung:   {len(key)} Zeichen")
print(f"  ASCII-only:                  {key.isascii()}")
print(f"  Prefix:                      {key[:7]!r}")
print(f"  Suffix:                      ...{key[-4:]!r}")
non_ascii = [(i, c, ord(c)) for i, c in enumerate(key) if ord(c) > 127]
if non_ascii:
    print(f"  ⚠️  {len(non_ascii)} Non-ASCII-Zeichen (Unicode-Spoofing-Verdacht!):")
    for i, c, o in non_ascii[:8]:
        print(f"      Pos {i}: {c!r} (U+{o:04X})")
    print("  → Quelle nicht vertrauen. Anderer Browser, oder per Hand tippen.")
    sys.exit(2)
sys.exit(0)
PY
DIAG_EXIT=$?

if [ "$DIAG_EXIT" -eq 2 ]; then
  echo
  echo "Setup ABGEBROCHEN wegen Spoofing-Verdacht. Nichts gespeichert,"
  echo "Zwischenablage bleibt unangetastet (kannst nochmal sauberer kopieren)."
  exit 1
fi

echo
read -r -p "Diese Form übernehmen und speichern? [j/N] " ANSWER
case "$ANSWER" in
  j|J|y|Y|ja|Ja|JA|yes|Yes) ;;
  *)
    echo "Abgebrochen. Nichts gespeichert."
    exit 1
    ;;
esac

# --- Alten Eintrag weg, dann speichern + verifizieren ---
echo
echo "Alten Eintrag löschen …"
security delete-generic-password -s "$SERVICE" -a "$ACCOUNT" >/dev/null 2>&1 \
  && echo "  ✓ alter Eintrag gelöscht" \
  || echo "  (kein alter Eintrag — neu anlegen)"

echo
echo "Validieren → Speichern → Re-Lesen → Re-Validieren …"
RAW_KEY="$RAW_KEY" "$PY" - << 'PY'
import os, sys
sys.path.insert(0, "/Users/max/Desktop/MF/Vibecoding/PeakCut/App/src")
from core.credentials import validate_api_key, default_credential_provider

raw = os.environ.get('RAW_KEY', '')
key = raw.strip()
key = ''.join(c for c in key if c not in '\r\n')

try:
    cleaned = validate_api_key(key)
    print(f"  ✓ lokale Validierung OK (Länge {len(cleaned)})")
except ValueError as e:
    print(f"  ✗ Validierung FAILED: {e}")
    sys.exit(1)

p = default_credential_provider()
try:
    p.store(cleaned)
    print(f"  ✓ in Schlüsselbund gespeichert")
except Exception as e:
    print(f"  ✗ store fehlgeschlagen: {type(e).__name__}: {e}")
    sys.exit(1)

roundtrip = p.get_api_key()
if roundtrip != cleaned:
    print(f"  ✗ Re-Read weicht ab "
          f"(re-read {len(roundtrip) if roundtrip else 0}, "
          f"original {len(cleaned)})")
    sys.exit(1)
st = p.status()
print(f"  ✓ Re-Read OK, Provider-Status ok={st.ok} reason={st.reason}")

# Test-Call
print()
print("Mini-Test-Call gegen Anthropic …")
try:
    import anthropic
    client = anthropic.Anthropic(api_key=cleaned)
    r = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10, temperature=0,
        messages=[{"role": "user", "content": "say only the word ok"}])
    text = r.content[0].text if r.content else "(leer)"
    print(f"  ✓ ERFOLGREICH — Anthropic-Antwort: {text!r}")
except anthropic.AuthenticationError as e:
    print(f"  ✗ AuthenticationError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ? Anderer Fehler: {type(e).__name__}: {e}")
    sys.exit(1)
PY

SETUP_EXIT=$?
unset RAW_KEY

if [ "$SETUP_EXIT" -eq 0 ]; then
  # Zwischenablage säubern, damit der Key nicht stundenlang im
  # Clipboard rumliegt.
  echo "" | pbcopy
  echo
  echo "=================================================="
  echo "FERTIG. Key sauber im Schlüsselbund, live geprüft."
  echo "Zwischenablage geleert. PeakCut kann gestartet werden."
fi
exit $SETUP_EXIT
