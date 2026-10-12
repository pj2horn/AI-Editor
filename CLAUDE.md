# AI-Editor

## Adobe Premiere: use 2026, never the Beta

Another Claude session works in the Premiere **Beta**. To avoid conflicts:

- Only ever open, script, or read prefs/plugins/presets for **Adobe Premiere Pro 2026**
  (`/Applications/Adobe Premiere Pro 2026/`). Confirm the real path first with
  `mdfind "kMDItemCFBundleIdentifier == 'com.adobe.PremierePro*'"` or `ls /Applications | grep -i premiere`.
- Never launch, quit, script, or change settings for anything with **"Beta"** in its name
  (e.g. `Adobe Premiere Pro (Beta)`), including its folders under
  `~/Library/Application Support/Adobe/` and `~/Documents/Adobe/`.
- Never quit or force-quit any running Premiere. The Beta may be in use.
- If a task is ambiguous about which Premiere, stop and ask.

The prep scripts here (`scripts/prep-*`) never touch Premiere. They only read media with ffmpeg.
