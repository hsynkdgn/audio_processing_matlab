# heli-noise-analyzer — Helicopter Noise Analysis System

Windows 10+ desktop application: extract audio from GoPro MP4 (or
MP3/WAV) recordings made inside a helicopter, cut a time interval, run
STFT spectrogram analysis, suppress selected frequencies with band-stop
(notch) filters, preview the result graphically and audibly, and save the
filtered audio as a WAV next to the source file.

**Status:** functionally complete (PHASE 1–4): media handling, DSP,
and the desktop UI are implemented and tested end-to-end. PHASE 5
(Windows packaging) is in progress — see `checkpoints.md` for the
phase-by-phase history and `docs/manual_test_windows.md` for the
checks that still require a real Windows machine.

## Usage (once packaged, or via `python -m heli_noise` on Windows)

1. **Browse…** and pick an MP4/MP3/WAV recording.
2. Enter the **start**/**stop** time to cut (`hh:mm:ss` or `mm:ss`,
   optional milliseconds).
3. Enter one or more **notch frequencies** in Hz, comma-separated
   (e.g. `17, 34, 51` for a rotor's fundamental + harmonics).
4. Click **Process** — a progress bar tracks extract → analyze → filter
   → normalize → save; before/after spectrograms appear when done.
5. **Play before** / **Play after** to audition the result; the filtered
   WAV is written next to the source file as `<name>_filtered.wav`.

## Stack
Python 3.12 target · PySide6 · matplotlib · numpy/scipy · soundfile ·
sounddevice · ffmpeg bundled via imageio-ffmpeg (users never install
ffmpeg) · pytest/pytest-qt · ruff · PyInstaller.

## Commands
```
pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -x -q
ruff check --fix . && ruff format .
python -m heli_noise   # Windows only
```

Development happens in a Linux cloud sandbox; the product runs on
Windows. See `CLAUDE.md` for the binding project rules and
`docs/manual_test_windows.md` for Windows-only manual checks.
