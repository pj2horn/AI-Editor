"""Local web interface: `ai-editor ui FOLDER` serves it on http://127.0.0.1:8765."""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import tempfile
import threading
import time
import webbrowser
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import export
from .analyze import ClipAnalysis, analyze_folder
from .score import Weights, frame_scores, segment_clips, select

EXPORT_TYPES = {"fcpxml": ".fcpxml", "xml": ".xml", "edl": ".edl", "csv": ".csv", "json": ".json"}


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.folder: str = ""
        self.analyses: list[ClipAnalysis] = []
        self.status = {"state": "idle", "done": 0, "total": 0, "current": "", "elapsed": 0.0, "error": ""}
        self.started = 0.0
        self.thumbs: dict[tuple[int, float], bytes] = {}

    def snapshot(self) -> dict:
        with self.lock:
            st = dict(self.status)
            if st["state"] == "running":
                st["elapsed"] = time.time() - self.started
            return {"folder": self.folder, "status": st, "clips": self.clips()}

    def clips(self) -> list[dict]:
        return [{
            "id": i, "name": a.info.name, "path": a.info.path, "duration": a.info.duration,
            "fps": float(a.info.fps), "width": a.info.width, "height": a.info.height,
            "codec": a.info.codec, "has_audio": a.info.has_audio, "timecode": a.info.timecode,
        } for i, a in enumerate(self.analyses)]

    def start_analysis(self, folder: str, force: bool = False) -> None:
        path = Path(folder).expanduser()
        if not path.is_dir():
            raise ValueError(f"not a folder: {folder}")
        with self.lock:
            if self.status["state"] == "running":
                raise ValueError("analysis already running")
            self.folder = str(path.resolve())
            self.analyses = []
            self.thumbs.clear()
            self.started = time.time()
            self.status = {"state": "running", "done": 0, "total": 0, "current": "", "elapsed": 0.0, "error": ""}

        def progress(done: int, total: int, name: str) -> None:
            with self.lock:
                self.status.update(done=done, total=total, current=name)

        def run() -> None:
            try:
                result = analyze_folder(path, force=force, progress=progress, log=lambda _m: None)
                with self.lock:
                    self.analyses = result
                    self.status.update(state="done", elapsed=time.time() - self.started, current="")
            except Exception as e:  # surfaced in the UI
                with self.lock:
                    self.status.update(state="error", error=str(e), elapsed=time.time() - self.started)

        threading.Thread(target=run, daemon=True).start()


def _settings(body: dict) -> dict:
    w = body.get("weights") or {}
    target = body.get("target")
    return {
        "segment": max(0.5, float(body.get("segment", 4.0))),
        "weights": Weights(float(w.get("focus", 0.6)), float(w.get("motion", 0.2)), float(w.get("exposure", 0.2))),
        "max_per_clip": int(body.get("max_per_clip", 1)),
        "min_score": float(body.get("min_score", 0.0)),
        "target": float(target) if target not in (None, "", 0) else None,
        "order": body.get("order", "clip") if body.get("order") in ("clip", "score") else "clip",
    }


def compute(analyses: list[ClipAnalysis], body: dict):
    s = _settings(body)
    segs = segment_clips(analyses, s["segment"], s["weights"])
    picked = select(segs, max_per_clip=s["max_per_clip"], min_score=s["min_score"],
                    target_duration=s["target"], order=s["order"])
    return segs, picked


def segments_payload(analyses: list[ClipAnalysis], body: dict) -> dict:
    segs, picked = compute(analyses, body)
    ids = {id(s): n for n, s in enumerate(segs)}
    chosen = {id(s) for s in picked}
    total = sum(a.info.duration for a in analyses)
    kept = sum(s.duration for s in picked)
    return {
        "segments": [{
            "id": n, "clip": s.clip_index, "start": round(s.start, 3), "end": round(s.end, 3),
            "score": s.score, "focus": round(s.focus, 3), "motion": round(s.motion, 3),
            "exposure": round(s.exposure, 3), "selected": id(s) in chosen,
        } for n, s in enumerate(segs)],
        "timeline": [ids[id(s)] for s in picked],
        "summary": {"segments": len(segs), "selected": len(picked), "selected_duration": kept,
                    "total_duration": total, "clips": len(analyses)},
    }


def frames_payload(analyses: list[ClipAnalysis], clip: int) -> dict:
    fs = frame_scores(analyses)[clip]
    return {"times": analyses[clip].metrics.times,
            **{k: np.round(v, 3).tolist() for k, v in fs.items()}}


def export_bytes(analyses: list[ClipAnalysis], body: dict) -> tuple[bytes, str]:
    fmt = body.get("format", "fcpxml")
    if fmt not in EXPORT_TYPES:
        raise ValueError(f"unknown export format {fmt!r}")
    _, picked = compute(analyses, body)
    if not picked:
        raise ValueError("nothing selected to export")
    name = (body.get("name") or "AI-Editor Selects").strip()
    fps = Fraction(str(body["fps"])).limit_denominator(1001) if body.get("fps") else None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"selects{EXPORT_TYPES[fmt]}"
        export.write(picked, out, name=name, fps=fps)
        return out.read_bytes(), out.name


def thumbnail(path: str, t: float, width: int = 320) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", path,
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "5", "-f", "image2", "-c:v", "mjpeg", "-"],
        check=True, capture_output=True,
    ).stdout


class Handler(BaseHTTPRequestHandler):
    state: State  # set on the subclass in serve()
    server_version = "AI-Editor"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    # ------------------------------------------------------------ helpers
    def _send(self, code: int, body: bytes, ctype: str, headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data).encode(), "application/json")

    def _error(self, msg: str, code: int = 400) -> None:
        self._json({"error": msg}, code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _clip(self, q: dict) -> tuple[int, ClipAnalysis | None]:
        try:
            i = int(q["clip"][0])
            return i, self.state.analyses[i] if i >= 0 else None
        except (KeyError, ValueError, IndexError):
            return -1, None

    # ------------------------------------------------------------ routes
    def do_GET(self) -> None:
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            html = resources.files("ai_editor").joinpath("web/index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if url.path == "/api/state":
            return self._json(self.state.snapshot())
        if url.path == "/api/frames":
            i, clip = self._clip(q)
            if clip is None:
                return self._error("unknown clip", 404)
            return self._json(frames_payload(self.state.analyses, i))
        if url.path == "/api/thumb":
            i, clip = self._clip(q)
            if clip is None:
                return self._error("unknown clip", 404)
            t = round(float(q.get("t", ["0"])[0]), 1)
            key = (i, t)
            if key not in self.state.thumbs:
                if len(self.state.thumbs) > 1000:
                    self.state.thumbs.clear()
                try:
                    self.state.thumbs[key] = thumbnail(clip.info.path, t)
                except subprocess.CalledProcessError:
                    return self._error("could not render thumbnail", 500)
            return self._send(200, self.state.thumbs[key], "image/jpeg",
                              {"Cache-Control": "max-age=3600"})
        if url.path == "/api/media":
            _, clip = self._clip(q)
            if clip is None:
                return self._error("unknown clip", 404)
            return self._media(clip.info.path)
        self._error("not found", 404)

    do_HEAD = do_GET

    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            body = self._body()
            if url.path == "/api/analyze":
                self.state.start_analysis(body.get("folder", ""), bool(body.get("force")))
                return self._json(self.state.snapshot())
            if url.path == "/api/segments":
                return self._json(segments_payload(self.state.analyses, body))
            if url.path == "/api/export":
                data, filename = export_bytes(self.state.analyses, body)
                ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                return self._send(200, data, ctype,
                                  {"Content-Disposition": f'attachment; filename="{filename}"'})
        except (ValueError, KeyError) as e:
            return self._error(str(e))
        self._error("not found", 404)

    def _media(self, path: str) -> None:
        """Serve a source file with HTTP Range support so <video> can seek."""
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "video/mp4"
        if ctype == "video/quicktime":
            ctype = "video/mp4"  # lets Chrome attempt H.264 .mov files
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            if a:
                start = int(a)
                end = int(b) if b else size - 1
            elif b:
                start = max(0, size - int(b))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            try:
                while remaining > 0:
                    chunk = fh.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser cancelled the request while seeking


def serve(folder: str | None = None, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    state = State()
    handler = type("BoundHandler", (Handler,), {"state": state})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{httpd.server_address[1]}/"
    if folder:
        state.start_analysis(folder)
    print(f"AI-Editor running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
