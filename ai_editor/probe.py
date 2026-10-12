"""Read clip metadata with ffprobe."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".m4v", ".mxf", ".mkv", ".avi", ".mts", ".m2ts", ".webm", ".mpg", ".mpeg",
}


@dataclass
class ClipInfo:
    path: str
    duration: float
    fps_num: int
    fps_den: int
    width: int
    height: int
    codec: str
    has_audio: bool
    audio_channels: int
    timecode: str | None

    @property
    def fps(self) -> Fraction:
        return Fraction(self.fps_num, self.fps_den)

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ClipInfo":
        return cls(**d)


def find_clips(folder: Path, recursive: bool = True) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    clips = [
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and not p.name.startswith(".")
    ]
    return sorted(clips, key=lambda p: str(p).lower())


def _parse_rate(rate: str | None) -> Fraction | None:
    if not rate or rate in ("0/0", "0"):
        return None
    try:
        r = Fraction(rate)
    except (ValueError, ZeroDivisionError):
        return None
    return r if r > 0 else None


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            return int(side["rotation"])
    rot = (stream.get("tags") or {}).get("rotate")
    return int(rot) if rot else 0


def probe(path: Path) -> ClipInfo:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    if video is None:
        raise ValueError(f"{path.name}: no video stream")
    audio = [s for s in streams if s.get("codec_type") == "audio"]

    fps = _parse_rate(video.get("r_frame_rate")) or _parse_rate(video.get("avg_frame_rate")) or Fraction(25)
    # Snap common NTSC rates so they stay exact (29.97 -> 30000/1001).
    fps = fps.limit_denominator(1001)

    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
    width, height = int(video["width"]), int(video["height"])
    if abs(_rotation(video)) % 180 == 90:
        width, height = height, width

    tags = {**(data.get("format", {}).get("tags") or {}), **(video.get("tags") or {})}
    timecode = tags.get("timecode")
    if timecode is None:
        tc_stream = next((s for s in streams if (s.get("tags") or {}).get("timecode")), None)
        timecode = tc_stream["tags"]["timecode"] if tc_stream else None

    return ClipInfo(
        path=str(path.resolve()),
        duration=duration,
        fps_num=fps.numerator,
        fps_den=fps.denominator,
        width=width,
        height=height,
        codec=video.get("codec_name", "?"),
        has_audio=bool(audio),
        audio_channels=sum(int(s.get("channels") or 0) for s in audio),
        timecode=timecode,
    )
