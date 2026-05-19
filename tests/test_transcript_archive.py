"""Roadmap #3 Gate A — Transcript-Sidecar + Archive-Reference + Ownership.

Carl-Gate-A-Zusatz (Claude-verifiziert): transcript.json ist
Worker-Besitz, früh & eigenständig geschrieben; project.json["transcript"]
ist nur Referenz, erst beim Speichern. save_project_archive erzeugt/
überschreibt transcript.json NIE (Asymmetrie zu speaker_activity.csv).
STOPP-Gate.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.project_archive import (  # noqa: E402
    ARCHIVE_DIR, material_root, _media_paths,
    build_archive_payload, parse_archive_payload,
    save_project_archive, load_project_archive,
)
from core.transcription import Transcript, TranscriptSegment, TranscriptWord  # noqa: E402
from core.transcript_archive import (  # noqa: E402
    TRANSCRIPT_NAME, TRANSCRIPT_REF,
    transcript_sidecar_path, write_transcript_sidecar,
    read_transcript_sidecar, build_transcript_ref, audio_fingerprint,
)
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402

_CFG = {"fps": 25, "context_duration_ms": 15000}


def _media(tmp_path):
    d = tmp_path / "material"
    d.mkdir()
    kb = d / "KB.wav"
    m1 = d / "MIC1 mix.wav"
    cam = d / "CAM_A.mp4"
    for f in (kb, m1, cam):
        f.write_bytes(b"\x00")
    return str(kb), [str(m1)], [str(cam)]


def _session(tmp_path):
    kb, mics, vids = _media(tmp_path)
    p = PeakCutProject()
    p.set_files(kb, mics, vids)
    p.guest_name = "Hartmut Rosa"
    s = PeakCutSession(p, dict(_CFG))
    s.load_analysis_results({"peaks": [], "video_offsets": []})
    return s


def _transcript():
    return Transcript(segments=(
        TranscriptSegment(0, 1500, "Das System",
                          words=(TranscriptWord(0, 800, "Das"),
                                 TranscriptWord(800, 1500, "System"))),))


# 1) Root identisch zu save_project_archive ------------------------------

def test_sidecar_root_identical_to_save_archive(tmp_path):
    s = _session(tmp_path)
    expected_dir = os.path.join(
        material_root(_media_paths(s.project), s.project.keyboard_track),
        ARCHIVE_DIR)
    got = transcript_sidecar_path(s.project)
    assert os.path.dirname(got) == expected_dir
    assert os.path.basename(got) == TRANSCRIPT_NAME


# 2) Worker legt .peakcut/ selbst an --------------------------------------

def test_worker_creates_archive_dir_itself(tmp_path):
    s = _session(tmp_path)
    sidecar = transcript_sidecar_path(s.project)
    assert not os.path.exists(os.path.dirname(sidecar))  # noch kein .peakcut
    ref = write_transcript_sidecar(
        s.project, _transcript(), engine="mlx-whisper",
        model="large-v3-turbo", language="de",
        audio_path=s.project.mic_tracks[0])
    assert os.path.isfile(sidecar)
    assert ref["path"] == TRANSCRIPT_REF
    assert ref["engine"] == "mlx-whisper"
    assert ref["model"] == "large-v3-turbo"
    assert ref["language"] == "de"
    assert not ref["audio_path"].startswith("/")  # relativ


# 3) Besitz-Trennung: save referenziert, überschreibt NIE ----------------

def test_ownership_save_references_but_never_rewrites(tmp_path):
    s = _session(tmp_path)
    ref = write_transcript_sidecar(
        s.project, _transcript(), engine="mlx-whisper",
        model="large-v3-turbo", language="de",
        audio_path=s.project.mic_tracks[0])
    sidecar = transcript_sidecar_path(s.project)
    before = open(sidecar, "rb").read()

    s.transcript_ref = ref
    save_project_archive(s)

    after = open(sidecar, "rb").read()
    assert after == before, "save_project_archive darf transcript.json NIE anfassen"

    root = material_root(_media_paths(s.project), s.project.keyboard_track)
    payload = json.load(open(os.path.join(root, ARCHIVE_DIR, "project.json")))
    assert payload["transcript"]["path"] == TRANSCRIPT_REF
    assert payload["transcript"]["engine"] == "mlx-whisper"


# 4) Alte Akten tolerant (kein transcript) -------------------------------

def test_payload_transcript_is_additive_and_optional():
    # build ohne session.transcript_ref -> transcript None
    class _FakeProject:
        keyboard_track = "/m/KB.wav"
        mic_tracks = ["/m/MIC.wav"]
        videos = ["/m/CAM.mp4"]
        guest_name = "G"

    class _FakeSession:
        project = _FakeProject()
        config = {"fps": 25}
        peaks = []
        video_offsets = []
        speaker_activity = []
        speaker_activity_csv = None
        speaker_activity_mic_assignments = []
        folgenschnitt_mic_assignments = []
        folgenschnitt_camera_assignments = []
        folgenschnitt_assignment_applied = True

    payload = build_archive_payload(_FakeSession(), material_root="/m")
    assert payload["transcript"] is None
    # parse einer Akte OHNE transcript-Key -> None, kein Fehler, nicht
    # in den Pflicht-Sektionen
    payload.pop("transcript")
    parsed = parse_archive_payload(payload, {})
    assert parsed["transcript"] is None


def test_load_old_archive_without_transcript_is_clean(tmp_path):
    s = _session(tmp_path)
    save_project_archive(s)  # ohne transcript_ref
    loaded = load_project_archive(
        material_root(_media_paths(s.project), s.project.keyboard_track),
        dict(_CFG))
    assert loaded.transcript is None
    assert loaded.transcript_error is None


# 5) Kaputtes/fehlendes Transkript -> Load crasht nicht ------------------

def test_corrupt_transcript_does_not_crash_load(tmp_path):
    s = _session(tmp_path)
    ref = write_transcript_sidecar(
        s.project, _transcript(), engine="mlx-whisper",
        model="m", language="de", audio_path=s.project.mic_tracks[0])
    s.transcript_ref = ref
    save_project_archive(s)
    # Sidecar absichtlich zerstören
    with open(transcript_sidecar_path(s.project), "w") as f:
        f.write("{ kaputt nicht json")
    loaded = load_project_archive(
        material_root(_media_paths(s.project), s.project.keyboard_track),
        dict(_CFG))
    assert loaded.transcript is None
    assert loaded.transcript_error  # gesetzt -> Smart später unavailable


def test_read_sidecar_tolerant_returns_none(tmp_path):
    assert read_transcript_sidecar(str(tmp_path), None) is None
    assert read_transcript_sidecar(str(tmp_path), {"path": "x/none.json"}) is None


# Task 3 — session.transcript* formalisiert (kein Ad-hoc-Attribut mehr)

def test_fresh_session_has_transcript_state_defaults(tmp_path):
    s = _session(tmp_path)
    assert s.transcript is None
    assert s.transcript_ref is None
    assert s.transcript_error is None


def test_transcript_ref_roundtrips_through_archive_at_session_level(tmp_path):
    s = _session(tmp_path)
    ref = write_transcript_sidecar(
        s.project, Transcript(segments=(TranscriptSegment(0, 900, "x"),)),
        engine="mlx-whisper", model="m", language="de",
        audio_path=s.project.mic_tracks[0])
    s.transcript_ref = ref
    save_project_archive(s)
    loaded = load_project_archive(
        material_root(_media_paths(s.project), s.project.keyboard_track),
        dict(_CFG))
    assert loaded.transcript_ref == ref
    assert loaded.transcript is not None      # Sidecar wieder gelesen
    assert loaded.transcript_error is None


# ══════════════════════════════════════════════════════════════════════
# #3-Revision Gate A — transcript_ref additiv erweitert (Spec §11 R2/R6,
# Carl Task 1). source + audio_fingerprint immer; source_path /
# transcript_span_ms / audio_duration_ms optional. Alte Akten ohne
# diese Felder laden weiter sauber.
# ══════════════════════════════════════════════════════════════════════


def test_audio_fingerprint_size_and_mtime(tmp_path):
    f = tmp_path / "mix.wav"
    f.write_bytes(b"\x00" * 17)
    fp = audio_fingerprint(str(f))
    assert fp["size"] == 17
    assert isinstance(fp["mtime_ns"], int) and fp["mtime_ns"] > 0
    # kein teurer Hash im UI-Pfad -> nur size + mtime_ns
    assert set(fp) == {"size", "mtime_ns"}
    # fehlende Datei -> None (tolerant, kein Wurf)
    assert audio_fingerprint(str(tmp_path / "weg.wav")) is None


def test_build_transcript_ref_has_source_and_fingerprint(tmp_path):
    s = _session(tmp_path)
    ref = build_transcript_ref(
        s.project, engine="mlx-whisper", model="m", language="de",
        audio_path=s.project.mic_tracks[0])
    assert ref["source"] == "whisper"            # Default-Quelle
    assert ref["audio_fingerprint"]["size"] == 1  # b"\x00" Mediafile
    assert "mtime_ns" in ref["audio_fingerprint"]
    # Optionale Felder NICHT vorhanden solange nicht übergeben
    for opt in ("source_path", "transcript_span_ms", "audio_duration_ms"):
        assert opt not in ref


def test_build_transcript_ref_optional_fields_only_when_given(tmp_path):
    s = _session(tmp_path)
    ref = build_transcript_ref(
        s.project, engine="descript", model="-", language="de",
        audio_path=s.project.mic_tracks[0],
        source="descript", source_path="/x/Transkript.docx",
        transcript_span_ms=4_200_000, audio_duration_ms=4_260_000)
    assert ref["source"] == "descript"
    assert ref["source_path"] == "/x/Transkript.docx"
    assert ref["transcript_span_ms"] == 4_200_000
    assert ref["audio_duration_ms"] == 4_260_000


def test_old_ref_without_new_fields_still_reads_sidecar(tmp_path):
    # Akte aus der Zeit VOR der Revision: ref hat nur path/engine/...
    s = _session(tmp_path)
    write_transcript_sidecar(
        s.project, _transcript(), engine="mlx-whisper", model="m",
        language="de", audio_path=s.project.mic_tracks[0])
    root = material_root(_media_paths(s.project), s.project.keyboard_track)
    old_ref = {"path": TRANSCRIPT_REF, "engine": "mlx-whisper",
               "model": "m", "language": "de", "audio_path": "material/MIC1 mix.wav"}
    # kein source / kein audio_fingerprint -> trotzdem lesbar, kein Wurf
    t = read_transcript_sidecar(root, old_ref)
    assert t is not None
    assert t.segments[0].text == "Das System"
