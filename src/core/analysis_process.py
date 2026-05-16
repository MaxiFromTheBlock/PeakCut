#!/usr/bin/env python3
"""
Standalone analysis process for PeakCut.

Runs sync + peak detection in a separate Python process to avoid
conflicts with the main GUI (especially screenshot operations).

Communication:
- Progress updates: stderr (line-based, "PROGRESS: message")
- Final results: stdout (JSON)
- Errors: stderr (line-based, "ERROR: message")

Usage:
    python analysis_process.py <config_json>

Where config_json contains:
{
    "keyboard_track": "/path/to/keyboard.wav",
    "mic_tracks": ["/path/to/mic1.wav", ...],
    "videos": ["/path/to/video1.mp4", ...],
    "reference_track": "/path/to/mix.wav",
    "temp_dir": "/path/to/temp",
    "export_dir": "/path/to/export",
    "config": {
        "threshold_factor": 0.3,
        "min_gap_ms": 12000,
        "context_duration_ms": 15000,
        "fps": 25
    }
}
"""

import sys
import os
import json


def progress(msg):
    """Send progress update to parent process."""
    print(f"PROGRESS: {msg}", file=sys.stderr, flush=True)


def error(msg):
    """Send error to parent process."""
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)


def run_analysis(config_data):
    """Run the full analysis and return results dict."""

    # Import heavy libraries only when needed
    progress("Lade Module...")

    # Add parent dir to path for imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(script_dir)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from pydub import AudioSegment
    from core.detection import detect_peaks
    from core.sync import sync_videos

    keyboard_track = config_data["keyboard_track"]
    mic_tracks = config_data.get("mic_tracks", [])
    videos = config_data.get("videos", [])
    reference_track = config_data.get("reference_track")
    temp_dir = config_data["temp_dir"]
    export_dir = config_data["export_dir"]
    cfg = config_data["config"]

    os.makedirs(export_dir, exist_ok=True)

    results = {
        "peaks": [],
        "video_offsets": [],
        "speaker_activity": [],
        "speaker_activity_csv": None,
        "speaker_activity_mic_assignments": [],
        "speaker_turns": [],
        "folgenschnitt_edit_decisions": [],
        "error": None
    }

    # Step 1: Sync videos (if any)
    if videos and reference_track:
        progress("Synchronisiere Videos...")
        try:
            video_offsets = sync_videos(
                video_files=videos,
                reference_path=reference_track,
                temp_dir=temp_dir,
                fps=cfg.get("fps", 25),
                status_fn=progress
            )
            results["video_offsets"] = video_offsets
            progress(f"Sync fertig: {len(video_offsets)} Offset(s)")
        except Exception as e:
            error(f"Sync fehlgeschlagen: {e}")
            results["video_offsets"] = []

    # Step 2: Speaker activity analysis (Folgenschnitt Stage 1)
    try:
        from core.speaker_activity import analyze_speaker_activity, build_default_mic_assignments

        default_people = config_data.get("default_people") or ["Matze", "Gast"]
        mic_assignments = build_default_mic_assignments(
            mic_tracks, default_people=default_people
        )
        if len(mic_assignments) >= 2:
            progress("Analysiere Sprecher-Aktivitaet...")
            speaker_activity_csv = os.path.join(export_dir, "speaker_activity.csv")
            speaker_activity = analyze_speaker_activity(
                mic_assignments,
                csv_path=speaker_activity_csv,
            )
            results["speaker_activity"] = [frame.to_dict() for frame in speaker_activity]
            results["speaker_activity_csv"] = speaker_activity_csv
            results["speaker_activity_mic_assignments"] = [
                assignment.to_dict() for assignment in mic_assignments
            ]
            progress(f"Sprecher-Aktivitaet: {len(speaker_activity)} Fenster")
    except Exception as e:
        error(f"Sprecher-Analyse fehlgeschlagen: {e}")
        results["speaker_activity"] = []
        results["speaker_activity_csv"] = None

    # Step 3: Peak detection
    if not keyboard_track or not os.path.exists(keyboard_track):
        error("Keine Keyboard-Datei gefunden")
        results["error"] = "No keyboard file"
        return results

    progress("Analysiere Peaks...")
    try:
        raw_peaks = detect_peaks(
            keyboard_track,
            cfg.get("threshold_factor", 0.3),
            cfg.get("min_gap_ms", 12000)
        )

        ctx = cfg.get("context_duration_ms", 15000)

        # Convert to serializable format (int() to convert numpy int64 to Python int)
        results["peaks"] = [
            {
                "index": i,
                "position_ms": int(t),
                "in_point_ms": int(max(0, t - ctx)),
                "out_point_ms": int(t + ctx),
                "context_ms": int(ctx),
                "ignored": False
            }
            for i, t in enumerate(raw_peaks)
        ]

        progress(f"{len(results['peaks'])} Peaks gefunden")

    except Exception as e:
        error(f"Peak-Analyse fehlgeschlagen: {e}")
        results["error"] = str(e)

    return results


def main():
    if len(sys.argv) < 2:
        error("Usage: analysis_process.py <config_json>")
        sys.exit(1)

    config_json = sys.argv[1]

    try:
        config_data = json.loads(config_json)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON config: {e}")
        sys.exit(1)

    try:
        results = run_analysis(config_data)
        # Output results as JSON to stdout
        print(json.dumps(results, ensure_ascii=False))
    except Exception as e:
        error(f"Analyse abgebrochen: {e}")
        print(json.dumps({"error": str(e), "peaks": [], "video_offsets": []}))
        sys.exit(1)


if __name__ == "__main__":
    main()
