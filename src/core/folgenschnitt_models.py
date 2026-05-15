from dataclasses import dataclass
from enum import Enum
from typing import Any


class SpeakerId(str, Enum):
    MATZE = "matze"
    GUEST = "guest"
    UNKNOWN = "unknown"


class CameraRole(str, Enum):
    MATZE_WIDE = "matze_wide"
    GUEST_WIDE = "guest_wide"
    GUEST_CLOSE = "guest_close"
    UNUSED = "unused"


def _speaker(value: str | SpeakerId | None) -> SpeakerId:
    if value is None:
        return SpeakerId.UNKNOWN
    if isinstance(value, SpeakerId):
        return value
    return SpeakerId(value)


def _camera_role(value: str | CameraRole) -> CameraRole:
    if isinstance(value, CameraRole):
        return value
    return CameraRole(value)


def _validate_range(start_ms: int, end_ms: int) -> None:
    if end_ms <= start_ms:
        raise ValueError(f"end_ms must be greater than start_ms: {start_ms} >= {end_ms}")


@dataclass(frozen=True)
class MicAssignment:
    track_index: int
    path: str
    speaker: SpeakerId

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_index": self.track_index,
            "path": self.path,
            "speaker": self.speaker.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MicAssignment":
        return cls(
            track_index=int(data["track_index"]),
            path=str(data["path"]),
            speaker=_speaker(data["speaker"]),
        )


@dataclass(frozen=True)
class CameraAssignment:
    path: str
    role: CameraRole

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "role": self.role.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CameraAssignment":
        return cls(
            path=str(data["path"]),
            role=_camera_role(data["role"]),
        )


@dataclass(frozen=True)
class ActivityFrame:
    start_ms: int
    end_ms: int
    levels_db: dict[str, float]
    noise_floor_db: dict[str, float]
    dominance_db: float
    raw_speaker: SpeakerId
    smoothed_speaker: SpeakerId
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
            "raw_speaker": self.raw_speaker.value,
            "smoothed_speaker": self.smoothed_speaker.value,
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
            raw_speaker=_speaker(data.get("raw_speaker")),
            smoothed_speaker=_speaker(data.get("smoothed_speaker")),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass(frozen=True)
class SpeakerTurn:
    start_ms: int
    end_ms: int
    speaker: SpeakerId
    confidence: float
    source: str = "speaker_activity"

    def __post_init__(self):
        _validate_range(self.start_ms, self.end_ms)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker": self.speaker.value,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpeakerTurn":
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            speaker=_speaker(data["speaker"]),
            confidence=float(data.get("confidence", 0.0)),
            source=str(data.get("source", "speaker_activity")),
        )


@dataclass(frozen=True)
class EditDecision:
    start_ms: int
    end_ms: int
    camera_path: str
    speaker: SpeakerId
    reason: str

    def __post_init__(self):
        _validate_range(self.start_ms, self.end_ms)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "camera_path": self.camera_path,
            "speaker": self.speaker.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditDecision":
        return cls(
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            camera_path=str(data["camera_path"]),
            speaker=_speaker(data["speaker"]),
            reason=str(data.get("reason", "")),
        )
