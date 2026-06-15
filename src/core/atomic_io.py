"""Atomares Schreiben von JSON-Dateien (DATA-1, Carl-Plan 2026-06-15).

Neutrales Modul (keine Abhängigkeit zu project_archive/transcript_archive),
damit es von beiden ohne Import-Zyklus genutzt werden kann.

Strategie: in eine temporäre Datei im selben Ordner schreiben, optional
fsync, dann os.replace (atomarer Namenswechsel). Bricht das Schreiben ab
(Crash/Kill/volle Platte/Serialisierungsfehler), bleibt die bestehende
Zieldatei unangetastet — nie ein truncierter Halbstand.
"""

import json
import os


def write_json_atomic(path, payload, *, indent=None, ensure_ascii=False,
                      fsync=True):
    """Schreibt ``payload`` als JSON atomar nach ``path``.

    tmp im selben Ordner -> json.dump -> flush -> optional os.fsync ->
    os.replace -> best-effort Directory-fsync. Bei einer Exception während
    des Schreibens wird die tmp-Datei entfernt und die alte Zieldatei
    bleibt intakt; die Exception wird weitergereicht.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=indent, ensure_ascii=ensure_ascii)
            f.flush()
            if fsync:
                os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # tmp aufräumen, Zieldatei nie anfassen, Fehler weiterreichen.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

    if fsync:
        # Directory-fsync macht den Namenswechsel durabler (Crash/NAS).
        # Auf manchen Plattformen/FS nicht möglich -> best effort.
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
