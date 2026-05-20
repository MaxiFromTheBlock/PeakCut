#!/bin/bash
# Test-Werkzeug: prüft einen Claude-Key direkt gegen die Anthropic-API,
# OHNE den macOS-Schlüsselbund anzufassen. Der Key kommt per
# Terminal-Prompt (read -s), wird NIE geprintet, NIE gespeichert, landet
# NICHT in der Shell-History (Pipe-Übergabe statt argv).

set -u
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO_ROOT/venv311/bin/python"

echo "Claude-Key-Test (Schlüsselbund nicht beteiligt)."
echo "Key aus Anthropic-Konsole hier eingeben — Eingabe wird NICHT angezeigt:"
read -rs -p "Key: " KEY
echo
if [ -z "${KEY:-}" ]; then
  echo "Kein Key — abbruch."
  exit 1
fi

# Pipe-Übergabe an Python — Key landet NICHT in argv (kein ps-Leak).
echo "$KEY" | "$PY" - << 'PY'
import sys
key = sys.stdin.read().rstrip('\n')

print()
print('Form-Check (Key-Wert wird NIE geprintet):')
print(f'  Länge:        {len(key)} Zeichen')
print(f'  ASCII-only:   {key.isascii()}')
print(f'  Prefix:       {key[:7]!r}')
print(f'  Suffix:       ...{key[-4:]!r}')

non_ascii = [(i, c, ord(c)) for i, c in enumerate(key) if ord(c) > 127]
if non_ascii:
    print(f'  ⚠️  {len(non_ascii)} Non-ASCII-Zeichen drin (Unicode-Spoofing?):')
    for i, c, o in non_ascii[:10]:
        print(f'      Pos {i}: {c!r} (U+{o:04X})')

ws = [i for i, c in enumerate(key) if c.isspace()]
if ws:
    print(f'  ⚠️  {len(ws)} Whitespace-Zeichen intern an Positionen: {ws[:10]}')

ctrl = [i for i, c in enumerate(key) if ord(c) < 0x20]
if ctrl:
    print(f'  ⚠️  {len(ctrl)} Steuerzeichen intern an Positionen: {ctrl[:10]}')

print()
print('Test-Call gegen Anthropic-API …')
try:
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    r = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=10, temperature=0,
        messages=[{'role': 'user', 'content': 'say only the word ok'}])
    text = r.content[0].text if r.content else '(leer)'
    print(f'  ✓ ERFOLGREICH — Anthropic-Antwort: {text!r}')
    print()
    print('Verdikt: der Key selbst funktioniert.')
    print('Wenn PeakCut trotzdem AuthenticationError zeigt, sitzt das')
    print('Problem im Schlüsselbund-Speicher-Pfad — nicht im Key.')
except anthropic.AuthenticationError as e:
    print(f'  ✗ AuthenticationError: {e}')
    print()
    print('Verdikt: Anthropic lehnt diesen Key ab. Mögliche Ursachen:')
    print('  - Key bei Anthropic widerrufen oder abgelaufen.')
    print('  - Tippfehler / Unicode-Spoofing aus der Copy-Source-Kette')
    print('    (Browser-Render hat lat. Buchstaben durch kyrillische o. ä.')
    print('    Doppelgänger ersetzt). Form-Check oben prüfen.')
except Exception as e:
    print(f'  ? Anderer Fehler: {type(e).__name__}: {e}')
    print('  (Netzwerk-Problem? Anthropic-API-Outage? siehe Klasse oben.)')
PY

unset KEY
