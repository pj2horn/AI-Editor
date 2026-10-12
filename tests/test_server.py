import json
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer

import pytest

from ai_editor.server import Handler, State


@pytest.fixture()
def server(footage):
    state = State()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), type("H", (Handler,), {"state": state}))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, state
    httpd.shutdown()
    httpd.server_close()


def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {})) as r:
        return r.status, dict(r.headers), r.read()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.status, dict(r.headers), r.read()


def wait_done(base):
    for _ in range(300):
        st = json.loads(get(base + "/api/state")[2])
        if st["status"]["state"] in ("done", "error"):
            return st
        time.sleep(0.05)
    raise TimeoutError


def test_ui_end_to_end(server, footage):
    base, _ = server
    status, headers, html = get(base + "/")
    assert status == 200 and b'id="tri"' in html

    post(base + "/api/analyze", {"folder": str(footage)})
    st = wait_done(base)
    assert st["status"]["state"] == "done"
    assert [c["name"] for c in st["clips"]] == ["a_sharp_then_soft.mp4", "b_dark.mp4", "c_normal.mov"]

    data = json.loads(post(base + "/api/segments", {
        "segment": 4, "weights": {"focus": 1, "motion": 0, "exposure": 0}, "max_per_clip": 1})[2])
    assert data["summary"]["selected"] == 3
    kept = [s for s in data["segments"] if s["selected"]]
    assert kept[0]["clip"] == 0 and kept[0]["start"] == 0  # sharp half of clip a
    assert data["timeline"] == [s["id"] for s in kept]

    frames = json.loads(get(base + "/api/frames?clip=0")[2])
    assert len(frames["times"]) == len(frames["focus"]) == 16

    status, headers, jpg = get(base + "/api/thumb?clip=0&t=1")
    assert headers["Content-Type"] == "image/jpeg" and jpg[:2] == b"\xff\xd8"

    status, headers, chunk = get(base + "/api/media?clip=0", {"Range": "bytes=10-19"})
    assert status == 206 and len(chunk) == 10 and headers["Content-Range"].startswith("bytes 10-19/")

    status, headers, body = post(base + "/api/export", {"format": "fcpxml", "segment": 4, "name": "Test cut"})
    assert "selects.fcpxml" in headers["Content-Disposition"]
    root = ET.fromstring(body.split(b"\n", 2)[2])
    assert root.find(".//project").get("name") == "Test cut"
    assert len(root.findall(".//spine/asset-clip")) == 3


def test_errors(server, tmp_path):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        post(base + "/api/analyze", {"folder": str(tmp_path / "missing")})
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/api/thumb?clip=5")
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        post(base + "/api/export", {"format": "mp4"})
    assert e.value.code == 400
