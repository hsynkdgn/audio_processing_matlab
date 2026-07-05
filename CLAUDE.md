# heli-noise-analyzer — Helicopter Noise Analysis System

Windows 10+ desktop application: spectrogram analysis and band-stop
filtering of helicopter audio recordings (MP4/MP3/WAV).
Development happens in a Linux cloud sandbox; the product runs on Windows.

## Architecture rules
- The core/ layer is COMPLETELY GUI-independent: no core module may import
  PySide6. All DSP/ffmpeg functions are pure Python, testable in isolation.
- The ui/ layer calls core; core never calls ui.
- Long-running operations (ffmpeg conversion, STFT, filtering) run in the
  background via QThread/QRunnable; the UI thread is NEVER blocked.
- All file paths use pathlib.Path. Code must be cross-platform but is
  PRIMARILY targeting Windows: paths with spaces and non-ASCII characters
  (e.g. C:\Users\Hüseyin\...) must always work; never hardcode "/" joins,
  never use Linux-only subprocess behavior.
- The ffmpeg binary is resolved via imageio-ffmpeg; never rely on system PATH.

## Cloud-sandbox rules
- All Qt tests run headless: set QT_QPA_PLATFORM=offscreen in test config.
- sounddevice playback cannot be verified in the sandbox: isolate playback
  behind a thin adapter (core-independent), unit-test the adapter's logic
  with a mock, and list real-audio checks in docs/manual_test_windows.md.
- Anything a future session needs must be committed — the VM is ephemeral.

## DSP rules
- Spectrogram: scipy.signal.stft, window=hann, nperseg=2048, noverlap=1536
  (defaults; must be configurable).
- Band-stop: scipy.signal.iirnotch(f0, Q) per frequency, applied with
  scipy.signal.filtfilt (zero phase). If an input frequency is >= Nyquist,
  raise an ERROR — never silently clamp.
- After filtering, peak-normalize output to [-1, 1] (clipping prevention).
- Stereo input is downmixed to mono by channel averaging; output WAV is
  mono, 16-bit PCM, at the original sample rate.

## Code standards
- All user-facing UI strings live in src/heli_noise/ui/strings.py;
  hardcoded UI strings in widget code are forbidden.
- Docstrings and type hints are mandatory for every core function.
- Error handling: core raises dedicated exception classes
  (MediaDecodeError, InvalidTimeRangeError, FilterConfigError, etc.);
  ui catches them and converts them into status icons (✓/✗) and
  log-panel messages.

## Git workflow (cloud)
- Each session works on its own branch and ends with a pushed branch + PR.
- Conventional commit messages: feat:, fix:, test:, docs:, chore:.
- Never merge to main yourself; the user reviews and merges PRs.
- Never force-push; never rewrite published history.

## Commands
- Install: pip install -r requirements.txt
- Test: QT_QPA_PLATFORM=offscreen python -m pytest tests/ -x -q
- Lint+format: ruff check --fix . && ruff format .
- Run (Windows only): python -m heli_noise
- Package: GitHub Actions workflow "build-windows.yml" (windows-latest)

## Session discipline
- Update checkpoints.md whenever a major work block completes.
- The first action in every new session is reading checkpoints.md.

## Forbidden
- Files under tests/fixtures/ are never edited by hand; they are generated
  by scripts/make_fixtures.py and committed.
- No new dependency in requirements.txt without asking the user first.

## Findings (append-only)
- 2026-07-05 (infrastructure session): sandbox Python is 3.11.15 — inside
  the supported range, but the app targets 3.12; CI and packaging pin 3.12.
- 2026-07-05: the git remote started completely empty; `main` was seeded
  with a stub README so PRs have a base branch.
