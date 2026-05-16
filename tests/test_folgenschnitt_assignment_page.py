from types import SimpleNamespace

from core.folgenschnitt_models import SHOT_TOTAL, SHOT_UNUSED, SHOT_WIDE, MicAssignment
from gui.assignment_page import build_assignment_state


def _session(mic_assignments=None, guest_name="Hartmut Rosa", mic_tracks=None):
    project = SimpleNamespace(
        guest_name=guest_name,
        mic_tracks=mic_tracks or ["/material/MIC1.wav", "/material/MIC2.wav"],
    )
    return SimpleNamespace(
        project=project,
        speaker_activity_mic_assignments=mic_assignments or [],
    )


def test_default_assignment_state_uses_full_video_filenames_and_default_people():
    session = _session(
        mic_assignments=[
            MicAssignment(0, "/material/MIC1.wav", "Matze", "mic_1"),
            MicAssignment(1, "/material/MIC2.wav", "Hartmut Rosa", "mic_2"),
        ]
    )
    video_files = [
        "/material/_HM_HartmutRosa_Cam04_MV_7922.MP4",
        "/material/_HM_HartmutRosa_Cam02_MV_7894.MP4",
        "/material/_HM_HartmutRosa_Cam03_Nachdreh.MP4",
    ]

    state = build_assignment_state(session, video_files)

    assert [r.filename for r in state.camera_rows] == [
        "_HM_HartmutRosa_Cam04_MV_7922.MP4",
        "_HM_HartmutRosa_Cam02_MV_7894.MP4",
        "_HM_HartmutRosa_Cam03_Nachdreh.MP4",
    ]
    assert state.people[:2] == ["Matze", "Hartmut Rosa"]
    assert state.camera_rows[0].shot_type == SHOT_WIDE
    assert state.camera_rows[0].person == "Matze"
    assert state.camera_rows[1].shot_type == SHOT_WIDE
    assert state.camera_rows[1].person == "Hartmut Rosa"
    assert state.camera_rows[2].shot_type == SHOT_UNUSED
    assert state.camera_rows[2].person is None
    assert [r.filename for r in state.mic_rows] == ["MIC1.wav", "MIC2.wav"]


def test_assignment_state_disables_person_for_total_and_unused():
    session = _session()
    state = build_assignment_state(session, ["/material/CAM_A.mp4"])

    state.camera_rows[0].shot_type = SHOT_TOTAL
    state.camera_rows[0].person = "Matze"
    cameras = state.to_camera_assignments()
    assert cameras[0].person is None

    state.camera_rows[0].shot_type = SHOT_UNUSED
    state.camera_rows[0].person = "Matze"
    cameras = state.to_camera_assignments()
    assert cameras[0].person is None


def test_assignment_state_reports_incomplete_but_does_not_block_keyboard_export():
    session = _session(guest_name="")
    # only one wide camera -> Folgenschnitt cannot run, but this must not raise
    state = build_assignment_state(session, ["/material/CAM_A.mp4"])

    assert state.is_complete() is False
    # producing assignments never raises -> Keyboardstellen path stays intact
    assert isinstance(state.to_camera_assignments(), list)
    assert isinstance(state.to_mic_assignments(), list)
