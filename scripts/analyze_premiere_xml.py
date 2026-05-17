#!/usr/bin/env python3
"""Analyse einer fertigen Premiere-Final-Cut-Pro-XML (FCP7 xmeml) einer
geschnittenen Folge — liefert echte Schnitt-Statistik, um die
Folgenschnitt-Stufe-2 v1-Zahlen zu fundieren (Carl-Plan Task 8).

Bewusst SEPARAT, KEINE App-Logik. Best-effort: nimmt Video-Track 1,
ignoriert Transitions. Ergebnis nur zum Defaults-Justieren, nicht zum
Algorithmus-Ändern.

Nutzung:  ./venv311/bin/python scripts/analyze_premiere_xml.py <datei.xml>
"""

import collections
import statistics
import sys
import xml.etree.ElementTree as ET


def analyze_premiere_xml(xml_path: str) -> dict:
    root = ET.parse(xml_path).getroot()
    seq = root.find("sequence")
    if seq is None:
        raise ValueError("Keine <sequence> gefunden — keine FCP7-XML?")

    tb = seq.find("rate/timebase")
    fps = int(tb.text) if tb is not None and tb.text else 25

    video = seq.find("media/video")
    tracks = video.findall("track") if video is not None else []
    v1 = tracks[0] if tracks else None
    v1_clipitems = v1.findall("clipitem") if v1 is not None else []

    warnings: list[str] = []
    transition_count = len(v1.findall("transitionitem")) if v1 is not None else 0
    all_video_clip_count = sum(len(t.findall("clipitem")) for t in tracks)
    if len(tracks) > 1 and any(t.findall("clipitem") for t in tracks[1:]):
        warnings.append(
            "Weitere Video-Spuren (V2/V3) enthalten Clipitems — "
            "Hauptstatistik nutzt trotzdem nur V1 (Overlay/Grafik ignoriert)."
        )

    clips = []
    nested = False
    for c in v1_clipitems:
        s = c.find("start")
        e = c.find("end")
        n = c.find("name")
        if c.find("sequence") is not None:
            nested = True
        if s is None or e is None:
            continue
        start_f, end_f = int(s.text), int(e.text)
        if end_f <= start_f:
            continue
        clips.append({
            "name": (n.text if n is not None and n.text else "?"),
            "start_f": start_f,
            "end_f": end_f,
            "len_s": (end_f - start_f) / fps,
        })
    if nested:
        warnings.append(
            "Nested/sequence-artige Clipitems gefunden — "
            "Kamera-Counts evtl. unzuverlässig."
        )

    # Gap/overlap detection on INTEGER FRAMES (exact). Doing it on
    # second-floats produced phantom ~1e-13 s gaps/overlaps on perfectly
    # frame-contiguous timelines.
    by_start = sorted(clips, key=lambda c: c["start_f"])
    gaps, overlaps = [], 0
    for prev, cur in zip(by_start, by_start[1:]):
        diff_f = cur["start_f"] - prev["end_f"]
        if diff_f > 0:
            gaps.append(diff_f / fps)
        elif diff_f < 0:
            overlaps += 1

    lengths = [round(c["len_s"], 3) for c in clips]
    n = len(clips)
    duration_f = max((c["end_f"] for c in clips), default=0)
    duration_s = duration_f / fps
    duration_min = duration_s / 60 if duration_s else 0.0

    if n >= 2:
        q = statistics.quantiles(lengths, n=4, method="inclusive")
        p25, p50, p75 = q[0], statistics.median(lengths), q[2]
    elif n == 1:
        p25 = p50 = p75 = lengths[0]
    else:
        p25 = p50 = p75 = 0.0

    buckets = []
    if duration_min > 0:
        num_buckets = int(duration_min // 5) + 1
        for i in range(num_buckets):
            lo, hi = i * 300.0, (i + 1) * 300.0
            in_b = [c for c in clips if lo <= c["start_f"] / fps < hi]
            minutes = max(0.0, min(hi, duration_s) - lo) / 60
            buckets.append({
                "bucket": i,
                "from_min": round(lo / 60, 1),
                "clips": len(in_b),
                "cuts_per_min": round(len(in_b) / minutes, 2) if minutes else 0.0,
            })

    return {
        "fps": fps,
        "clip_count": n,
        "v1_clip_count": n,
        "all_video_clip_count": all_video_clip_count,
        "video_track_count": len(tracks),
        "duration_min": duration_min,
        "shot_lengths_s": lengths,
        "min_s": min(lengths) if lengths else 0.0,
        "max_s": max(lengths) if lengths else 0.0,
        "mean_s": round(statistics.mean(lengths), 2) if lengths else 0.0,
        "median_s": p50,
        "p25_s": p25,
        "p75_s": p75,
        "clips_per_min": round(n / duration_min, 3) if duration_min else 0.0,
        "cuts_per_min": (
            round(max(0, n - 1) / duration_min, 3) if duration_min else 0.0
        ),
        "cuts_per_min_buckets": buckets,
        "camera_clip_counts": dict(
            collections.Counter(c["name"] for c in clips)
        ),
        "transition_count": transition_count,
        "gap_count": len(gaps),
        "gap_total_s": round(sum(gaps), 3),
        "max_gap_s": round(max(gaps), 3) if gaps else 0.0,
        "overlap_count": overlaps,
        "warnings": warnings,
    }


def _print_report(r: dict) -> None:
    print(f"FPS: {r['fps']}  |  Clips: {r['clip_count']}  |  "
          f"Dauer: {r['duration_min']:.1f} min")
    print(f"Cliplänge s — min {r['min_s']:.1f} / P25 {r['p25_s']:.1f} / "
          f"Median {r['median_s']:.1f} / P75 {r['p75_s']:.1f} / "
          f"max {r['max_s']:.1f} / Ø {r['mean_s']:.1f}")
    print(f"Clips/Min: {r['clips_per_min']:.2f}  |  "
          f"Schnitte/Min: {r['cuts_per_min']:.2f}")
    print(f"Video-Spuren: {r['video_track_count']}  |  V1-Clips: "
          f"{r['v1_clip_count']}  |  alle Video-Clips: "
          f"{r['all_video_clip_count']}  |  Transitions(V1): "
          f"{r['transition_count']}")
    print(f"Lücken: {r['gap_count']} (gesamt {r['gap_total_s']:.1f}s, "
          f"max {r['max_gap_s']:.1f}s)  |  Überlappungen: {r['overlap_count']}")
    if r["warnings"]:
        print("⚠ WARNUNGEN:")
        for w in r["warnings"]:
            print(f"  - {w}")
    print("Tempo-Verlauf (5-Min-Buckets):")
    for b in r["cuts_per_min_buckets"]:
        print(f"  ab {b['from_min']:>4} min: {b['clips']:>3} Clips "
              f"({b['cuts_per_min']}/min)")
    print("Kameras (Clips):")
    for name, cnt in sorted(r["camera_clip_counts"].items(),
                            key=lambda kv: -kv[1]):
        print(f"  {cnt:>4}  {name}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Nutzung: analyze_premiere_xml.py <datei.xml>", file=sys.stderr)
        return 1
    _print_report(analyze_premiere_xml(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
