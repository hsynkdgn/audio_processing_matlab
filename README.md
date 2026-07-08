# heli-noise-analyzer — Helicopter Noise Analysis System

Windows 10+ desktop application: extract audio from GoPro MP4 (or
MP3/WAV) recordings made inside a helicopter, cut a time interval, run
frequency-spectrum analysis, suppress selected frequencies with band-stop
(notch) filters, preview the result graphically and audibly, and save the
filtered audio as a WAV next to the source file.

**Status:** all 5 phases complete; the Windows exe builds via the
"Build Windows exe" GitHub Actions workflow. See `checkpoints.md` for
the phase-by-phase history and `docs/manual_test_windows.md` for the
checks that require a real Windows machine.

## Usage (once packaged, or via `python -m heli_noise` on Windows)

1. **Browse…** and pick an MP4/MP3/WAV recording.
2. Enter the **start**/**stop** time to cut (`hh:mm:ss` or `mm:ss`,
   optional milliseconds).
3. Enter one or more **notch frequencies** in Hz, comma-separated
   (e.g. `17, 34, 51` for a rotor's fundamental + harmonics).
4. Click **Process** — a progress bar tracks extract → analyze → filter
   → normalize → save; interactive before/after frequency-amplitude
   spectra appear when done, styled after MATLAB's `plot` (white axes,
   MATLAB-blue curve): zoom/pan via the toolbar, hover shows the exact
   Hz/dB under the cursor, **left-click the curve to pin a data tip**
   (right-click clears them), and toggle **minor grid** / **peak markers**
   (auto-detected rotor fundamental/harmonics) per chart.
5. **Play before** / **Play after** to audition the result — drag the
   seek slider to scrub through the audio while it plays; the filtered
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
