# heli-noise-analyzer — Helicopter Noise Analysis System

Windows 10+ desktop application: extract audio from GoPro MP4 (or
MP3/WAV) recordings made inside a helicopter, cut a time interval, run
STFT spectrogram analysis, suppress selected frequencies with band-stop
(notch) filters, preview the result graphically and audibly, and save the
filtered audio as a WAV next to the source file.

**Status:** infrastructure only — application code lands in PHASE 1+
(see `checkpoints.md`).

## Stack
Python 3.12 target · PySide6 · matplotlib · numpy/scipy · soundfile ·
sounddevice · ffmpeg bundled via imageio-ffmpeg (users never install
ffmpeg) · pytest/pytest-qt · ruff · PyInstaller.

## Commands
```
pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -x -q
ruff check --fix . && ruff format .
```

Development happens in a Linux cloud sandbox; the product runs on
Windows. See `CLAUDE.md` for the binding project rules and
`docs/manual_test_windows.md` for Windows-only manual checks.
