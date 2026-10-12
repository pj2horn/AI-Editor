"""Decode sampled frames with ffmpeg and measure focus, motion and exposure.

Raw per-frame measurements are cached, so changing the segment length,
weights or selection rules never requires decoding the footage again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .probe import ClipInfo, find_clips, probe

CACHE_VERSION = 1
CACHE_NAME = ".ai-editor-cache.json"


@dataclass
class FrameMetrics:
    """Raw measurements for frames sampled at `sample_fps`."""

    times: list[float] = field(default_factory=list)
    sharpness: list[float] = field(default_factory=list)  # variance of the Laplacian
    motion: list[float] = field(default_factory=list)     # mean abs diff to previous sample
    luma: list[float] = field(default_factory=list)       # mean luma, 0..1
    clip_hi: list[float] = field(default_factory=list)    # fraction of blown-out pixels
    clip_lo: list[float] = field(default_factory=list)    # fraction of crushed pixels


@dataclass
class ClipAnalysis:
    info: ClipInfo
    metrics: FrameMetrics
    mtime: float
    size: int

    def to_dict(self) -> dict:
        return {"info": self.info.to_dict(), "metrics": self.metrics.__dict__,
                "mtime": self.mtime, "size": self.size}

    @classmethod
    def from_dict(cls, d: dict) -> "ClipAnalysis":
        return cls(ClipInfo.from_dict(d["info"]), FrameMetrics(**d["metrics"]), d["mtime"], d["size"])


def _laplacian_var(img: np.ndarray) -> float:
    lap = (4 * img[1:-1, 1:-1] - img[:-2, 1:-1] - img[2:, 1:-1] - img[1:-1, :-2] - img[1:-1, 2:])
    return float(lap.var())


def measure_clip(info: ClipInfo, sample_fps: float = 2.0, width: int = 480) -> FrameMetrics:
    w = min(width, info.width)
    w -= w % 2
    h = max(2, round(w * info.height / info.width / 2) * 2)
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", info.path, "-an", "-sn", "-dn",
        "-vf", f"fps={sample_fps},scale={w}:{h}:flags=area,format=gray",
        "-f", "rawvideo", "-",
    ]
    frame_bytes = w * h
    m = FrameMetrics()
    prev = None
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        assert proc.stdout is not None
        i = 0
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            raw = np.frombuffer(buf, dtype=np.uint8).reshape(h, w)
            img = raw.astype(np.float32)
            m.times.append(round((i + 0.5) / sample_fps, 4))
            m.sharpness.append(round(_laplacian_var(img), 3))
            m.motion.append(round(float(np.abs(img - prev).mean()) if prev is not None else 0.0, 4))
            m.luma.append(round(float(img.mean()) / 255.0, 4))
            m.clip_hi.append(round(float((raw >= 250).mean()), 4))
            m.clip_lo.append(round(float((raw <= 5).mean()), 4))
            prev = img
            i += 1
        stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if proc.returncode != 0 and not m.times:
        raise RuntimeError(f"{info.name}: ffmpeg failed: {stderr.strip()[:300]}")
    # The first sample has no predecessor; reuse the second one's motion.
    if len(m.motion) > 1:
        m.motion[0] = m.motion[1]
    return m


def _load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    if data.get("version") != CACHE_VERSION:
        return {}
    return data


def analyze_folder(
    folder: Path,
    cache_path: Path | None = None,
    sample_fps: float = 2.0,
    width: int = 480,
    jobs: int | None = None,
    recursive: bool = True,
    force: bool = False,
    log=lambda msg: print(msg, file=sys.stderr),
) -> list[ClipAnalysis]:
    folder = folder.resolve()
    cache_path = cache_path or folder / CACHE_NAME
    settings = {"sample_fps": sample_fps, "width": width}
    cache = {} if force else _load_cache(cache_path)
    cached_clips = cache.get("clips", {}) if cache.get("settings") == settings else {}

    paths = find_clips(folder, recursive=recursive)
    if not paths:
        log(f"No video files found in {folder}")
        return []

    results: dict[str, ClipAnalysis] = {}
    todo: list[Path] = []
    for p in paths:
        st = p.stat()
        hit = cached_clips.get(str(p.resolve()))
        if hit and hit["mtime"] == st.st_mtime and hit["size"] == st.st_size:
            results[str(p.resolve())] = ClipAnalysis.from_dict(hit)
        else:
            todo.append(p)

    if todo:
        log(f"Analysing {len(todo)} clip(s) ({len(results)} cached)...")

    def work(p: Path) -> ClipAnalysis:
        st = p.stat()
        info = probe(p)
        return ClipAnalysis(info, measure_clip(info, sample_fps, width), st.st_mtime, st.st_size)

    jobs = jobs or max(1, min(8, (os.cpu_count() or 2)))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(work, p): p for p in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            p = futures[fut]
            try:
                results[str(p.resolve())] = fut.result()
                log(f"  [{n}/{len(todo)}] {p.name}")
            except Exception as e:  # keep going; one bad file shouldn't sink the batch
                log(f"  [{n}/{len(todo)}] skipped {p.name}: {e}")

    ordered = [results[str(p.resolve())] for p in paths if str(p.resolve()) in results]
    try:
        cache_path.write_text(json.dumps({
            "version": CACHE_VERSION,
            "settings": settings,
            "clips": {a.info.path: a.to_dict() for a in ordered},
        }))
    except OSError as e:
        log(f"Could not write cache {cache_path}: {e}")
    return ordered
