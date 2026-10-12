# AI-Editor — token saver for Claude Code

Do the heavy lifting on your own machine, for free, before Claude reads anything.
A video becomes a one-page `summary.md` + two images, and a folder of stills
becomes one or two numbered contact sheets.

| Input | Raw (1 frame/sec) | After prep |
|---|---|---|
| 71s vertical reel, 720×1280 | ~88,000 tokens | ~2,100 tokens |
| 20s 1080p clip | ~30,700 tokens | ~1,100 tokens |
| 24 frame grabs | 24 images | 2 sheets |

## What's here

| Path | What it does |
|---|---|
| `scripts/prep-video` | Video or audio → `summary.md` (length, format, scene cuts, LUFS/true peak, pauses, words/min, first and last line, on-screen text, token estimate), `sheet.jpg` (timestamped frame per scene + every ~5s), `hook.jpg` (first 2s), `transcript.txt` |
| `scripts/prep-images` | Folder/files of stills (incl. RAW/HEIC on macOS via `sips`) → `summary.md` table + numbered `sheet-1.jpg` [`sheet-2.jpg`] |
| `scripts/lib/transcribe.py` | Whisper wrapper: tries mlx-whisper → faster-whisper → openai-whisper |
| `mac/vision.swift` | Apple Vision from the command line: `ocr`, `faces`, `cutout [--green]` |
| `scripts/hooks/guard-media.sh` | PreToolUse hook: blocks Claude from reading raw video/audio and tells it to prep instead |
| `.claude/skills/token-saver/` | Skill that tells Claude when and how to use all of the above |
| `install.sh` | Links everything for use in every project (asks before each step) |
| `docs/setup-prompt.md` | The prompt from the reel, plus a version adapted for Premiere/Resolve work |
| `docs/reel-breakdown.md` | Breakdown of the reel that inspired this |

## Setup (Mac)

```bash
brew install ffmpeg
pip3 install mlx-whisper        # Apple Silicon (Intel: pip3 install faster-whisper)
./install.sh                    # asks before each step
```

The first transcript downloads the Whisper model (`base.en` by default; set
`WHISPER_MODEL=small.en` for better accuracy).

Inside this repo the skill and hook work with no install, via `.claude/`.

## Use

```bash
prep-video clip.mov                 # -> ./.prep/clip/summary.md
prep-video vo.wav                   # audio-only works too
prep-images ~/Desktop/selects       # -> ./.prep/selects/summary.md
SCENE_THRESHOLD=0.2 prep-video fast-cut.mp4   # catch more cuts
```

Turn off the guard hook for a session with `TOKEN_SAVER_OFF=1`.

## Status

- `prep-video` and `prep-images` were tested on Linux: vertical, horizontal and audio-only
  input, and runs through a symlink. They're written for macOS's bash 3.2 but haven't
  been run on a Mac yet.
- Transcripts: the code path is in place, but it's untested end to end. The cloud
  sandbox couldn't download a Whisper model.
- `mac/vision.swift` was written without a Mac or Swift toolchain, so it hasn't been
  compiled. `install.sh` step 3 will show any build errors.
