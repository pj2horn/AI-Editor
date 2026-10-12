# Token-saver setup prompts

## The original (from the reel, transcribed off the screen)

> Build me a token-saver mod for Claude Code. Start by auditing my setup for token efficiency.
>
> 1. Look through my recent sessions and list the 5 tasks where you spend the most tokens. For each, tell me what you were reading (images, video frames, long files, transcripts, web pages) and roughly how many tokens it costs each time.
> 2. For each one, tell me whether my Mac could do the heavy lifting locally, for free, before you ever read it. Check what's built in first: Apple's Vision framework (text recognition, face detection, person cutouts) through a small Swift script, Spotlight (mdfind) for finding files, and sips for image details. Then free local tools: ffmpeg for one contact sheet instead of separate frames, Whisper for transcripts, and simple scripts that summarize long files.
> 3. For the top two, build a local prep step that saves a one-page summary and at most two images, so you read that instead of the raw files.
>
> Show me a before-and-after token estimate for each, and wait for my OK before installing anything.

## Adapted for Two Horn (paste into Claude Code on the Mac, from `~/AI-Editor`)

This version starts from the tools already in this repo instead of building from
scratch, and points the audit at editing work.

> I edit in Premiere Pro and DaVinci Resolve. Footage lives on external drives (`/Volumes/...`) and in `~/Movies`. This repo (`~/AI-Editor`) already has a token-saver: `scripts/prep-video`, `scripts/prep-images`, `mac/vision.swift`, a guard hook, and the `token-saver` skill. Read the README first.
>
> 1. **Audit.** Look through my recent Claude Code sessions (`~/.claude/projects/*/*.jsonl`) and list the 5 tasks where you spent the most tokens. For each: what you were reading (video frames, frame grabs, RAW stills, interview transcripts, Premiere/Resolve project or XML/EDL exports, LUT/DCTL files, client briefs, web pages) and roughly how many tokens it cost each time. Show the numbers as a table.
> 2. **Local first.** For each one, say whether this Mac could do the heavy lifting before you read it. Check built-ins first: Apple Vision via `mac/vision.swift` (slates, burned-in captions, lower thirds, faces for framing checks, person cutouts), Spotlight (`mdfind`) instead of `find` across whole drives, `sips` for image details, and `mdls` for clip metadata. Then free tools: ffmpeg contact sheets, `mlx-whisper` for transcripts, and short scripts that summarize long files (for example, an XML/EDL summarizer that lists sequences, track counts, clip names, durations, and markers instead of you reading the raw XML).
> 3. **Build.** For the top two that `prep-video` / `prep-images` *don't* already cover, add a prep step in `scripts/` that writes a one-page `summary.md` and at most two images. Follow the existing scripts' style (bash 3.2-safe, ffmpeg-only where possible) and add it to the `token-saver` skill.
> 4. **Verify.** Compile `mac/vision.swift` (`swiftc -O mac/vision.swift -o ~/bin/vision`) and fix it if it doesn't build. It was written without a Mac. Run `prep-video` on a real interview clip and `prep-images` on a folder of RAWs, and check that the transcript and OCR sections fill in.
>
> Show me a before-and-after token estimate for each, and wait for my OK before installing anything or editing `~/.claude/settings.json`.
