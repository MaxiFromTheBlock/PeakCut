from dataclasses import dataclass
from typing import Any

UNKNOWN_SPEAKER = None

SHOT_WIDE = "weit"
SHOT_CLOSE = "nah_close"
SHOT_MEDIUM = "halbnah"
SHOT_TOTAL = "totale"
SHOT_UNUSED = "unused"

BUILTIN_SHOT_TYPES = [
    SHOT_WIDE,
    SHOT_CLOSE,
    SHOT_MEDIUM,
    SHOT_TOTAL,
    SHOT_UNUSED,
]

PERSON_REQUIRED_SHOT_TYPES = {SHOT_WIDE, SHOT_CLOSE, SHOT_MEDIUM}
PERSONLESS_SHOT_TYPES = {SHOT_TOTAL, SHOT_UNUSED}


def _normalize_optional_person(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_required_person(value: str | None, field_name: str = "person") -> str:
    normalized = _normalize_optional_person(value)
    if normalized is None:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_speaker(value: str | None) -> str | None:
    return _normalize_optional_person(value)


def _validate_range(start_ms: int, end_ms: int) -> None:
    if end_ms <= start_ms:
        raise ValueError(f"end_ms must be greater than start_ms: {start_ms} >= {end_ms}")


@dataclass(frozen=True)
class MicAssignment:
    track_index: int
    path: str
    person: str
    speaker_key: str = ""

    def __post_init__(self):
        object.__setattr__(self, "person", _normalize_required_person(self.person))
        if not self.speaker_key:
            object.__setattr__(self, "speaker_key", f"mic_{self.track_index + 1}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_index": self.track_index,
            "path": self.path,
            "person": self.person,
            "speaker_key": self.speaker_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MicAssignment":
        return cls(
            track_index=int(data["track_index"]),
            path=str(data["path"]),
            person=str(data["person"]),
            speaker_key=str(data.get("speaker_key", "")),
        )


@dataclass(frozen=True)
class CameraAssignment:
    path: str
    shot_type: str
    person: str | None = None

    def __post_init__(self):
        if not str(self.path).strip():
            raise ValueError("path must not be empty")
        if not str(self.shot_type).strip():
            raise ValueError("shot_type must not be empty")
        if self.shot_type in PERSONLESS_SHOT_TYPES:
            object.__setattr__(self, "person", None)
        elif self.shot_type in PERSON_REQUIRED_SHOT_TYPES:
            object.__setattr__(
                self, "person", _normalize_required_person(self.person)
            )
        else:
            object.__setattr__(
                self, "person", _normalize_optional_person(self.person)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "shot_type": self.shot_type,
            "person": self.person,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraAssignment":
        return cls(
            path=str(data["path"]),
            shot_type=str(data["shot_type"]),
            person=data.get("person"),
        )


@dataclass(frozen=True)
class ActivityFrame:
    start_ms: int
    end_ms: int
    levels_db: dict[str, float]
    noise_floor_db: dict[str, float]
    dominance_db: float
    raw_speaker: str | None
    smoothed_speaker: str | None
    confidence: float

    def __post_init__(self):
        _validate_range(self.start_ms, self.end_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "levels_db": dict(self.levels_db),
            "noise_floor_db": dict(self.noise_floor_db),
            "dominance_db": self.dominance_db,
            "raw_speaker": self.raw_speaker,
            "smoothed_speaker": self.smoothed_speaker,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActivityFrame":
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            levels_db={str(k): float(v) for k, v in data.get("levels_db", {}).items()},
            noise_floor_db={str(k): float(v) for k, v in data.get("noise_floor_db", {}).items()},
            dominance_db=float(data.get("dominance_db", 0.0)),
            raw_speaker=_normalize_speaker(data.get("raw_speaker")),
            smoothed_speaker=_normalize_speaker(data.get("smoothed_speaker")),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass(frozen=True)
class SpeakerTurn:
    start_ms: int
    end_ms: int
    speaker: str
    confidence: float
    source: str = "speaker_activity"

    def __post_init__(self):
        _validate_range(self.start_ms, self.end_ms)
        object.__setattr__(
            self, "speaker", _normalize_required_person(self.speaker, "speaker")
        )

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker": self.speaker,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpeakerTurn":
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            speaker=str(data["speaker"]),
            confidence=float(data.get("confidence", 0.0)),
            source=str(data.get("source", "speaker_activity")),
        )


@dataclass(frozen=True)
class EditDecision:
    start_ms: int
    end_ms: int
    camera_path: str
    speaker: str
    reason: str

    def __post_init__(self):
        _validate_range(self.start_ms, self.end_ms)
        object.__setattr__(
            self, "speaker", _normalize_required_person(self.speaker, "speaker")
        )

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "camera_path": self.camera_path,
            "speaker": self.speaker,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditDecision":
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            camera_path=str(data["camera_path"]),
            speaker=str(data["speaker"]),
            reason=str(data.get("reason", "")),
        )
