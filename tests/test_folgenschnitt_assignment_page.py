import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QComboBox

from core.folgenschnitt_models import (
    ActivityFrame,
    SHOT_TOTAL,
    SHOT_UNUSED,
    MicAssignment,
)
from gui.assignment_page import (
    SHOT_COMBO_STYLESHEET,
    AssignmentPage,
    build_assignment_state,
    preview_start_s_for_mic,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _session(mic_assignments=None, guest_name="Hartmut Rosa", mic_tracks=None,
             speaker_activity=None):
    project = SimpleNamespace(
        guest_name=guest_name,
        mic_tracks=mic_tracks or ["/material/MIC1.wav", "/material/MIC2.wav"],
    )
    return SimpleNamespace(
        project=project,
        speaker_activity_mic_assignments=mic_assignments or [],
        speaker_activity=speaker_activity or [],
    )


def _hm_mics():
    return [
        MicAssignment(0, "/material/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/material/MIC2.wav", "Hartmut Rosa", "mic_2"),
    ]


def test_default_assignment_state_starts_all_person_fields_empty():
    session = _session(mic_assignments=_hm_mics())
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
    assert all(r.shot_type is None for r in state.camera_rows)
    assert all(r.person is None for r in state.camera_rows)
    assert state.to_camera_assignments() == []
    # speaker_key stays (technical, from analysis); person is deliberately empty
    assert [r.speaker_key for r in state.mic_rows] == ["mic_1", "mic_2"]
    assert [r.person for r in state.mic_rows] == ["", ""]
    assert state.people == []


def test_build_assignment_state_filters_mix_out_of_mic_rows():
    session = _session(mic_assignments=[
        MicAssignment(0, "/material/MIC1.wav", "Matze", "mic_1"),
        MicAssignment(1, "/material/Sheila Mix.mp3", "Gast", "mic_mix"),
        MicAssignment(2, "/material/MIC2.wav", "Sheila", "mic_2"),
    ])

    state = build_assignment_state(session, [])

    assert [r.path for r in state.mic_rows] == [
        "/material/MIC1.wav",
        "/material/MIC2.wav",
    ]
    assert [r.speaker_key for r in state.mic_rows] == ["mic_1", "mic_2"]


def test_neutral_camera_rows_create_no_camera_assignments():
    session = _session(mic_assignments=_hm_mics())
    state = build_assignment_state(session, ["/material/CAM_A.mp4"])

    assert state.to_camera_assignments() == []
    assert state.is_complete() is False


def test_assignment_state_disables_person_for_total_and_unused():
    session = _session(mic_assignments=_hm_mics())
    state = build_assignment_state(session, ["/material/CAM_A.mp4"])

    state.camera_rows[0].shot_type = SHOT_TOTAL
    state.camera_rows[0].person = "Matze"
    assert state.to_camera_assignments()[0].person is None

    state.camera_rows[0].shot_type = SHOT_UNUSED
    state.camera_rows[0].person = "Matze"
    assert state.to_camera_assignments()[0].person is None


def test_assignment_state_reports_incomplete_but_does_not_block_keyboard_export():
    session = _session(guest_name="")
    state = build_assignment_state(session, ["/material/CAM_A.mp4"])

    assert state.is_complete() is False
    assert isinstance(state.to_camera_assignments(), list)
    assert isinstance(state.to_mic_assignments(), list)


def test_preview_start_uses_longest_active_run_for_mic():
    session = _session(speaker_activity=[
        ActivityFrame(10_000, 10_200, {}, {}, 0.0, None, None, 0.0),
        ActivityFrame(12_000, 12_200, {}, {}, 8.0, "mic_1", "mic_1", 0.9),
        ActivityFrame(20_000, 20_200, {}, {}, 8.0, "mic_1", "mic_1", 0.9),
        ActivityFrame(20_100, 20_300, {}, {}, 8.0, "mic_1", "mic_1", 0.9),
        ActivityFrame(20_200, 20_400, {}, {}, 8.0, "mic_1", "mic_1", 0.9),
    ])

    assert preview_start_s_for_mic(session, "mic_1") == 19.5


def test_preview_start_falls_back_to_zero_without_activity():
    session = _session(speaker_activity=[])

    assert preview_start_s_for_mic(session, "mic_1") == 0.0


def test_committed_person_name_becomes_option_without_prefilling_other_empty_fields():
    _app()
    page = AssignmentPage()

    source = QComboBox()
    source.setEditable(True)
    target = QComboBox()
    target.setEditable(True)
    untouched = QComboBox()
    untouched.setEditable(True)

    page._register_person_combo(source)
    page._register_person_combo(target)
    page._register_person_combo(untouched)

    source.setCurrentText("Matze")
    page._commit_person_name(source)

    assert source.currentText() == "Matze"
    assert target.findText("Matze") >= 0
    assert untouched.findText("Matze") >= 0
    assert target.currentText() == ""
    assert untouched.currentText() == ""


def test_shot_combo_stylesheet_sets_readable_text_color():
    assert "color:" in SHOT_COMBO_STYLESHEET
    assert "#1D1D1F" in SHOT_COMBO_STYLESHEET
