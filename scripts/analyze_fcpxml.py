#!/usr/bin/env python3
"""Confidence-gated FCPXML composition ESTIMATOR (Carl-Spec).

⚠ FCPXML composition estimate, NOT authoritative.
Use for provisional Stage-2 tuning only. A flattened cut timeline (B)
is the better anchor; this reverse-reads a messy Premiere FCPXML 1.8.

Reconstructs the visible camera per top-spine segment by resolving
nested enabled clips and effective lane (a disabled ancestor does NOT
kill visible children — that is the Premiere export trap). Reports a
confidence rating; LOW means: do not use as default anchor.
"""

import collections
import re
import statistics
import sys
import urllib.parse
import xml.etree.ElementTree as ET

_VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mxf", ".mts")
_CAM_SEG = re.compile(r'(?i)(?:^|[ _])cam(?:[ _]|\d|$)')
_CAM_FILE = re.compile(r'(?i)\bcam ?(\d+)\b')

DISCLAIMER = ("FCPXML composition estimate, NOT authoritative — "
              "provisional Stage-2 tuning only.")


def camera_key_from_src(src):
    """Camera key from an asset source path. None if not a camera
    (graphics/audio/title). Prefer a speaking path folder, then a
    'CAM N' in the filename, else the basename."""
    if not src:
        return None
    path = urllib.parse.unquote(src)
    path = re.sub(r'^\w+://', '', path)
    segs = [s for s in path.split('/') if s]
    if not segs:
        return None
    fname = segs[-1]
    if not fname.lower().endswith(_VIDEO_EXT):
        return None  # not a camera (png/jpg/wav/mp3/...)
    for seg in reversed(segs[:-1]):
        if _CAM_SEG.search(seg):
            return seg.strip()
    m = _CAM_FILE.search(fname)
    if m:
        return f"CAM {m.group(1)}"
    return fname.rsplit('.', 1)[0]


def _rt(t):
    if not t:
        return 0.0
    t = t.rstrip('s')
    if '/' in t:
        a, b = t.split('/')
        return float(a) / float(b)
    return float(t)


def _asset_src(a):
    s = a.get("src")
    if s:
        return s
    mr = a.find("media-rep")
    return mr.get("src") if mr is not None else None


def _candidates(elem, eff_lane, assets):
    """Yield (effective_lane, camera_key) for every enabled descendant
    that resolves to a camera. The candidate's OWN enabled flag counts;
    a disabled ancestor does NOT disqualify its children."""
    lane = elem.get("lane")
    lane = int(lane) if lane not in (None, "") else eff_lane
    own_ok = elem.get("enabled") != "0"
    ref = elem.get("ref")
    if ref is None:
        v = elem.find("video")
        if v is not None:
            ref = v.get("ref")
    if own_ok and ref is not None and ref in assets:
        ck = camera_key_from_src(assets[ref])
        if ck is not None:
            yield (lane, ck)
    # A clip's own primary <video> is resolved above and inherits this
    # clip's enabled state; do NOT recurse into it as an independent
    # candidate (that would resurrect a disabled clip's footage). Only
    # nested clips are independent — for THEM an ancestor enabled="0"
    # does not disqualify (the Premiere export trap).
    for child in elem:
        if child.tag in ("clip", "asset-clip", "spine", "ref-clip"):
            yield from _candidates(child, lane, assets)


def analyze_fcpxml(path):
    root = ET.parse(path).getroot()
    if root.tag != "fcpxml":
        raise ValueError("Kein <fcpxml> Root — falsches Format für diesen Estimator")

    res = root.find("resources")
    assets = {a.get("id"): _asset_src(a) for a in res.iter("asset")}
    fps = 25
    seq = root.find(".//sequence")
    fmtid = seq.get("format") if seq is not None else None
    for f in res.iter("format"):
        if f.get("id") == fmtid and f.get("frameDuration"):
            fps = round(1.0 / _rt(f.get("frameDuration")))
            break
    spine = seq.find("spine")

    segments = []          # (start_s, end_s, camkey)
    gaps = []
    ambiguous = []         # (start,end)
    unresolved = []        # (start,end) no camera at all
    for c in spine:
        if c.tag == "gap":
            gaps.append(_rt(c.get("duration")))
            continue
        if c.tag == "transition":
            continue
        start = _rt(c.get("offset"))
        dur = _rt(c.get("duration"))
        end = start + dur
        cands = list(_candidates(c, 0, assets))
        if not cands:
            unresolved.append((start, end))
            continue
        top = max(l for l, _ in cands)
        keys = {k for l, k in cands if l == top}
        if len(keys) == 1:
            segments.append((start, end, next(iter(keys))))
        else:
            ambiguous.append((start, end))

    # merge adjacent same-camera segments (gap <= 2 frames)
    segments.sort(key=lambda s: s[0])
    tol = 2.0 / fps
    runs = []
    for s, e, k in segments:
        if runs and runs[-1][2] == k and s - runs[-1][1] <= tol:
            runs[-1] = (runs[-1][0], e, k)
        else:
            runs.append((s, e, k))

    rl = [e - s for s, e, k in runs if e > s]
    n = len(runs)
    visible_s = sum(rl)
    vis_min = visible_s / 60 if visible_s else 0.0
    if len(rl) >= 2:
        q = statistics.quantiles(rl, n=4, method="inclusive")
        p25, p50, p75 = round(q[0], 1), round(statistics.median(rl), 1), round(q[2], 1)
    elif rl:
        p25 = p50 = p75 = round(rl[0], 1)
    else:
        p25 = p50 = p75 = 0.0

    by_dur = collections.Counter()
    by_cnt = collections.Counter()
    for s, e, k in runs:
        by_dur[k] += e - s
        by_cnt[k] += 1
    buckets = []
    if visible_s:
        nb = int((runs[-1][0]) // 300) + 1
        for i in range(nb):
            lo, hi = i * 300.0, (i + 1) * 300.0
            buckets.append({"from_min": round(lo / 60, 1),
                            "runs": sum(1 for s, _, _ in runs if lo <= s < hi)})

    amb_s = sum(e - s for s, e in ambiguous)
    unres_s = sum(e - s for s, e in unresolved)
    total_s = visible_s + amb_s + unres_s
    pct_unclear = (amb_s + unres_s) / total_s if total_s else 1.0
    keys = set(by_dur)
    max_run = max(rl) if rl else 0.0
    dominant_share = (max(by_dur.values()) / visible_s
                      if visible_s and by_dur else 0.0)

    # Technical unambiguity (one winner per segment) does NOT mean
    # semantic credibility. A confidently-read base assembly track is
    # still wrong. These checks downgrade implausible cuts to LOW.
    warnings = []
    implausible = False
    if dominant_share >= 0.80:
        implausible = True
        warnings.append(
            f"Dominant camera covers {dominant_share*100:.0f}% of "
            f"visible duration")
    if p75 > 0 and max_run >= 20 * p75:
        implausible = True
        warnings.append(
            f"Longest run is {max_run:.0f}s, suspiciously above P75 "
            f"({p75:.0f}s)")
    elif max_run >= 1200:
        implausible = True
        warnings.append(f"Longest run is {max_run:.0f}s (>= 20 min)")
    if n < 30 and vis_min > 60:
        implausible = True
        warnings.append(
            f"Only {n} runs over {vis_min:.0f} min — implausibly few cuts")
    if implausible:
        warnings.append(
            "Likely reading base assembly, not final camera decisions")

    if len(keys) < 2 or pct_unclear > 0.05 or implausible:
        conf = "LOW"
    elif pct_unclear >= 0.01:
        conf = "MEDIUM"
    else:
        conf = "HIGH"
    if len(keys) < 2:
        warnings.append("Nur 1 Kamera-Key erkannt — Schätzung unbrauchbar als Anker.")
    if pct_unclear > 0.05:
        warnings.append(f"{pct_unclear*100:.1f}% der Dauer mehrdeutig/unaufgelöst.")

    return {
        "disclaimer": DISCLAIMER,
        "confidence": conf,
        "fps": fps,
        "run_count": n,
        "visible_min": round(vis_min, 2),
        "cuts_per_min": round(max(0, n - 1) / vis_min, 2) if vis_min else 0.0,
        "min_s": round(min(rl), 1) if rl else 0.0,
        "p25_s": p25, "median_s": p50, "p75_s": p75,
        "max_s": round(max(rl), 1) if rl else 0.0,
        "mean_s": round(statistics.mean(rl), 1) if rl else 0.0,
        "camera_share_by_duration": [(k, round(v, 1))
                                     for k, v in by_dur.most_common()],
        "camera_share_by_count": dict(by_cnt),
        "buckets": buckets,
        "gap_count": len(gaps),
        "gap_total_s": round(sum(gaps), 2),
        "max_gap_s": round(max(gaps), 2) if gaps else 0.0,
        "ambiguous_segment_count": len(ambiguous),
        "ambiguous_duration_s": round(amb_s, 1),
        "unresolved_duration_s": round(unres_s, 1),
        "pct_unclear": round(pct_unclear * 100, 2),
        "warnings": warnings,
    }


def _report(r):
    print(f"⚠ {r['disclaimer']}")
    print(f"CONFIDENCE: {r['confidence']}  (unklar {r['pct_unclear']}% )")
    print(f"Runs: {r['run_count']}  sichtbar {r['visible_min']} min  "
          f"Schnitte/Min {r['cuts_per_min']}")
    print(f"Run-Länge s: min {r['min_s']} / P25 {r['p25_s']} / "
          f"Median {r['median_s']} / P75 {r['p75_s']} / max {r['max_s']} / "
          f"Ø {r['mean_s']}")
    print("Kamera-Anteil (Dauer s):")
    for k, v in r["camera_share_by_duration"]:
        print(f"  {v:>8}  {k}")
    print(f"Gaps: {r['gap_count']} ({r['gap_total_s']}s)  "
          f"ambiguous: {r['ambiguous_segment_count']} "
          f"({r['ambiguous_duration_s']}s)  unresolved {r['unresolved_duration_s']}s")
    for w in r["warnings"]:
        print(f"  ⚠ {w}")


def main():
    if len(sys.argv) != 2:
        print("Nutzung: analyze_fcpxml.py <datei.fcpxml>", file=sys.stderr)
        return 1
    _report(analyze_fcpxml(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
