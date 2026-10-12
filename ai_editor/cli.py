"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
import time
from fractions import Fraction
from pathlib import Path

from . import __version__, export
from .analyze import analyze_folder
from .score import Weights, segment_clips, select


def parse_duration(text: str) -> float:
    """'90', '90s', '16m', '1h30m', '1:30' -> seconds."""
    text = text.strip().lower()
    if ":" in text:
        secs = 0.0
        for part in text.split(":"):
            secs = secs * 60 + float(part)
        return secs
    total, num = 0.0, ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch in "hms" and num:
            total += float(num) * {"h": 3600, "m": 60, "s": 1}[ch]
            num = ""
        else:
            raise argparse.ArgumentTypeError(f"bad duration {text!r}")
    return total + (float(num) if num else 0.0)


def fmt_duration(secs: float) -> str:
    secs = int(round(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def _analysis_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("folder", type=Path, help="folder of footage")
    p.add_argument("--cache", type=Path, help="analysis cache file (default: FOLDER/.ai-editor-cache.json)")
    p.add_argument("--sample-fps", type=float, default=2.0, help="frames sampled per second (default 2)")
    p.add_argument("--jobs", "-j", type=int, help="clips analysed in parallel")
    p.add_argument("--no-recursive", action="store_true", help="don't scan subfolders")
    p.add_argument("--force", action="store_true", help="ignore the cache and re-analyse everything")


def _run_analysis(args) -> list:
    t0 = time.time()
    analyses = analyze_folder(args.folder, cache_path=args.cache, sample_fps=args.sample_fps,
                              jobs=args.jobs, recursive=not args.no_recursive, force=args.force)
    total = sum(a.info.duration for a in analyses)
    print(f"{len(analyses)} clips, {fmt_duration(total)} of footage, ready in {time.time() - t0:.1f}s",
          file=sys.stderr)
    return analyses


def cmd_analyze(args) -> int:
    _run_analysis(args)
    return 0


def cmd_cut(args) -> int:
    analyses = _run_analysis(args)
    if not analyses:
        return 1
    segments = segment_clips(analyses, args.segment, Weights.parse(args.weights))
    picked = select(segments, max_per_clip=args.max_per_clip, min_score=args.min_score,
                    target_duration=args.target, order=args.order)
    if not picked:
        print("No segments passed the filters; try a lower --min-score.", file=sys.stderr)
        return 1

    fps = Fraction(args.fps).limit_denominator(1001) if args.fps else None
    outputs = args.output or [args.folder / "selects.fcpxml"]
    for out in outputs:
        export.write(picked, out, name=args.name, fps=fps)
        print(f"wrote {out}", file=sys.stderr)

    total = sum(a.info.duration for a in analyses)
    kept = sum(s.duration for s in picked)
    print(f"{fmt_duration(total)} -> {len(picked)} selects, {fmt_duration(kept)} "
          f"({100 * kept / total:.0f}% of footage)", file=sys.stderr)
    return 0


def cmd_report(args) -> int:
    analyses = _run_analysis(args)
    segments = segment_clips(analyses, args.segment, Weights.parse(args.weights))
    best: dict[int, float] = {}
    for s in segments:
        best[s.clip_index] = max(best.get(s.clip_index, 0.0), s.score)
    print(f"{'clip':40} {'dur':>8} {'fps':>7} {'res':>11} {'best':>5}")
    for i, a in enumerate(analyses):
        c = a.info
        print(f"{c.name[:40]:40} {fmt_duration(c.duration):>8} {float(c.fps):7.3f} "
              f"{f'{c.width}x{c.height}':>11} {best.get(i, 0):5.0f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-editor", description="Score every segment of your footage and export a selects timeline.")
    parser.add_argument("--version", action="version", version=f"ai-editor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="analyse a folder (results are cached)")
    _analysis_args(p)
    p.set_defaults(func=cmd_analyze)

    for name, func, help_ in (("cut", cmd_cut, "pick the best segments and export a timeline"),
                              ("report", cmd_report, "list clips with their best segment score")):
        p = sub.add_parser(name, help=help_)
        _analysis_args(p)
        p.add_argument("--segment", type=parse_duration, default=4.0, help="segment length (default 4s)")
        p.add_argument("--weights", default="focus=0.6,motion=0.2,exposure=0.2",
                       help="scoring weights (default focus=0.6,motion=0.2,exposure=0.2)")
        if name == "cut":
            p.add_argument("-o", "--output", type=Path, action="append",
                           help="output file; .fcpxml .xml .edl .csv .json (repeatable)")
            p.add_argument("--max-per-clip", type=int, default=1,
                           help="segments kept per clip, 0 = no limit (default 1)")
            p.add_argument("--min-score", type=float, default=0.0, help="drop segments below this 0-100 score")
            p.add_argument("--target", type=parse_duration, help="cap total length, e.g. 16m")
            p.add_argument("--order", choices=("clip", "score"), default="clip",
                           help="timeline order (default: clip order)")
            p.add_argument("--fps", help="timeline frame rate, e.g. 25 or 30000/1001 (default: most common)")
            p.add_argument("--name", help="timeline name (default: output file name)")
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
