import csv
import math
import os
from dataclasses import dataclass

import numpy as np
import soundfile as sf

from .folgenschnitt_models import ActivityFrame, MicAssignment

DEFAULT_PEOPLE = ["Matze", "Gast"]


@dataclass(frozen=True)
class SpeakerActivityParams:
    window_ms: int = 200
    hop_ms: int = 100
    noise_floor_percentile: float = 10.0
    active_db_above_noise: float = 10.0
    switch_dominance_db: float = 6.0
    hold_dominance_db: float = 3.0


SPEAKER_ACTIVITY_DEFAULTS = SpeakerActivityParams()


def build_default_mic_assignments(
    mic_tracks: list[str],
    default_people: list[str] | None = None,
) -> list[MicAssignment]:
    """Build MVP default assignments.

    The defensive filter is load-bearing: mix/keyboard tracks must never be
    mistaken for a person's microphone. Filter first, then pair the first two
    real speaker mics with default_people positionally — never pair against
    the raw mic_tracks list.
    """
    people = default_people if default_people is not None else list(DEFAULT_PEOPLE)
    speaker_tracks = [
        path for path in mic_tracks
        if _is_speaker_mic_candidate(path)
    ]
    assignments = []
    for idx, (path, person) in enumerate(zip(speaker_tracks[:2], people)):
        assignments.append(MicAssignment(track_index=idx, path=path, person=person))
    return assignments


def _is_speaker_mic_candidate(path: str) -> bool:
    basename = os.path.basename(path).lower()
    excluded_markers = ("mix", "keyboard", "keys", "klavier")
    return not any(marker in basename for marker in excluded_markers)


def analyze_speaker_activity(
    mic_assignments: list[MicAssignment],
    params: SpeakerActivityParams = SPEAKER_ACTIVITY_DEFAULTS,
    csv_path: str | None = None,
) -> list[ActivityFrame]:
    """Analyze relative speaker dominance in low-resolution audio windows."""
    if len(mic_assignments) < 2:
        return []

    level_series = {
        assignment.speaker_key: _read_window_levels_db(
            assignment.path,
            window_ms=params.window_ms,
            hop_ms=params.hop_ms,
        )
        for assignment in mic_assignments
    }

    if not level_series:
        return []

    min_frames = min(len(values) for values in level_series.values())
    if min_frames == 0:
        return []

    for speaker in list(level_series):
        level_series[speaker] = level_series[speaker][:min_frames]

    noise_floor = {
        speaker: float(np.percentile(values, params.noise_floor_percentile))
        for speaker, values in level_series.items()
    }

    frames = []
    previous_speaker: str | None = None

    for frame_idx in range(min_frames):
        levels_db = {
            speaker: float(values[frame_idx])
            for speaker, values in level_series.items()
        }
        raw_speaker, dominance_db, confidence = _classify_frame(
            levels_db,
            noise_floor,
            params,
            previous_speaker,
        )
        smoothed_speaker = raw_speaker
        if smoothed_speaker is not None:
            previous_speaker = smoothed_speaker

        frame = ActivityFrame(
            start_ms=frame_idx * params.hop_ms,
            end_ms=frame_idx * params.hop_ms + params.window_ms,
            levels_db=levels_db,
            noise_floor_db=noise_floor,
            dominance_db=dominance_db,
            raw_speaker=raw_speaker,
            smoothed_speaker=smoothed_speaker,
            confidence=confidence,
        )
        frames.append(frame)

    if csv_path:
        write_speaker_activity_csv(frames, csv_path)

    return frames


def read_speaker_activity_csv(csv_path: str) -> list[ActivityFrame]:
    """Exakte Umkehr von write_speaker_activity_csv (HC-4 Task 3).

    'unknown'/'' -> None für raw/smoothed_speaker. Speaker-Keys =
    Spalten auf '_db', die ein passendes '_noise_floor_db' haben
    (schließt dominance_db aus)."""
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        fns = reader.fieldnames or []
        keys = [c[:-3] for c in fns
                if c.endswith("_db") and not c.endswith("_noise_floor_db")
                and f"{c[:-3]}_noise_floor_db" in fns]
        frames: list[ActivityFrame] = []
        for row in reader:
            def _spk(v):
                return None if v in (None, "", "unknown", "None") else v
            frames.append(ActivityFrame(
                start_ms=int(row["start_ms"]),
                end_ms=int(row["end_ms"]),
                levels_db={k: float(row[f"{k}_db"]) for k in keys
                           if row.get(f"{k}_db") not in (None, "")},
                noise_floor_db={k: float(row[f"{k}_noise_floor_db"])
                                for k in keys
                                if row.get(f"{k}_noise_floor_db")
                                not in (None, "")},
                dominance_db=float(row["dominance_db"] or 0.0),
                raw_speaker=_spk(row.get("raw_speaker")),
                smoothed_speaker=_spk(row.get("smoothed_speaker")),
                confidence=float(row["confidence"] or 0.0),
            ))
    return frames


def write_speaker_activity_csv(frames: list[ActivityFrame], csv_path: str) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    speaker_keys = list(frames[0].levels_db.keys()) if frames else []
    fieldnames = (
        ["start_ms", "end_ms"]
        + [f"{key}_db" for key in speaker_keys]
        + [f"{key}_noise_floor_db" for key in speaker_keys]
        + ["dominance_db", "raw_speaker", "smoothed_speaker", "confidence"]
    )

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for frame in frames:
            row = {
                "start_ms": frame.start_ms,
                "end_ms": frame.end_ms,
                "dominance_db": frame.dominance_db,
                "raw_speaker": frame.raw_speaker or "unknown",
                "smoothed_speaker": frame.smoothed_speaker or "unknown",
                "confidence": frame.confidence,
            }
            for key in speaker_keys:
                row[f"{key}_db"] = frame.levels_db.get(key, "")
                row[f"{key}_noise_floor_db"] = frame.noise_floor_db.get(key, "")
            writer.writerow(row)


def _read_window_levels_db(path: str, window_ms: int, hop_ms: int) -> list[float]:
    levels = []
    with sf.SoundFile(path) as audio:
        sr = audio.samplerate
        window_samples = max(1, int(sr * window_ms / 1000))
        hop_samples = max(1, int(sr * hop_ms / 1000))
        total_frames = len(audio)

        start = 0
        while start + window_samples <= total_frames:
            audio.seek(start)
            data = audio.read(window_samples, dtype="float32", always_2d=True)
            mono = np.mean(data, axis=1)
            levels.append(_rms_db(mono))
            start += hop_samples

    return levels


def _rms_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return 20.0 * math.log10(max(rms, 1e-9))


def _classify_frame(
    levels_db: dict[str, float],
    noise_floor_db: dict[str, float],
    params: SpeakerActivityParams,
    previous_speaker: str | None,
) -> tuple[str | None, float, float]:
    active = []
    for speaker, level_db in levels_db.items():
        if level_db - noise_floor_db.get(speaker, -120.0) >= params.active_db_above_noise:
            active.append((speaker, level_db))

    if not active:
        return None, 0.0, 0.0

    active.sort(key=lambda item: item[1], reverse=True)
    top_speaker, top_level = active[0]
    second_level = active[1][1] if len(active) > 1 else -120.0
    dominance_db = top_level - second_level

    threshold = params.switch_dominance_db
    if previous_speaker == top_speaker:
        threshold = params.hold_dominance_db

    if dominance_db < threshold:
        return None, float(dominance_db), 0.0

    confidence = min(1.0, max(0.0, dominance_db / params.switch_dominance_db))
    return top_speaker, float(dominance_db), float(confidence)
