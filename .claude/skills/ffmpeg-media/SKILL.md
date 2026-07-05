---
name: ffmpeg-media
description: "Use when extracting audio from MP4/MP3, cutting time intervals, or constructing any ffmpeg command."
---

# ffmpeg / media handling rules

## Resolving the binary — imageio-ffmpeg ONLY

```python
import imageio_ffmpeg

ffmpeg_exe: str = imageio_ffmpeg.get_ffmpeg_exe()
```

- NEVER rely on system PATH, NEVER ask the user to install ffmpeg.
- `get_ffmpeg_exe()` returns an absolute path to a bundled binary that
  works on both the Linux sandbox and Windows targets.
- There is no bundled ffprobe: duration/stream info must come from
  parsing `ffmpeg -i <file>` stderr (see below) — do not shell out to
  `ffprobe`.

## Command template (extract + cut in one pass)

```python
cmd = [
    ffmpeg_exe,
    "-hide_banner",
    "-y",                      # overwrite output without prompting
    "-ss", str(start_seconds), # BEFORE -i: fast keyframe seek
    "-to", str(stop_seconds),  # absolute stop time (with -ss before -i,
                               # ffmpeg >= 4 treats -to relative to -ss
                               # output start; verify against duration)
    "-i", str(input_path),     # pathlib.Path -> str at the boundary
    "-vn",                     # drop video
    "-acodec", "pcm_s16le",    # 16-bit PCM
    "-ar", str(sample_rate),   # keep the ORIGINAL rate (probe it first)
    "-ac", "1",                # downmix to mono
    str(output_wav_path),
]
```

### Why -ss placement matters

- `-ss` BEFORE `-i`: input seeking — ffmpeg jumps near the keyframe, fast
  even on multi-GB GoPro MP4s. For audio decoding it is sample-accurate
  enough for this application.
- `-ss` AFTER `-i`: output seeking — decodes and discards everything up
  to the cut point; on a 30-minute MP4 this takes minutes. Do not do it.
- When `-ss` is before `-i`, timestamps are reset to 0 at the seek point;
  be careful combining with `-to` (it then acts like a duration bound).
  If exactness matters, prefer `-ss <start>` before `-i` plus
  `-t <stop-start>` (duration) — unambiguous across ffmpeg versions.

## Subprocess rules (must work on BOTH Linux dev AND Windows target)

```python
import subprocess

result = subprocess.run(
    cmd,                      # list of str — NEVER a joined string
    shell=False,              # NEVER shell=True
    capture_output=True,      # no shell redirection (> /dev/null etc.)
    text=True,
    encoding="utf-8",
    errors="replace",         # ffmpeg stderr may contain non-UTF8 bytes
    check=False,              # inspect returncode ourselves
)
if result.returncode != 0:
    raise MediaDecodeError(result.stderr[-2000:])
```

- `shell=False` + list args: quoting-safe for paths with spaces and
  non-ASCII characters (C:\Users\Hüseyin\Yeni Klasör\uçuş 1.mp4).
- No shell redirection or pipes in commands — they are shell features
  and break with shell=False; use capture_output instead.
- Explicit `encoding="utf-8", errors="replace"`: Windows defaults to a
  legacy code page (cp1252/cp1254) and would otherwise mangle or crash
  on non-ASCII in ffmpeg output.
- Convert `pathlib.Path` to `str` only inside the command list.
- On Windows, later add `creationflags=subprocess.CREATE_NO_WINDOW`
  guarded by `sys.platform == "win32"` so no console flashes; never use
  Linux-only flags (`preexec_fn`, `os.setsid`).

## Parsing duration (no ffprobe available)

Run `[ffmpeg_exe, "-hide_banner", "-i", str(path)]` — it exits non-zero
("At least one output file must be specified") but prints stream info on
STDERR. Parse:

```
Duration: 00:12:34.56, start: 0.000000, bitrate: ...
...
Stream #0:1(und): Audio: aac ..., 48000 Hz, stereo, ...
```

```python
import re

m = re.search(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)", stderr)
if m is None:
    raise MediaDecodeError("Could not parse duration from ffmpeg output")
h, mnt, s, frac = m.groups()
duration = int(h) * 3600 + int(mnt) * 60 + int(s) + float(f"0.{frac}")

sr = re.search(r"Audio:.*?(\d+)\s*Hz", stderr)   # original sample rate
```

- `Duration: N/A` (some streams) → raise `MediaDecodeError`.
- No audio stream in the MP4 → raise `MediaDecodeError` with a clear
  message; do not produce an empty WAV.

## Validation rules

- Validate `0 <= start < stop <= duration` BEFORE running ffmpeg; raise
  `InvalidTimeRangeError` otherwise.
- Output WAV goes into the SOURCE file's folder
  (`input_path.parent / f"{input_path.stem}_filtered.wav"`), built with
  pathlib — never string concatenation with "/" or "\\".
- Long conversions run in a worker thread (see qt-ui-conventions);
  core exposes a plain blocking function, the UI wraps it.
