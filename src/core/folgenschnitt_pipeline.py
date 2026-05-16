"""Guarded Folgenschnitt export pipeline.

Builds speaker turns + edit decisions from the assignment step at export
time. The hard guardrail: an incomplete or invalid assignment must never
break the Keyboardstellen export. Any problem here results in a skip
reason, never an exception that propagates to the export worker.
"""

from .folgenschnitt_decisions import build_edit_decisions, build_speaker_turns
from .folgenschnitt_models import SHOT_WIDE
from .speaker_activity import build_default_mic_assignments

SKIP_REASON = "Zuordnung unvollstaendig"


def build_default_folgenschnitt_mic_assignments(project, analysis_assignments=None):
    if analysis_assignments:
        return list(analysis_assignments)
    mic_tracks = list(getattr(project, "mic_tracks", []) or [])
    return build_default_mic_assignments(mic_tracks)


def has_minimum_folgenschnitt_assignment(mic_assignments, camera_assignments):
    persons = {m.person for m in mic_assignments if m.person}
    if len(persons) < 2:
        return False, SKIP_REASON
    wide_persons = {
        c.person
        for c in camera_assignments
        if c.shot_type == SHOT_WIDE and c.person
    }
    if len(wide_persons) < 2:
        return False, SKIP_REASON
    return True, None


def _skip(session, reason):
    session.speaker_turns = []
    session.folgenschnitt_edit_decisions = []
    session.folgenschnitt_skip_reason = reason
    return reason


def prepare_folgenschnitt_for_export(session) -> str | None:
    activity = list(getattr(session, "speaker_activity", []) or [])

    mic_assignments = (
        list(getattr(session, "folgenschnitt_mic_assignments", []) or [])
        or list(getattr(session, "speaker_activity_mic_assignments", []) or [])
    )
    if not mic_assignments:
        mic_assignments = build_default_folgenschnitt_mic_assignments(
            getattr(session, "project", None),
            getattr(session, "speaker_activity_mic_assignments", None),
        )
    camera_assignments = list(
        getattr(session, "folgenschnitt_camera_assignments", []) or []
    )

    if not activity:
        return _skip(session, SKIP_REASON)

    ok, reason = has_minimum_folgenschnitt_assignment(
        mic_assignments, camera_assignments
    )
    if not ok:
        return _skip(session, reason)

    try:
        turns = build_speaker_turns(activity, mic_assignments)
        sequence_end_ms = max((f.end_ms for f in activity), default=0)
        decisions = build_edit_decisions(
            turns, camera_assignments, sequence_end_ms=sequence_end_ms
        )
    except ValueError:
        return _skip(session, SKIP_REASON)

    if not turns or not decisions:
        return _skip(session, SKIP_REASON)

    session.speaker_turns = turns
    session.folgenschnitt_edit_decisions = decisions
    session.folgenschnitt_skip_reason = None
    return None
