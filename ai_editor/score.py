"""Turn raw frame metrics into scored segments and pick the selects."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .analyze import ClipAnalysis
from .probe import ClipInfo


@dataclass
class Weights:
    focus: float = 0.6
    motion: float = 0.2
    exposure: float = 0.2

    def normalized(self) -> "Weights":
        total = self.focus + self.motion + self.exposure
        if total <= 0:
            raise ValueError("weights must not all be zero")
        return Weights(self.focus / total, self.motion / total, self.exposure / total)

    @classmethod
    def parse(cls, text: str) -> "Weights":
        """Parse 'focus=0.6,motion=0.2,exposure=0.2' (missing keys become 0)."""
        vals = {"focus": 0.0, "motion": 0.0, "exposure": 0.0}
        for part in text.split(","):
            key, _, val = part.partition("=")
            key = key.strip().lower()
            if key not in vals:
                raise ValueError(f"unknown weight {key!r}; use focus, motion, exposure")
            vals[key] = float(val)
        return cls(**vals)


@dataclass
class Segment:
    clip: ClipInfo
    clip_index: int
    start: float
    end: float
    focus: float
    motion: float
    exposure: float
    score: float  # 0..100

    @property
    def duration(self) -> float:
        return self.end - self.start


def _rank(values: np.ndarray) -> np.ndarray:
    """Percentile rank in 0..1 (ties share the average rank)."""
    if values.size == 0:
        return values
    order = values.argsort(kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    ranks[order] = np.arange(values.size)
    # average tied ranks
    uniq, inv = np.unique(values, return_inverse=True)
    sums = np.bincount(inv, weights=ranks)
    counts = np.bincount(inv)
    ranks = (sums / counts)[inv]
    return ranks / max(1, values.size - 1)


def frame_scores(analyses: list[ClipAnalysis]) -> list[dict[str, np.ndarray]]:
    """Per-frame 0..1 scores. Focus and motion are ranked across the whole shoot,
    so 'sharp' means sharp relative to everything else you filmed."""
    sharp = np.concatenate([np.log1p(np.asarray(a.metrics.sharpness, dtype=np.float64)) for a in analyses]) \
        if analyses else np.array([])
    motion = np.concatenate([np.log1p(np.asarray(a.metrics.motion, dtype=np.float64)) for a in analyses]) \
        if analyses else np.array([])
    focus_r, motion_r = _rank(sharp), _rank(motion)

    out, i = [], 0
    for a in analyses:
        n = len(a.metrics.times)
        luma = np.asarray(a.metrics.luma)
        clipped = np.asarray(a.metrics.clip_hi) + np.asarray(a.metrics.clip_lo)
        exposure = 1.0 - np.abs(luma - 0.45) / 0.45 - 3.0 * clipped
        out.append({
            "focus": focus_r[i:i + n],
            "motion": motion_r[i:i + n],
            "exposure": np.clip(exposure, 0.0, 1.0),
        })
        i += n
    return out


def segment_clips(
    analyses: list[ClipAnalysis],
    segment_length: float = 4.0,
    weights: Weights | None = None,
) -> list[Segment]:
    if segment_length <= 0:
        raise ValueError("segment length must be positive")
    w = (weights or Weights()).normalized()
    segments: list[Segment] = []
    for idx, (a, fs) in enumerate(zip(analyses, frame_scores(analyses))):
        times = np.asarray(a.metrics.times)
        dur = a.info.duration or (times[-1] if times.size else 0.0)
        n_full = int(dur // segment_length)
        bounds = [(k * segment_length, (k + 1) * segment_length) for k in range(n_full)]
        tail = dur - n_full * segment_length
        if n_full == 0 and dur > 0:
            bounds = [(0.0, dur)]  # short clip: one segment covering all of it
        elif tail >= segment_length / 2:
            bounds.append((n_full * segment_length, dur))
        for start, end in bounds:
            mask = (times >= start) & (times < end)
            if not mask.any():
                continue
            # Focus uses the 25th percentile: a segment is only as usable as its softer moments.
            f = float(np.percentile(fs["focus"][mask], 25))
            m = float(fs["motion"][mask].mean())
            e = float(fs["exposure"][mask].mean())
            score = 100.0 * (w.focus * f + w.motion * m + w.exposure * e)
            segments.append(Segment(a.info, idx, start, end, f, m, e, round(score, 2)))
    return segments


def select(
    segments: list[Segment],
    max_per_clip: int = 1,
    min_score: float = 0.0,
    target_duration: float | None = None,
    order: str = "clip",
) -> list[Segment]:
    by_clip: dict[int, list[Segment]] = {}
    for s in segments:
        if s.score >= min_score:
            by_clip.setdefault(s.clip_index, []).append(s)

    picked: list[Segment] = []
    for segs in by_clip.values():
        picked.extend(sorted(segs, key=lambda s: -s.score)[:max_per_clip] if max_per_clip > 0 else segs)

    if target_duration is not None:
        kept, total = [], 0.0
        for s in sorted(picked, key=lambda s: -s.score):
            if total >= target_duration:
                break
            kept.append(s)
            total += s.duration
        picked = kept

    if order == "score":
        return sorted(picked, key=lambda s: -s.score)
    return sorted(picked, key=lambda s: (s.clip_index, s.start))
