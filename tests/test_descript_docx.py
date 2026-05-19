"""Descript .docx transcript import (Roadmap #3 Revision Task 2A)."""

import os
import sys
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.descript_docx import parse_descript_docx  # noqa: E402
from core.transcription import Transcript, TranscriptError  # noqa: E402


def _write_docx(path, paragraphs):
    body = "".join(
        "<w:p><w:r><w:t>" + escape(text) + "</w:t></w:r></w:p>"
        for text in paragraphs
    )
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)


def test_parse_descript_docx_builds_transcript_segments(tmp_path):
    docx = tmp_path / "transcript.docx"
    _write_docx(docx, [
        "Sheila:",
        "[00:00:00] Ich starte hier.",
        "Matze:",
        "[00:01:00] Und ich antworte.",
        "[00:03:00] Das ist ein weiterer Gedanke.",
    ])

    transcript = parse_descript_docx(str(docx))

    assert isinstance(transcript, Transcript)
    assert [s.start_ms for s in transcript.segments] == [0, 60_000, 180_000]
    assert [s.end_ms for s in transcript.segments] == [60_000, 180_000, 240_000]
    assert [s.text for s in transcript.segments] == [
        "Sheila: Ich starte hier.",
        "Matze: Und ich antworte.",
        "Matze: Das ist ein weiterer Gedanke.",
    ]
    assert all(s.words == () for s in transcript.segments)


def test_parse_descript_docx_keeps_same_minute_segments_valid(tmp_path):
    docx = tmp_path / "same-minute.docx"
    _write_docx(docx, [
        "Sheila:",
        "[00:05:00] Erster Teil.",
        "[00:05:00] Zweiter Teil in derselben Minute.",
        "[00:06:00] Nächste Minute.",
    ])

    transcript = parse_descript_docx(str(docx))

    assert [(s.start_ms, s.end_ms) for s in transcript.segments] == [
        (300_000, 300_001),
        (300_001, 360_000),
        (360_000, 420_000),
    ]
    assert transcript.segments[0].text == "Sheila: Erster Teil."
    assert transcript.segments[1].text == "Sheila: Zweiter Teil in derselben Minute."


def test_parse_descript_docx_supports_inline_speaker_and_timestamp(tmp_path):
    docx = tmp_path / "inline.docx"
    _write_docx(docx, [
        "[01:02:00] Sheila: Mit Sprecher im selben Absatz.",
        "[01:03:00] Matze: Danach Matze.",
    ])

    transcript = parse_descript_docx(str(docx))

    assert transcript.segments[0].start_ms == 3_720_000
    assert transcript.segments[0].text == "Sheila: Mit Sprecher im selben Absatz."
    assert transcript.segments[1].text == "Matze: Danach Matze."


def test_parse_descript_docx_rejects_broken_or_unexpected_files(tmp_path):
    missing = tmp_path / "missing.docx"
    try:
        parse_descript_docx(str(missing))
        assert False, "missing file must raise TranscriptError"
    except TranscriptError:
        pass

    broken = tmp_path / "broken.docx"
    broken.write_text("not a zip")
    try:
        parse_descript_docx(str(broken))
        assert False, "broken docx must raise TranscriptError"
    except TranscriptError:
        pass

    no_timestamps = tmp_path / "no-timestamps.docx"
    _write_docx(no_timestamps, ["Sheila:", "Kein Zeitstempel."])
    try:
        parse_descript_docx(str(no_timestamps))
        assert False, "unexpected transcript must raise TranscriptError"
    except TranscriptError:
        pass
