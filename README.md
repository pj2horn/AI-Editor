# AI-Editor

Point it at a folder of footage. It scores every few seconds of every clip for **focus**, **motion** and **exposure**, keeps the best moments, and writes a selects timeline you can open in DaVinci Resolve, Premiere Pro, Final Cut Pro or Avid.

It works like [Cutdown](https://cutdown.app): you can turn an hour of rushes into a stringout of the usable shots without scrubbing through them by hand.

## Install

Requires Python 3.10+ and `ffmpeg`/`ffprobe` on your `PATH`.

```bash
pip install -e .            # or: pip install -e '.[dev]' to run the tests
```

## Use

```bash
# Analyse once (cached in FOLDER/.ai-editor-cache.json)
ai-editor analyze ~/Footage/Shoot01

# Best 4s from each clip -> Resolve / FCP timeline (default output: FOLDER/selects.fcpxml)
ai-editor cut ~/Footage/Shoot01

# Up to 3 x 3s per clip, focus-heavy, capped at 16 minutes, for Premiere and Avid
ai-editor cut ~/Footage/Shoot01 --segment 3s --max-per-clip 3 \
    --weights focus=0.7,motion=0.1,exposure=0.2 --target 16m \
    -o selects.xml -o selects.edl -o selects.csv

# Quick per-clip overview
ai-editor report ~/Footage/Shoot01
```

You can change the segment length, weights, `--max-per-clip`, `--min-score`, `--target` or `--order` and re-run `cut` straight away. Only new or modified files are decoded again.

### Outputs

| Extension | For |
|---|---|
| `.fcpxml` | DaVinci Resolve, Final Cut Pro (FCPXML 1.9) |
| `.xml` | Premiere Pro (FCP7 XML), also Resolve |
| `.edl` | CMX3600 for Avid, Resolve or Premiere; the clip name and scores go in comments |
| `.csv` / `.json` | Scores for every pick |

Embedded source timecode is respected, so the cuts line up with the camera originals.

## How scoring works

1. **Sampling.** ffmpeg decodes each clip at 2 fps (`--sample-fps`), downscaled to 480 px greyscale. Clips are analysed in parallel.
2. **Per-frame metrics**
   - *Focus*: variance of the Laplacian (edge energy), ranked against every frame in the shoot, so "sharp" means sharp relative to the rest of your footage.
   - *Motion*: mean pixel change between samples, ranked the same way.
   - *Exposure*: how close mean luma is to mid-grey, with a penalty for blown highlights and crushed blacks.
3. **Segments.** Each clip is cut into fixed-length segments (`--segment`). Each segment's focus score is its 25th-percentile frame, because a shot is only as usable as its softest moment. Motion and exposure are averaged.
4. **Score** = weighted blend, 0 to 100 (`--weights`, normalised to sum to 1).
5. **Selection.** It takes the top N segments per clip, drops any below `--min-score`, and then keeps the highest scorers until it reaches `--target`.

RAW formats that ffmpeg can't decode (BRAW, R3D, CRM) are skipped. Use proxies for those.

## Tests

```bash
pytest
```
