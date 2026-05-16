"""Guarded Folgenschnitt export pipeline.

Builds speaker turns + edit decisions from the assignment step at export
time. The hard guardrail: an incomplete or invalid assignment must never
break the Keyboardstellen export. Any problem here results in a skip
reason, never an exception that propagates to the export worker.
"""

from .folgenschnitt_decisions import build_edit_decisions, build_speaker_turns
from .folgenschnitt_loosening import (
    apply_time_logic_loosening,
    build_pause_ranges,
    build_stage1_base_camera_assignments,
)
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
    # Generalized: each speaking person must resolve to a base camera
    # (weit > close > halbnah > totale-fallback). Guardrail unchanged:
    # if not, Folgenschnitt is skipped cleanly.
    base = build_stage1_base_camera_assignments(mic_assignments, camera_assignments)
    if len({c.person for c in base if c.person}) < 2:
        return False, SKIP_REASON
    return True, None


def _skip(session, reason):
    session.speaker_turns = []
    session.folgenschnitt_edit_decisions = []
    session.folgenschnitt_skip_reason = reason
    return reason


def prepare_folgenschnitt_for_export(session) -> str | None:
    activity = list(getattr(session, "speaker_activity", []) or [])
    camera_assignments = list(
        getattr(session, "folgenschnitt_camera_assignments", []) or []
    )

    if getattr(session, "folgenschnitt_assignment_applied", False):
        # User went through the assignment step. An empty result is a
        # deliberate "incomplete" — never substitute analysis/default mics.
        mic_assignments = list(
            getattr(session, "folgenschnitt_mic_assignments", []) or []
        )
    else:
        # Legacy/headless path (assignment step never run): keep the old
        # fallback so non-Folgenschnitt usage is unaffected.
        mic_assignments = (
            list(getattr(session, "folgenschnitt_mic_assignments", []) or [])
            or list(getattr(session, "speaker_activity_mic_assignments", []) or [])
        )
        if not mic_assignments:
            mic_assignments = build_default_folgenschnitt_mic_assignments(
                getattr(session, "project", None),
                getattr(session, "speaker_activity_mic_assignments", None),
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
        # Generality adapter: feed Stage 1 a synthetic per-person base
        # (wide>close>halbnah>totale). Stage 1 stays UNCHANGED. The
        # loosening layer then works on the ORIGINAL assignments.
        base_camera_assignments = build_stage1_base_camera_assignments(
            mic_assignments, camera_assignments
        )
        stage1_decisions = build_edit_decisions(
            turns, base_camera_assignments, sequence_end_ms=sequence_end_ms
        )
        decisions = apply_time_logic_loosening(
            stage1_decisions,
            camera_assignments,
            pause_ranges=build_pause_ranges(activity),
        )
    except ValueError:
        return _skip(session, SKIP_REASON)

    if not turns or not decisions:
        return _skip(session, SKIP_REASON)

    session.speaker_turns = turns
    session.folgenschnitt_edit_decisions = decisions
    session.folgenschnitt_skip_reason = None
    return None
