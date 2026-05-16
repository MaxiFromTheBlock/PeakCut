# review_camera_labels.py - human label for a camera, derived from the
# assignment step. Pure function (unit-tested without Qt).

import os

from core.folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_TOTAL,
    SHOT_UNUSED,
    SHOT_WIDE,
)

SHOT_LABELS = {
    SHOT_WIDE: "weit",
    SHOT_CLOSE: "Close",
    SHOT_MEDIUM: "halbnah",
    SHOT_TOTAL: "Totale",
    SHOT_UNUSED: "",
}


def camera_display_label(video_path: str, camera_assignments) -> str:
    basename = os.path.splitext(os.path.basename(video_path))[0]
    assignment = next(
        (item for item in camera_assignments if item.path == video_path),
        None,
    )
    if assignment is None:
        return basename

    shot_label = SHOT_LABELS.get(assignment.shot_type, assignment.shot_type or "")
    shot_label = shot_label.strip()
    if assignment.person and shot_label:
        return f"{assignment.person} {shot_label}"
    if assignment.person:
        return assignment.person
    if shot_label:
        return shot_label
    return basename
