"""Roadmap #3 Gate A — Transkriptions-Verträge (Carl-Finalplan).

Reine Datenmodelle + Engine-Protocol. KEIN echtes Whisper, kein Worker,
keine Persistenz (= spätere Tasks/Gates). Gate A STOPP: nach Freigabe
nicht mehr an diesen Contracts drehen.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class TranscriptError(Exception):
    """Kontrollierter Fehler in der Transkriptions-Schicht."""


@dataclass(frozen=True)
class TranscriptWord:
    start_ms: int
    end_ms: int
    text: str

    def __post_init__(self):
        if self.start_ms < 0:
            raise ValueError(f"start_ms muss >= 0 sein: {self.start_ms}")
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms muss > start_ms sein: {self.start_ms} >= {self.end_ms}")

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms,
                "text": self.text}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TranscriptWord":
        return cls(start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]),
                   text=str(d["text"]))


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    words: tuple[TranscriptWord, ...] = ()

    def __post_init__(self):
        if self.start_ms < 0:
            raise ValueError(f"start_ms muss >= 0 sein: {self.start_ms}")
        if self.end_ms <= self.start_ms:
            raise ValueError(
                f"end_ms muss > start_ms sein: {self.start_ms} >= {self.end_ms}")
        if not isinstance(self.words, tuple):
            object.__setattr__(self, "words", tuple(self.words))

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms,
                "text": self.text,
                "words": [w.to_dict() for w in self.words]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TranscriptSegment":
        return cls(
            start_ms=int(d["start_ms"]), end_ms=int(d["end_ms"]),
            text=str(d["text"]),
            words=tuple(TranscriptWord.from_dict(w)
                        for w in d.get("words", [])))


@dataclass(frozen=True)
class Transcript:
    segments: tuple[TranscriptSegment, ...] = ()

    def __post_init__(self):
        if not isinstance(self.segments, tuple):
            object.__setattr__(self, "segments", tuple(self.segments))

    def to_dict(self) -> dict[str, Any]:
        return {"segments": [s.to_dict() for s in self.segments]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Transcript":
        return cls(segments=tuple(TranscriptSegment.from_dict(s)
                                  for s in d.get("segments", [])))


@runtime_checkable
class TranscriptionEngine(Protocol):
    """Austauschbarer Transkriptions-Lieferant (mlx-whisper in v1;
    Tests injizieren einen Stub — kein echtes Whisper in pytest)."""

    def transcribe(self, audio_path: str, *, language: str,
                    model: str) -> Transcript:
        ...
