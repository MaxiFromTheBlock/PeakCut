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


def test_shot_combo_uses_non_native_view_for_readable_popup():
    # Bug: das native macOS-Popup ignoriert das QAbstractItemView-Stylesheet
    # (markierte Zeile weiß-auf-hellgrau, unlesbar). setView(QListView())
    # erzwingt Qts eigene Liste -> SHOT_COMBO_STYLESHEET greift, Zeile lesbar.
    from PyQt6.QtWidgets import QListView
    from gui.assignment_page import make_shot_combo, SHOT_CHOICES

    combo = make_shot_combo()
    assert isinstance(combo.view(), QListView)
    assert combo.count() == len(SHOT_CHOICES)


# ---------------------------------------------------------------------
# Slice B Task 7 — unused_clips_mode Toggle in AssignmentPage
# ---------------------------------------------------------------------


def test_assignment_state_default_unused_clips_mode_is_disable():
    """Pure State: frische AssignmentState ohne Session traegt
    DEFAULT_UNUSED_CLIPS_MODE."""
    from core.folgenschnitt_multitrack_layout import (
        DEFAULT_UNUSED_CLIPS_MODE,
    )
    from gui.assignment_page import AssignmentState

    state = AssignmentState(camera_rows=[], mic_rows=[])
    assert state.unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


def test_build_assignment_state_reads_mode_from_session():
    """build_assignment_state liest session.folgenschnitt_unused_clips_mode."""
    from core.folgenschnitt_multitrack_layout import UNUSED_CLIPS_REMOVE

    session = _session(mic_assignments=_hm_mics())
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_REMOVE
    video_files = ["/material/Cam.mp4"]

    state = build_assignment_state(session, video_files)
    assert state.unused_clips_mode == UNUSED_CLIPS_REMOVE


def test_build_assignment_state_default_when_session_attr_missing():
    """Wenn Session das Attribut nicht hat (z.B. alte Test-Stubs),
    faellt build_assignment_state auf den Default zurueck."""
    from core.folgenschnitt_multitrack_layout import (
        DEFAULT_UNUSED_CLIPS_MODE,
    )

    session = _session(mic_assignments=_hm_mics())
    # Attribut bewusst NICHT setzen — der SimpleNamespace hat es nicht.
    video_files = ["/material/Cam.mp4"]

    state = build_assignment_state(session, video_files)
    assert state.unused_clips_mode == DEFAULT_UNUSED_CLIPS_MODE


def test_assignment_state_completeness_independent_of_mode():
    """is_complete-Logik darf NICHT vom Toggle abhaengen — Folgenschnitt-
    Qualitaet bleibt unberuehrt vom Layout-Mode."""
    from gui.assignment_page import (
        AssignmentState, CameraRow, MicRow,
    )

    rows_complete = [
        CameraRow("/A.mp4", "A.mp4", "weit", "Jan"),
        CameraRow("/B.mp4", "B.mp4", "weit", "Tim"),
    ]
    mics_complete = [
        MicRow(0, "/MIC1.wav", "MIC1.wav", "Jan", "mic_1"),
        MicRow(1, "/MIC2.wav", "MIC2.wav", "Tim", "mic_2"),
    ]

    state_disable = AssignmentState(
        camera_rows=rows_complete,
        mic_rows=mics_complete,
        unused_clips_mode="disable",
    )
    state_remove = AssignmentState(
        camera_rows=rows_complete,
        mic_rows=mics_complete,
        unused_clips_mode="remove",
    )
    assert state_disable.is_complete() == state_remove.is_complete()


def test_assignment_page_apply_writes_mode_to_session():
    """apply_to_session schreibt _state.unused_clips_mode in
    session.folgenschnitt_unused_clips_mode."""
    from core.folgenschnitt_multitrack_layout import UNUSED_CLIPS_REMOVE

    _app()
    session = _session(mic_assignments=_hm_mics())
    session.folgenschnitt_unused_clips_mode = "disable"

    page = AssignmentPage()
    page.set_session(session, ["/material/Cam.mp4"])

    # User toggelt auf Remove
    page._state.unused_clips_mode = UNUSED_CLIPS_REMOVE
    page.apply_to_session()

    assert session.folgenschnitt_unused_clips_mode == UNUSED_CLIPS_REMOVE


def test_assignment_page_has_unused_clips_mode_toggle():
    """AssignmentPage stellt einen Toggle (Radio-Buttons) fuer Remove/
    Disable zur Verfuegung. Default-Selection = Disable."""
    from core.folgenschnitt_multitrack_layout import (
        UNUSED_CLIPS_DISABLE,
        UNUSED_CLIPS_REMOVE,
    )

    _app()
    session = _session(mic_assignments=_hm_mics())
    session.folgenschnitt_unused_clips_mode = UNUSED_CLIPS_DISABLE

    page = AssignmentPage()
    page.set_session(session, ["/material/Cam.mp4"])

    # Page exposes Radio-Buttons fuer beide Modi.
    assert hasattr(page, "_unused_clips_disable_radio")
    assert hasattr(page, "_unused_clips_remove_radio")
    # Default-Selection entspricht Session-Wert.
    assert page._unused_clips_disable_radio.isChecked()
    assert not page._unused_clips_remove_radio.isChecked()

    # Toggle auf Remove: Klick auf Remove-Radio wechselt _state-Mode.
    page._unused_clips_remove_radio.setChecked(True)
    assert page._state.unused_clips_mode == UNUSED_CLIPS_REMOVE


def test_assignment_page_toggle_default_disable_when_session_has_no_attr():
    """Wenn die Session das Attribut nicht traegt (Edge-Case), zeigt
    der Toggle Default = Disable."""
    from core.folgenschnitt_multitrack_layout import UNUSED_CLIPS_DISABLE

    _app()
    session = _session(mic_assignments=_hm_mics())
    # Attribut bewusst nicht setzen.

    page = AssignmentPage()
    page.set_session(session, ["/material/Cam.mp4"])

    assert page._state.unused_clips_mode == UNUSED_CLIPS_DISABLE
    assert page._unused_clips_disable_radio.isChecked()
