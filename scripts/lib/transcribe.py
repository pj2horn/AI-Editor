#!/usr/bin/env python3
"""Transcribe a 16 kHz mono wav to "[m:ss] text" lines.

Tries, in order: mlx-whisper (fastest on Apple Silicon), faster-whisper,
openai-whisper. Prints the backend used on stdout; exits 1 if none work.

Usage: transcribe.py <audio.wav> <out.txt>
Env: WHISPER_MODEL (default "base.en"; try "small.en" for better accuracy)
"""
import os
import sys

MODEL = os.environ.get("WHISPER_MODEL", "base.en")


def stamp(t):
    t = int(t)
    return f"[{t // 60}:{t % 60:02d}]"


def mlx(path):
    import mlx_whisper

    repo = f"mlx-community/whisper-{MODEL}-mlx"
    r = mlx_whisper.transcribe(path, path_or_hf_repo=repo)
    return [(s["start"], s["text"]) for s in r["segments"]]


def faster(path):
    from faster_whisper import WhisperModel

    m = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(path, vad_filter=True)
    return [(s.start, s.text) for s in segs]


def openai(path):
    import whisper

    r = whisper.load_model(MODEL).transcribe(path)
    return [(s["start"], s["text"]) for s in r["segments"]]


def main():
    src, out = sys.argv[1], sys.argv[2]
    for name, fn in (("mlx-whisper", mlx), ("faster-whisper", faster), ("openai-whisper", openai)):
        try:
            segs = fn(src)
        except Exception as e:  # missing package, model download blocked, etc.
            print(f"{name}: {e}", file=sys.stderr)
            continue
        with open(out, "w") as f:
            for start, text in segs:
                text = text.strip()
                if text:
                    f.write(f"{stamp(start)} {text}\n")
        print(f"{name} {MODEL}")
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
