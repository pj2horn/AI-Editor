# Breakdown: "How I saved 94% in token usage"

Instagram reel, 1:11, 720×1280 @ 24fps. I analyzed it with this repo's own
`prep-video` (one contact sheet + hook frames, ~2k tokens instead of ~88k) plus
OCR on the frames. The voiceover isn't transcribed because Whisper models
couldn't be downloaded in the cloud sandbox, so the script below is reconstructed
from on-screen headings and burned-in caption words.

## The numbers

| | |
|---|---|
| Length | 1:11 |
| Hard cuts | 2 (0:36, 1:08). It's essentially one handheld take |
| Loudness | −14.1 LUFS integrated (right at Instagram/TikTok normalization), −0.8 dBTP peak (a little hot; −1 dBTP is the safe ceiling) |
| Pauses | none over 0.6s. Music bed under a VO that never stops |

## How it's built

**Production is close to free.** A phone pointed at a monitor, slightly tilted,
with a webcam and a fidget spinner in frame for "real desk" texture. All the
"editing" is a long scrolling web page that Claude built. The creator scrolls it
on camera, so each section heading does the job of a title card. The only
post-production is the captions and two cuts.

**Captions:** one word at a time, white serif, centered in the middle third.
They sit over the busy screen and stay legible because of the font weight and
the dark UI behind them.

## Structure (reconstructed)

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:20 | **Hook + problem.** Overlay text: "How I saved 94% in token usage." | A wall of blue thumbnail tiles: "40 seconds of video, one frame a second: 40 images." The cost made visual |
| 0:20–0:27 | Text recognition | OCR pulling "Claude Mods blowing my mind" off a frame |
| 0:27–0:33 | Face detection | A box on the creator's face |
| 0:33–0:36 | "Green screen, no green screen" | original → mask → green comp, "4.2s · Apple Vision" |
| 0:36–0:44 | Spotlight, Transcript | `mdfind` finding a file; Whisper word-level timings |
| 0:44–0:49 | Contact sheet | one image replacing the wall of frames |
| 0:49–0:55 | **Payoff: "What Claude reads"** | the one-page summary: 1:54, 9 scenes, −14.1 LUFS, 383 words (202/min), first and last line, `sheet.jpg`, `hook.jpg` |
| 0:55–1:08 | **"The difference"** | bar chart: ~50,000 tokens vs ~3,000 (that's the 94%) |
| 1:08–1:11 | **Save-bait** | the full prompt on screen, readable if paused |

## Why it works

1. **The hook is a number plus a visual.** "94%" is concrete, and the wall of tiles
   shows the waste before anything is explained.
2. **Each tool gets ~5 seconds and a real output**, not a description. The viewer
   sees OCR, a face box and a cutout actually work.
3. **The payoff is a before/after metric** with a chart. It pays off the hook's
   number exactly.
4. **The prompt at the end drives saves and shares.** You can't copy it at full
   speed, so people save the reel or screenshot it.
5. **It's self-referential.** The summary on screen describes a video Claude edited
   (last line: "Claude edited this entire video."), which sets up the next post.

## Ideas for Two Horn using this repo

- **"I made Claude watch a 40-minute interview for 3,000 tokens."** Run `prep-video`
  on a real interview and show the summary, sheet, and transcript grep that found
  the soundbite. Same before/after bar.
- **"My AI assistant can't see RAW, so I built it eyes."** `prep-images` on a shoot's
  selects: 300 RAWs become 2 numbered sheets, and Claude picks the hero frames by number.
- **Format to copy:** a scrolling HTML explainer filmed off the monitor, with
  one-word captions and the prompt on screen at the end. Claude can build the
  explainer page as an artifact. Keep the true peak at −1 dBTP.
