---
name: token-saver
description: Prep video, audio, and folders of stills locally before looking at them, so you read a one-page summary and at most two images instead of raw frames. Use whenever a task involves a video/audio file (mp4, mov, mxf, braw, wav, m4a...), a folder of frame grabs, reference stills, RAWs or selects, or "watch / look at / review / check this clip".
---

# Token saver

Raw media is the most expensive thing you read. A 1-minute vertical video read
as 1 frame/sec is ~75k tokens and still has no audio. Do the heavy lifting on the
machine first, for free, then read the small result.

## Video or audio file

```bash
prep-video "<file>"            # or scripts/prep-video from this repo
```

It prints the path to `summary.md` (default `./.prep/<name>/`). Then:

1. Read `summary.md` first. It has length, picture format, scene cuts, loudness
   (LUFS / true peak), pauses, word count and pace, the first and last lines,
   on-screen text per frame, and a token estimate.
2. Open `sheet.jpg` (one timestamped frame per scene, plus one every ~5s) only if
   the task needs the picture. Open `hook.jpg` (the first 2 seconds) only for
   questions about the opening or hook.
3. Read `transcript.txt` only if the task needs the actual words. Use `grep` on it
   before reading the whole thing.
4. Need a specific moment? Pull that one frame, don't re-read the video:
   `ffmpeg -ss 0:42 -i "<file>" -frames:v 1 /tmp/f.jpg`

Useful env vars: `SCENE_THRESHOLD=0.2` (more cuts, for fast edits),
`WHISPER_MODEL=small.en` (better transcripts), `NO_TRANSCRIPT=1`, `NO_OCR=1`.

## Folder of stills / frame grabs / RAWs

```bash
prep-images "<folder>"         # or: prep-images a.jpg b.png ... -o out_dir
```

Read `summary.md` (one row per file: dimensions, size) and `sheet-1.jpg`
(numbered tiles that match the table). There's a `sheet-2.jpg` only if there are
more than 20 images. Open a full-res original only when the task needs detail
from that one file.

## macOS extras (Apple Vision, free and built in)

```bash
swift mac/vision.swift ocr    <image>                   # read on-screen text / captions / slates
swift mac/vision.swift faces  <image>                   # face count + boxes (framing checks)
swift mac/vision.swift cutout <image> out.png [--green] # person cutout, no green screen needed
mdfind -name "<name>" -onlyin ~/Movies                  # find files via Spotlight instead of `find` over a whole drive
sips -g pixelWidth -g pixelHeight <image>               # image details without opening the image
```

## Rules

- Premiere: only Adobe Premiere Pro 2026, never anything named "Beta" (another session uses it). Never quit a running Premiere.

- Never Read a raw video/audio file. The guard hook blocks it and tells you which command to run.
- Don't open full-res images just to check size, format, or count. Use the summary table or `sips`.
- Quote the summary's token estimate when you report back, so the saving is visible.
