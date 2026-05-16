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
    track = video.find("track") if video is not None else None
    clipitems = track.findall("clipitem") if track is not None else []

    clips = []
    for c in clipitems:
        s = c.find("start")
        e = c.find("end")
        n = c.find("name")
        if s is None or e is None:
            continue
        start_f, end_f = int(s.text), int(e.text)
        if end_f <= start_f:
            continue
        clips.append({
            "name": (n.text if n is not None and n.text else "?"),
            "start_s": start_f / fps,
            "len_s": (end_f - start_f) / fps,
        })

    lengths = [round(c["len_s"], 3) for c in clips]
    n = len(clips)
    duration_s = max((c["start_s"] + c["len_s"] for c in clips), default=0.0)
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
            in_b = [c for c in clips if lo <= c["start_s"] < hi]
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
        "duration_min": duration_min,
        "shot_lengths_s": lengths,
        "min_s": min(lengths) if lengths else 0.0,
        "max_s": max(lengths) if lengths else 0.0,
        "mean_s": round(statistics.mean(lengths), 2) if lengths else 0.0,
        "median_s": p50,
        "p25_s": p25,
        "p75_s": p75,
        "cuts_per_min": round(n / duration_min, 3) if duration_min else 0.0,
        "cuts_per_min_buckets": buckets,
        "camera_clip_counts": dict(
            collections.Counter(c["name"] for c in clips)
        ),
    }


def _print_report(r: dict) -> None:
    print(f"FPS: {r['fps']}  |  Clips: {r['clip_count']}  |  "
          f"Dauer: {r['duration_min']:.1f} min")
    print(f"Cliplänge s — min {r['min_s']:.1f} / P25 {r['p25_s']:.1f} / "
          f"Median {r['median_s']:.1f} / P75 {r['p75_s']:.1f} / "
          f"max {r['max_s']:.1f} / Ø {r['mean_s']:.1f}")
    print(f"Schnitte/Min gesamt: {r['cuts_per_min']:.2f}")
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
