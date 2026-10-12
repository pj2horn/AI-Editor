import json
import xml.etree.ElementTree as ET
from fractions import Fraction

from ai_editor import export
from ai_editor.analyze import analyze_folder
from ai_editor.cli import main, parse_duration
from ai_editor.score import Weights, segment_clips, select


def quiet(_msg):
    pass


def test_analysis_and_cache(footage, tmp_path):
    cache = tmp_path / "cache.json"
    analyses = analyze_folder(footage, cache_path=cache, log=quiet)
    assert [a.info.name for a in analyses] == ["a_sharp_then_soft.mp4", "b_dark.mp4", "c_normal.mov"]
    a = analyses[0]
    assert a.info.fps == 25 and (a.info.width, a.info.height) == (640, 360)
    assert a.info.timecode == "10:00:00:00"
    assert len(a.metrics.times) == 16  # 8s at 2 fps

    logs = []
    again = analyze_folder(footage, cache_path=cache, log=logs.append)
    assert not any("Analysing" in m for m in logs), "second run should come entirely from cache"
    assert again[0].metrics.sharpness == a.metrics.sharpness


def test_scoring_prefers_sharp_and_well_exposed(footage, tmp_path):
    analyses = analyze_folder(footage, cache_path=tmp_path / "c.json", log=quiet)
    segs = segment_clips(analyses, segment_length=4.0)
    a_segs = [s for s in segs if s.clip_index == 0]
    assert len(a_segs) == 2
    assert a_segs[0].focus > a_segs[1].focus
    assert a_segs[0].score > a_segs[1].score

    dark = [s for s in segs if s.clip_index == 1]
    normal = [s for s in segs if s.clip_index == 2]
    assert max(s.exposure for s in dark) < min(s.exposure for s in normal)

    picked = select(segs, max_per_clip=1)
    assert len(picked) == 3
    assert picked[0].start == 0.0  # the sharp half of clip a

    # Focus-only weighting ignores exposure entirely.
    focus_only = segment_clips(analyses, 4.0, Weights.parse("focus=1"))
    assert all(abs(s.score - 100 * s.focus) < 0.01 for s in focus_only)


def test_target_duration_and_order(footage, tmp_path):
    analyses = analyze_folder(footage, cache_path=tmp_path / "c.json", log=quiet)
    segs = segment_clips(analyses, segment_length=2.0)
    picked = select(segs, max_per_clip=0, target_duration=6.0)
    assert 6.0 <= sum(s.duration for s in picked) < 8.0
    by_score = select(segs, max_per_clip=0, order="score")
    assert [s.score for s in by_score] == sorted((s.score for s in by_score), reverse=True)


def test_exports(footage, tmp_path):
    analyses = analyze_folder(footage, cache_path=tmp_path / "c.json", log=quiet)
    picked = select(segment_clips(analyses, 4.0), max_per_clip=1)

    fcp = tmp_path / "s.fcpxml"
    export.write(picked, fcp)
    root = ET.parse(fcp).getroot()
    clips = root.findall(".//spine/asset-clip")
    assert len(clips) == 3
    # Clip a carries source TC 10:00:00:00, so its in-point is 36000s.
    assert clips[0].get("start") == "36000s"
    assert clips[0].get("duration") == "4s"
    assert clips[1].get("offset") == "3604s"

    xm = tmp_path / "s.xml"
    export.write(picked, xm)
    xroot = ET.parse(xm).getroot()
    vitems = xroot.findall(".//video/track/clipitem")
    expected, rec = [], 0
    for s in picked:
        expected.append(rec)
        rec += round(s.duration * 25)
    assert [int(v.find("start").text) for v in vitems] == expected
    assert len(xroot.findall(".//audio/track/clipitem")) == 3

    edl = tmp_path / "s.edl"
    export.write(picked, edl)
    text = edl.read_text()
    assert "001  AX       V     C        10:00:00:00 10:00:04:00 01:00:00:00 01:00:04:00" in text
    assert "* FROM CLIP NAME: a_sharp_then_soft.mp4" in text

    js = tmp_path / "s.json"
    export.write(picked, js)
    assert len(json.loads(js.read_text())) == 3


def test_timecode_roundtrip():
    assert export.tc_to_frames("01:00:00:00", Fraction(25)) == 90000
    assert export.frames_to_tc(90000, Fraction(25)) == "01:00:00:00"
    assert export.tc_to_frames("00:01:00;02", Fraction(30000, 1001)) == 1800


def test_parse_duration():
    assert parse_duration("16m") == 960
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1:30") == 90
    assert parse_duration("4") == 4


def test_cli_cut(footage, tmp_path):
    out1, out2 = tmp_path / "x.fcpxml", tmp_path / "x.edl"
    rc = main(["cut", str(footage), "--cache", str(tmp_path / "c.json"),
               "--segment", "2s", "--target", "6s", "-o", str(out1), "-o", str(out2)])
    assert rc == 0 and out1.exists() and out2.exists()
