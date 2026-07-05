# Checkpoints

## Status Summary
- Last update: 2026-07-05
- Active phase: PHASE 3 complete — next up PHASE 4 (integration)
- Known open issues:
  - sounddevice cannot be verified in the sandbox: `import sounddevice`
    raises `OSError: PortAudio library not found` (no audio stack in the
    VM). Playback must be manually tested on Windows (see
    docs/manual_test_windows.md). It stays in requirements.txt for the
    Windows target; sandbox code/tests must never import it at module
    scope outside the playback adapter.
  - build-windows.yml is a skeleton: the PyInstaller spec/options are
    TODOs to be completed in PHASE 5.
  - Sandbox Python is 3.11.15; CI and packaging use 3.12 (the app target).

## Phase List
- [x] PHASE 1: core/ — media handling (ffmpeg wrapper, time cutting, WAV extraction) + tests
- [x] PHASE 2: core/ — DSP (STFT, spectrogram matrix, notch chain, normalize) + tests
- [x] PHASE 3: ui/ — main window, all panels, status icons, worker threads (headless-testable)
- [ ] PHASE 4: integration — end-to-end flow, error scenarios, manual Windows test plan
- [ ] PHASE 5: packaging — build-windows.yml completed, exe artifact verified on Windows 10, README

## Phase Records
(when each phase completes: what was done, which files, test results,
notes for the next session — updating this section is MANDATORY at the
end of every phase)

### PHASE 3 (ui/) — 2026-07-05
- Done: full GUI layer per qt-ui-conventions skill, plus a thin
  core/pipeline.py added as a prerequisite (composes media.py + dsp.py
  into one extract->DC-remove->before-spectrogram->notch->normalize->
  after-spectrogram->save call, fully Qt-independent and tested with the
  MP4 fixture — this is the "orchestrator" flagged as a maybe in the
  PHASE 2 notes; it turned out to need its own tests, so it landed here).
- Files: src/heli_noise/core/pipeline.py (ProcessResult, process_recording),
  src/heli_noise/core/dsp.py gained parse_frequency_list (comma-separated
  notch input parsing, reused by the UI); src/heli_noise/ui/theme.py
  (cockpit palette + QSS), ui/strings.py (all user-facing strings),
  ui/status_icon.py (StatusIcon idle/ok/error), ui/worker.py (Worker +
  start_worker QThread pattern, auto-injects progress_cb into jobs that
  accept it), ui/spectrogram_canvas.py (matplotlib backend_qtagg
  embedding), ui/playback.py (PlaybackAdapter, lazy sounddevice import so
  module import never fails headless; PlaybackError wraps
  PortAudioError/OSError), ui/main_window.py (assembles everything:
  file picker, time/notch inputs, process button, before/after
  spectrogram canvases, play/stop buttons, log panel), src/heli_noise/
  __main__.py (QApplication entry point for `python -m heli_noise`,
  unblocks the build-windows.yml PyInstaller step).
- Test results: 118 passed total (78 from PHASE 1+2 + 40 new), headless,
  ruff clean. MainWindow tests run the REAL pipeline against the
  committed MP4 fixture (not mocked) including a full click-through
  producing an actual output WAV; playback tests prove the app degrades
  gracefully to a red status icon when sounddevice/PortAudio is
  unavailable (the sandbox's actual condition), and mock sounddevice to
  verify PlaybackAdapter's own success/failure logic. Manual sanity check
  via MainWindow with a "Hüseyin Yeni Klasör/uçuş kaydı 1.mp4" path
  (spaces + non-ASCII) confirmed end-to-end.
- Bug caught while wiring the worker (fixed before commit): a test that
  emitted `worker.progress` manually from the test thread raced against
  the job finishing; fixed by having Worker.run() auto-inject
  `progress_cb=self.progress.emit` into jobs whose signature accepts it
  (matching the qt-ui-conventions skill's prescribed pattern), so
  progress is reported synchronously from inside the job itself.
- Notes for next session: PHASE 4 is end-to-end integration (real GoPro-
  shaped scenarios, more error-scenario coverage, docs/manual_test_windows.md
  execution planning) — the pieces are now all wired, so PHASE 4 is mostly
  about breadth of scenario coverage and polish, not new architecture.
  PHASE 5 (packaging) still needs the real PyInstaller spec; __main__.py
  now exists so build-windows.yml's placeholder command should at least
  run (untested here — Windows-only, see docs/manual_test_windows.md).

### PHASE 2 (core DSP) — 2026-07-05
- Done: GUI-independent DSP primitives per dsp-pipeline skill rules.
- Files: src/heli_noise/core/dsp.py (SpectrogramResult, compute_spectrogram,
  apply_notch, apply_notch_chain, remove_dc_offset, normalize_peak),
  tests/test_dsp.py (31 tests).
- Bug caught by tests (fixed before commit): compute_spectrogram crashed on
  signals shorter than nperseg — scipy auto-clamps nperseg to the signal
  length internally but leaves noverlap untouched, tripping scipy's own
  "noverlap must be less than nperseg" error. Fixed by clamping both
  nperseg and noverlap ourselves before calling stft().
- Test results: 78 passed total (47 from PHASE 1 + 31 new), headless,
  ruff clean. Covers: Nyquist rejection (incl. 23 kHz valid @48k / invalid
  @44.1k), zero-phase filtfilt (never lfilter) via a centered-impulse
  test, exact-duplicate dedup, close-frequency overlapping notches,
  short-segment spectrogram, silence (-inf guard), DC offset removal,
  all-zero normalize (no div-by-zero).
- Notes for next session: PHASE 3 (ui/) wires media.py + dsp.py behind
  QThread workers (qt-ui-conventions skill); no orchestrating "run full
  pipeline" function exists yet in core — that composition happens in
  PHASE 3/4 where cut -> load_wav -> remove_dc_offset -> notch chain ->
  normalize_peak -> save_wav is assembled, likely in the UI worker or a
  thin core/pipeline.py if it turns out to need its own tests.

### PHASE 1 (core media handling) — 2026-07-05
- Done: GUI-independent media layer per ffmpeg-media skill rules.
- Files: src/heli_noise/core/exceptions.py (HeliNoiseError + MediaDecodeError,
  InvalidTimeRangeError, FilterConfigError), src/heli_noise/core/timefmt.py
  (parse_time/format_seconds — the single shared hh:mm:ss helper),
  src/heli_noise/core/media.py (MediaInfo, probe_media via ffmpeg -i stderr
  parsing, extract_audio with -ss-before-i + -t, load_wav with stereo
  averaging, save_wav PCM_16), scripts/make_fixtures.py extended with
  tone_440hz_48k.mp4 (AAC) + .mp3 fixtures (both encoders present in the
  imageio-ffmpeg static build), tests/test_media.py + tests/test_timefmt.py.
- Test results: 47 passed (headless), ruff clean. Windows-critical path
  test (spaces + non-ASCII, "Hüseyin Yeni Klasör/uçuş kaydı 1.mp4") passes.
  FFT content check confirms the extracted cut is the 440 Hz tone.
- Notes for next session: PHASE 2 implements core DSP (STFT spectrogram
  matrix, notch chain, normalize) per .claude/skills/dsp-pipeline/SKILL.md;
  reuse load_wav/save_wav and FilterConfigError from this phase. Playback
  adapter stays out of core (PHASE 3/4, mocked in sandbox).

### PHASE 0 (infrastructure) — 2026-07-05
- Done: full project scaffolding on branch
  `claude/heli-noise-analyzer-setup-5de9ic`.
- Files: pyproject.toml, requirements.txt, .gitignore, CLAUDE.md,
  checkpoints.md, src/heli_noise/{,core/,ui/}__init__.py,
  tests/{conftest.py,test_smoke.py}, tests/fixtures/*.wav (generated by
  scripts/make_fixtures.py), .claude/skills/* (3 skills),
  .claude/agents/{dsp-reviewer,test-runner}.md, .claude/settings.json +
  .claude/hooks/*.py (4 hooks), .github/workflows/{ci,build-windows}.yml,
  docs/manual_test_windows.md.
- Test results: see PR description (smoke tests + import verification).
- Notes for next session: read this file first; PHASE 1 implements
  src/heli_noise/core/media.py (ffmpeg wrapper via imageio-ffmpeg) with
  the rules in .claude/skills/ffmpeg-media/SKILL.md. NO application code
  exists yet — only infrastructure.
