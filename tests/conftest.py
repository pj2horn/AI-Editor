import subprocess
from pathlib import Path

import pytest


def make_clip(path: Path, seconds: int, vf: str = "", fps: int = 25, tc: str | None = None) -> Path:
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate={fps}:duration={seconds}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    if vf:
        cmd += ["-vf", vf]
    if tc:
        cmd += ["-timecode", tc]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture(scope="session")
def footage(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("footage")
    # Sharp for 4s, then heavily blurred.
    make_clip(d / "a_sharp_then_soft.mp4", 8, vf="boxblur=12:enable='gte(t,4)'", tc="10:00:00:00")
    # Underexposed throughout.
    make_clip(d / "b_dark.mp4", 6, vf="eq=brightness=-0.45")
    make_clip(d / "c_normal.mov", 5)
    (d / "notes.txt").write_text("not a video")
    return d
