from core.folgenschnitt_models import (
    SHOT_CLOSE,
    SHOT_TOTAL,
    SHOT_UNUSED,
    SHOT_WIDE,
    CameraAssignment,
)
from gui.review_camera_labels import camera_display_label


def test_camera_display_label_uses_person_and_shot_label():
    assignments = [
        CameraAssignment("/material/CAM_A.mp4", SHOT_WIDE, "Matze"),
        CameraAssignment("/material/CAM_B.mp4", SHOT_CLOSE, "Hartmut"),
    ]

    assert camera_display_label("/material/CAM_A.mp4", assignments) == "Matze weit"
    assert camera_display_label("/material/CAM_B.mp4", assignments) == "Hartmut Close"


def test_camera_display_label_uses_personless_shot_label_or_filename_fallback():
    assignments = [
        CameraAssignment("/material/TOTAL.mp4", SHOT_TOTAL),
        CameraAssignment("/material/UNUSED.mp4", SHOT_UNUSED),
    ]

    assert camera_display_label("/material/TOTAL.mp4", assignments) == "Totale"
    assert camera_display_label("/material/UNUSED.mp4", assignments) == "UNUSED"
    assert camera_display_label("/material/CAM_RAW.mp4", assignments) == "CAM_RAW"
