"""#76 Task 1 — Playback-Mode-Contracts (Carl-Plan 2026-06-15).

Drei Wiedergabe-Modi als eingefrorener, Qt-freier Vertrag:
- key   = kurzer Drücker-Ton (Keyboard-Preview)
- speak = Sprecher-/Mix-Fenster um den Drücker
- smart = KI-Sinnabschnitt (ClipCandidate)

Reines Core-Modul ohne Qt. Die Migration von session.mode (heute noch
"keyboard"/"mic") auf dieses Vokabular passiert mit der Controller-
Integration (Tasks 5-7) — normalize_playback_mode überführt die Alt-Werte.
"""

PLAYBACK_MODE_KEY = "key"
PLAYBACK_MODE_SPEAK = "speak"
PLAYBACK_MODE_SMART = "smart"

PLAYBACK_MODE_ORDER = (PLAYBACK_MODE_KEY, PLAYBACK_MODE_SPEAK, PLAYBACK_MODE_SMART)

_LEGACY = {"keyboard": PLAYBACK_MODE_KEY, "mic": PLAYBACK_MODE_SPEAK}
_LABELS = {
    PLAYBACK_MODE_KEY: "Key",
    PLAYBACK_MODE_SPEAK: "Speak",
    PLAYBACK_MODE_SMART: "Smart",
}


def normalize_playback_mode(value):
    """Beliebigen Wert auf einen gültigen Modus abbilden.

    Ungültig/None -> "key". Case-insensitiv, getrimmt. Alte Werte
    ("keyboard"/"mic") werden überführt.
    """
    if not isinstance(value, str):
        return PLAYBACK_MODE_KEY
    v = value.strip().lower()
    if v in PLAYBACK_MODE_ORDER:
        return v
    if v in _LEGACY:
        return _LEGACY[v]
    return PLAYBACK_MODE_KEY


def next_playback_mode(value):
    """Nächster Modus im Zyklus key -> speak -> smart -> key."""
    cur = normalize_playback_mode(value)
    i = PLAYBACK_MODE_ORDER.index(cur)
    return PLAYBACK_MODE_ORDER[(i + 1) % len(PLAYBACK_MODE_ORDER)]


def label_for_mode(value):
    """Anzeige-Label ("Key"/"Speak"/"Smart")."""
    return _LABELS[normalize_playback_mode(value)]
