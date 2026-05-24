"""Descript .docx import for Roadmap #3 smart clip boundaries.

The parser intentionally depends only on the Python standard library.
Descript exports observed for PeakCut have speaker labels (``Name:``) and
coarse minute timestamps (``[HH:MM:00]``), but no word-level timing.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from .transcription import Transcript, TranscriptError, TranscriptSegment

_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2})\]")
_INLINE_SPEAKER_RE = re.compile(r"^([^:\[\]]{1,80}):\s*(.*)$")
_DOC_XML = "word/document.xml"
_NAME_PARTICLES = {
    "da", "de", "del", "den", "der", "di", "du", "la", "le",
    "van", "von", "y", "zu", "zum", "zur",
}
_SENTENCE_START_WORDS = {
    "aber", "also", "das", "dann", "der", "die", "ein", "eine",
    "einen", "einem", "er", "es", "hat", "ich", "ist", "oder",
    "sie", "sind", "und", "warum", "was", "weil", "wenn", "wie",
    "wir",
}
_SENTENCE_PUNCTUATION_RE = re.compile(r"[.!?;,\"„“”()\[\]{}]")


@dataclass
class _Record:
    raw_start_ms: int
    speaker: str
    parts: list[str]


def parse_descript_docx(path: str) -> Transcript:
    """Read a Descript .docx export into PeakCut's frozen Transcript.

    Each timestamp starts one segment. Its end is the next timestamp; the
    final segment gets a conservative +60s end because Descript's export is
    minute-coarse. Repeated timestamps are kept as separate segments by
    assigning later equal-minute records a 1ms virtual offset. This preserves
    document order and satisfies TranscriptSegment's strict end > start
    invariant without pretending to know a better intra-minute boundary.
    """
    paragraphs = _read_docx_paragraphs(path)
    records = _records_from_paragraphs(paragraphs)
    if not records:
        raise TranscriptError("Descript-docx enthaelt keine Zeitstempel")
    return Transcript(segments=tuple(_segments_from_records(records)))


def _read_docx_paragraphs(path: str) -> list[str]:
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                xml_bytes = zf.read(_DOC_XML)
            except KeyError as exc:
                raise TranscriptError(
                    "Descript-docx enthaelt kein word/document.xml") from exc
    except FileNotFoundError as exc:
        raise TranscriptError(f"Descript-docx nicht gefunden: {path}") from exc
    except zipfile.BadZipFile as exc:
        raise TranscriptError(f"Descript-docx ist keine gueltige .docx: {path}") from exc
    except OSError as exc:
        raise TranscriptError(f"Descript-docx kann nicht gelesen werden: {path}") from exc

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise TranscriptError("Descript-docx XML ist unlesbar") from exc

    paragraphs: list[str] = []
    for p in _iter_local(root, "p"):
        pieces: list[str] = []
        for node in p.iter():
            name = _local_name(node.tag)
            if name == "t" and node.text:
                pieces.append(node.text)
            elif name == "tab":
                pieces.append(" ")
            elif name == "br":
                pieces.append(" ")
        text = _compact("".join(pieces))
        if text:
            paragraphs.append(text)
    return paragraphs


def _records_from_paragraphs(paragraphs: list[str]) -> list[_Record]:
    records: list[_Record] = []
    current: _Record | None = None
    current_speaker = ""
    last_raw: int | None = None

    def finish_current() -> None:
        nonlocal current
        if current is not None:
            records.append(current)
            current = None

    for paragraph in paragraphs:
        matches = list(_TIMESTAMP_RE.finditer(paragraph))
        if not matches:
            speaker = _speaker_label(paragraph)
            if speaker is not None:
                current_speaker = speaker
            elif current is not None:
                current.parts.append(paragraph)
            continue

        prefix = paragraph[:matches[0].start()].strip()
        prefix_speaker = _speaker_label(prefix) if prefix else None
        if prefix_speaker is not None:
            current_speaker = prefix_speaker
        elif prefix and current is not None:
            current.parts.append(prefix)

        for i, match in enumerate(matches):
            start_ms = _timestamp_to_ms(match)
            if last_raw is not None and start_ms < last_raw:
                raise TranscriptError("Descript-Zeitstempel sind nicht sortiert")
            last_raw = start_ms

            finish_current()
            next_start = matches[i + 1].start() if i + 1 < len(matches) else len(paragraph)
            body = paragraph[match.end():next_start].strip()
            speaker, body = _split_inline_speaker(body, current_speaker)
            current_speaker = speaker
            current = _Record(raw_start_ms=start_ms, speaker=speaker, parts=[])
            if body:
                current.parts.append(body)
    finish_current()

    if not records:
        return []
    if not any(_record_text(r) for r in records):
        raise TranscriptError("Descript-docx enthaelt keine Transkripttexte")
    return records


def _segments_from_records(records: list[_Record]) -> list[TranscriptSegment]:
    starts: list[int] = []
    previous = -1
    for r in records:
        start = max(r.raw_start_ms, previous + 1)
        starts.append(start)
        previous = start

    segments: list[TranscriptSegment] = []
    for i, record in enumerate(records):
        start_ms = starts[i]
        end_ms = starts[i + 1] if i + 1 < len(starts) else start_ms + 60_000
        if end_ms <= start_ms:
            end_ms = start_ms + 1
        text = _record_text(record)
        if not text:
            raise TranscriptError(
                f"Descript-Segment bei {record.raw_start_ms}ms ist leer")
        segments.append(TranscriptSegment(start_ms, end_ms, text, words=()))
    return segments


def _record_text(record: _Record) -> str:
    body = _compact(" ".join(p.strip() for p in record.parts if p.strip()))
    if record.speaker and body:
        return f"{record.speaker}: {body}"
    return body


def _split_inline_speaker(text: str, fallback: str) -> tuple[str, str]:
    match = _INLINE_SPEAKER_RE.match(text.strip())
    if not match:
        return fallback, text.strip()
    speaker = _speaker_label(match.group(1).strip() + ":")
    if speaker is None:
        return fallback, text.strip()
    body = match.group(2).strip()
    return speaker, body


def _speaker_label(text: str) -> str | None:
    text = text.strip()
    if not text.endswith(":"):
        return None
    speaker = text[:-1].strip()
    if not speaker or len(speaker) > 80:
        return None
    if _TIMESTAMP_RE.search(speaker):
        return None
    if not _looks_like_speaker_name(speaker):
        return None
    return speaker


def _looks_like_speaker_name(label: str) -> bool:
    """Conservative Descript-speaker heuristic.

    Speaker labels are expected to be simple names ("Matze",
    "Sheila de Liz"). A prose sentence ending in a colon should stay
    transcript text, not become the next speaker.
    """
    if _SENTENCE_PUNCTUATION_RE.search(label):
        return False
    words = label.split()
    if not (1 <= len(words) <= 5):
        return False
    saw_name_word = False
    for word in words:
        lower = word.lower()
        if lower in _SENTENCE_START_WORDS:
            return False
        if lower in _NAME_PARTICLES:
            continue
        parts = re.split(r"[-'’]", word)
        if not parts or any(not p for p in parts):
            return False
        for part in parts:
            if not part.isalpha():
                return False
            if not (part[0].isupper() or part.isupper()):
                return False
        saw_name_word = True
    return saw_name_word


def _timestamp_to_ms(match: re.Match[str]) -> int:
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    if minutes >= 60 or seconds >= 60:
        raise TranscriptError(f"Ungueltiger Zeitstempel: {match.group(0)}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000


def _iter_local(root: ElementTree.Element, local: str):
    for node in root.iter():
        if _local_name(node.tag) == local:
            yield node


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _compact(text: str) -> str:
    return " ".join(text.split())
