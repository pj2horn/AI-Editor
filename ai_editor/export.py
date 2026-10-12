"""Write selects as timelines NLEs can import.

.fcpxml  DaVinci Resolve, Final Cut Pro
.xml     Premiere Pro (FCP7 XML / xmeml), also Resolve
.edl     CMX3600, anything (Avid, Resolve, Premiere)
.csv     spreadsheet of selects with scores
.json    machine-readable selects
"""

from __future__ import annotations

import csv
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .score import Segment


# ---------------------------------------------------------------- timecode

def _nominal(fps: Fraction) -> int:
    return round(fps)


def _is_ntsc(fps: Fraction) -> bool:
    return fps.denominator == 1001


def tc_to_frames(tc: str, fps: Fraction) -> int:
    """Timecode string -> frame count. ';' or '.' before frames means drop-frame."""
    drop = ";" in tc or "." in tc
    h, m, s, f = (int(x) for x in tc.replace(";", ":").replace(".", ":").split(":"))
    base = _nominal(fps)
    frames = ((h * 60 + m) * 60 + s) * base + f
    if drop and base in (30, 60):
        dropped = 2 * (base // 30)
        total_min = h * 60 + m
        frames -= dropped * (total_min - total_min // 10)
    return frames


def frames_to_tc(frames: int, fps: Fraction) -> str:
    base = _nominal(fps)
    f = frames % base
    s = frames // base
    return f"{s // 3600 % 24:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{f:02d}"


def _source_start_frames(seg: Segment) -> int:
    return tc_to_frames(seg.clip.timecode, seg.clip.fps) if seg.clip.timecode else 0


def _src_frames(seg: Segment) -> tuple[int, int]:
    """Segment in/out as frame numbers in the clip's own rate, inside the clip."""
    fps = seg.clip.fps
    last = max(1, math.floor(seg.clip.duration * fps))
    a = min(round(seg.start * fps), last - 1)
    b = min(max(a + 1, round(seg.end * fps)), last)
    return a, b


def timeline_fps(segments: list[Segment]) -> Fraction:
    if not segments:
        return Fraction(25)
    return Counter(s.clip.fps for s in segments).most_common(1)[0][0]


def _rt(x: Fraction) -> str:
    """Rational time for FCPXML."""
    x = Fraction(x)
    return f"{x.numerator}s" if x.denominator == 1 else f"{x.numerator}/{x.denominator}s"


# ---------------------------------------------------------------- FCPXML

def to_fcpxml(segments: list[Segment], name: str, fps: Fraction) -> str:
    frame = 1 / fps
    root = ET.Element("fcpxml", version="1.9")
    resources = ET.SubElement(root, "resources")

    first = segments[0].clip if segments else None
    width, height = (first.width, first.height) if first else (1920, 1080)
    ET.SubElement(resources, "format", id="r0", frameDuration=_rt(frame), width=str(width), height=str(height))

    formats: dict[tuple, str] = {}
    assets: dict[str, str] = {}
    next_id = 1
    for seg in segments:
        c = seg.clip
        key = (c.fps, c.width, c.height)
        if key not in formats:
            fid = f"r{next_id}"
            next_id += 1
            formats[key] = fid
            ET.SubElement(resources, "format", id=fid, frameDuration=_rt(1 / c.fps),
                          width=str(c.width), height=str(c.height))
        if c.path not in assets:
            aid = f"r{next_id}"
            next_id += 1
            assets[c.path] = aid
            start = Fraction(_source_start_frames(seg)) / c.fps
            dur = Fraction(math.floor(c.duration * c.fps)) / c.fps
            attrs = dict(id=aid, name=Path(c.path).stem, start=_rt(start), duration=_rt(dur),
                         hasVideo="1", format=formats[key], videoSources="1")
            if c.has_audio:
                attrs.update(hasAudio="1", audioSources="1", audioChannels=str(c.audio_channels or 2))
            asset = ET.SubElement(resources, "asset", **attrs)
            ET.SubElement(asset, "media-rep", kind="original-media", src=Path(c.path).as_uri())

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name=name)
    project = ET.SubElement(event, "project", name=name)
    sequence = ET.SubElement(project, "sequence", format="r0", tcStart="3600s", tcFormat="NDF")
    spine = ET.SubElement(sequence, "spine")

    offset_frames = 0
    for seg in segments:
        c = seg.clip
        a, b = _src_frames(seg)
        src_start = Fraction(_source_start_frames(seg) + a) / c.fps
        # Duration must land on the timeline's frame grid.
        dur_frames = max(1, math.floor(Fraction(b - a) / c.fps * fps))
        ET.SubElement(spine, "asset-clip", ref=assets[c.path], name=Path(c.path).stem,
                      offset=_rt(3600 + offset_frames * frame), start=_rt(src_start),
                      duration=_rt(dur_frames * frame), format=formats[(c.fps, c.width, c.height)],
                      tcFormat="NDF")
        offset_frames += dur_frames
    sequence.set("duration", _rt(offset_frames * frame))

    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + ET.tostring(root, encoding="unicode") + "\n"


# ---------------------------------------------------------------- FCP7 XML (Premiere)

def _rate_el(parent: ET.Element, fps: Fraction) -> None:
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(_nominal(fps))
    ET.SubElement(rate, "ntsc").text = "TRUE" if _is_ntsc(fps) else "FALSE"


def _tc_el(parent: ET.Element, fps: Fraction, frames: int) -> None:
    tc = ET.SubElement(parent, "timecode")
    _rate_el(tc, fps)
    ET.SubElement(tc, "string").text = frames_to_tc(frames, fps)
    ET.SubElement(tc, "frame").text = str(frames)
    ET.SubElement(tc, "displayformat").text = "NDF"


def to_xmeml(segments: list[Segment], name: str, fps: Fraction) -> str:
    root = ET.Element("xmeml", version="4")
    seq = ET.SubElement(root, "sequence", id="sequence-1")
    ET.SubElement(seq, "name").text = name
    dur_el = ET.SubElement(seq, "duration")
    _rate_el(seq, fps)
    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    fmt = ET.SubElement(ET.SubElement(video, "format"), "samplecharacteristics")
    _rate_el(fmt, fps)
    first = segments[0].clip if segments else None
    ET.SubElement(fmt, "width").text = str(first.width if first else 1920)
    ET.SubElement(fmt, "height").text = str(first.height if first else 1080)
    vtrack = ET.SubElement(video, "track")
    audio = ET.SubElement(media, "audio")
    atrack = ET.SubElement(audio, "track")

    files_written: set[str] = set()
    file_ids: dict[str, str] = {}
    rec = 0
    for i, seg in enumerate(segments, 1):
        c = seg.clip
        a, b = _src_frames(seg)
        length = max(1, math.floor(Fraction(b - a) / c.fps * fps))
        total = math.floor(c.duration * c.fps)
        fid = file_ids.setdefault(c.path, f"file-{len(file_ids) + 1}")

        def clipitem(track: ET.Element, kind: str) -> ET.Element:
            item = ET.SubElement(track, "clipitem", id=f"clipitem-{kind}{i}")
            ET.SubElement(item, "name").text = Path(c.path).name
            ET.SubElement(item, "duration").text = str(total)
            _rate_el(item, c.fps)
            ET.SubElement(item, "start").text = str(rec)
            ET.SubElement(item, "end").text = str(rec + length)
            ET.SubElement(item, "in").text = str(a)
            ET.SubElement(item, "out").text = str(a + round(Fraction(length) / fps * c.fps))
            f = ET.SubElement(item, "file", id=fid)
            if fid not in files_written:
                files_written.add(fid)
                ET.SubElement(f, "name").text = Path(c.path).name
                ET.SubElement(f, "pathurl").text = Path(c.path).as_uri()
                _rate_el(f, c.fps)
                ET.SubElement(f, "duration").text = str(total)
                _tc_el(f, c.fps, _source_start_frames(seg))
                fm = ET.SubElement(f, "media")
                sc = ET.SubElement(ET.SubElement(fm, "video"), "samplecharacteristics")
                ET.SubElement(sc, "width").text = str(c.width)
                ET.SubElement(sc, "height").text = str(c.height)
                if c.has_audio:
                    ET.SubElement(ET.SubElement(fm, "audio"), "channelcount").text = str(c.audio_channels or 2)
            return item

        clipitem(vtrack, "v")
        if c.has_audio:
            item = clipitem(atrack, "a")
            st = ET.SubElement(item, "sourcetrack")
            ET.SubElement(st, "mediatype").text = "audio"
            ET.SubElement(st, "trackindex").text = "1"
        rec += length

    dur_el.text = str(rec)
    _tc_el(seq, fps, 3600 * _nominal(fps))
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="unicode") + "\n"


# ---------------------------------------------------------------- EDL

def to_edl(segments: list[Segment], name: str, fps: Fraction) -> str:
    lines = [f"TITLE: {name}", "FCM: NON-DROP FRAME", ""]
    rec = 3600 * _nominal(fps)
    for i, seg in enumerate(segments, 1):
        c = seg.clip
        a, b = _src_frames(seg)
        base = _source_start_frames(seg)
        length = max(1, math.floor(Fraction(b - a) / c.fps * fps))
        src_out = a + round(Fraction(length) / fps * c.fps)
        lines.append(
            f"{i:03d}  AX       V     C        "
            f"{frames_to_tc(base + a, c.fps)} {frames_to_tc(base + src_out, c.fps)} "
            f"{frames_to_tc(rec, fps)} {frames_to_tc(rec + length, fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {Path(c.path).name}")
        lines.append(f"* COMMENT: SCORE {seg.score:.0f} FOCUS {seg.focus:.2f} "
                     f"MOTION {seg.motion:.2f} EXPOSURE {seg.exposure:.2f}")
        lines.append("")
        rec += length
    return "\n".join(lines)


# ---------------------------------------------------------------- CSV / JSON

def _rows(segments: list[Segment]) -> list[dict]:
    return [{
        "clip": Path(s.clip.path).name, "path": s.clip.path,
        "start": round(s.start, 3), "end": round(s.end, 3), "duration": round(s.duration, 3),
        "score": s.score, "focus": round(s.focus, 3), "motion": round(s.motion, 3),
        "exposure": round(s.exposure, 3),
    } for s in segments]


def to_csv(segments: list[Segment], path: Path) -> None:
    rows = _rows(segments)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["clip"])
        writer.writeheader()
        writer.writerows(rows)


def write(segments: list[Segment], out: Path, name: str | None = None, fps: Fraction | None = None) -> None:
    name = name or out.stem
    fps = fps or timeline_fps(segments)
    ext = out.suffix.lower()
    if ext == ".fcpxml":
        out.write_text(to_fcpxml(segments, name, fps))
    elif ext == ".xml":
        out.write_text(to_xmeml(segments, name, fps))
    elif ext == ".edl":
        out.write_text(to_edl(segments, name, fps))
    elif ext == ".csv":
        to_csv(segments, out)
    elif ext == ".json":
        out.write_text(json.dumps(_rows(segments), indent=2))
    else:
        raise ValueError(f"unsupported output type {ext!r}; use .fcpxml, .xml, .edl, .csv or .json")
