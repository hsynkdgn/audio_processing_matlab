# Checkpoints

## Status Summary
- Last update: 2026-07-05
- Active phase: ALL 5 PHASES COMPLETE from the cloud-sandbox side. The
  one remaining item in the entire project is Windows-only and cannot
  be done from this environment by design: running docs/manual_test_windows.md
  on a real Windows 10/11 machine (playback, file dialogs, the packaged
  exe itself). Everything else — core, DSP, UI, integration, and the
  packaging pipeline — is implemented, tested, and committed.
- Known open issues:
  - sounddevice cannot be verified in the sandbox: `import sounddevice`
    raises `OSError: PortAudio library not found` (no audio stack in the
    VM). Playback must be manually tested on Windows (see
    docs/manual_test_windows.md). It stays in requirements.txt for the
    Windows target; sandbox code/tests must never import it at module
    scope outside the playback adapter.
  - The packaged .exe itself is UNVERIFIED on real Windows — the sandbox
    can only sanity-build the PyInstaller spec into a throwaway Linux
    ELF (proves Analysis/hidden-imports/data-collection all resolve; see
    PHASE 5 record). The actual build-windows.yml run on windows-latest
    has not been observed by this session. First person to run it should
    download the artifact and work through docs/manual_test_windows.md.
  - Sandbox Python is 3.11.15; CI and packaging use 3.12 (the app target).

## Phase List
- [x] PHASE 1: core/ — media handling (ffmpeg wrapper, time cutting, WAV extraction) + tests
- [x] PHASE 2: core/ — DSP (STFT, spectrogram matrix, notch chain, normalize) + tests
- [x] PHASE 3: ui/ — main window, all panels, status icons, worker threads (headless-testable)
- [x] PHASE 4: integration — end-to-end flow, error scenarios, manual Windows test plan
- [x] PHASE 5: packaging — build-windows.yml completed, README (exe artifact verification on
      real Windows 10 is the one item no cloud session can perform — see Known open issues)

## Phase Records
(when each phase completes: what was done, which files, test results,
notes for the next session — updating this section is MANDATORY at the
end of every phase)

### UI revamp: spectrum view + playback seeking — 2026-07-07
- User feedback after running the packaged exe on real Windows: the
  time-frequency spectrograms weren't the desired view. Requested (and
  built): frequency-vs-amplitude plots (no time axis) for before/after,
  interactive charts, and a draggable seek control during playback
  (user chose a plain slider over a waveform view when asked).
- core: dsp.py gained SpectrumResult + compute_spectrum() (Welch, hann,
  same nperseg/noverlap defaults and short-signal clamping as the STFT
  path; power -> dB with epsilon). pipeline.ProcessResult now carries
  before_spectrum/after_spectrum; spectrogram computation removed from
  the pipeline (compute_spectrogram itself stays in core, still tested,
  per the DSP rules — just no longer displayed).
- ui: new spectrum_canvas.py (SpectrumCanvas line plot + SpectrumPanel
  wrapping it with a matplotlib NavigationToolbar2QT for zoom/pan/reset
  and a live cursor readout "NNN.N Hz, ±N.N dB"); old
  spectrogram_canvas.py deleted. playback.py rewritten from fire-and-
  forget sd.play to sd.OutputStream + pull callback: position_seconds/
  duration_seconds properties, seek(seconds) (live while playing),
  start-offset play, auto-finish at end of signal; still lazily imports
  sounddevice so the module always imports headlessly. main_window.py:
  QSlider + position/duration label next to the playback buttons,
  100 ms QTimer syncing them while playing; drag updates the label,
  release seeks; slider disabled until a result exists.
- Tests: 166 passed (playback adapter mock suite rewritten around a
  fake OutputStream whose callback tests pump manually — 13 tests;
  7 new compute_spectrum tests incl. notch-dip verification; 7 spectrum
  panel tests; 5 seek-slider tests). ruff + format clean.
- Note for Windows testing: OutputStream playback and seeking were only
  mock-tested here — docs/manual_test_windows.md gained seek-slider
  checks; a fresh exe build is needed to see any of this.

### Project-wide review round 2 — 2026-07-05
- A full-project review after PHASE 5 found one serious leftover bug,
  one latent crash, and a set of smaller gaps; all fixed:
  1. **Failure-path button race (real bug)**: the PHASE 4 fix moved
     control re-enabling to `QThread.finished` — but only on the success
     path; `_on_process_failed` still re-enabled the button early,
     leaving the exact same GC-destroys-live-QThread race open on every
     failed run. Both paths now re-enable ONLY from `_on_thread_stopped`.
  2. **deleteLater vs Python GC double-destruction (latent, intermittent
     segfault)**: `start_worker` connected `thread.finished` to
     `worker.deleteLater`/`thread.deleteLater` while MainWindow also
     dropped its Python references on the same signal — two independent
     destruction paths for the same C++ objects; a pending DeferredDelete
     could fire against an already-collected object. Reproduced as a
     ~1-in-5 segfault by the new failure-path test. Fixed by removing the
     deleteLater connections entirely: lifetime is now owned solely by
     Python, and `start_worker` gained an `on_stopped` callback
     (connected to `QThread.finished`) as the sanctioned point to drop
     references. Verified with 12 consecutive crash-free runs of the
     previously-crashing file + 4 full-suite runs.
  3. CI now also runs `ruff format --check` (format drift could
     previously pass CI).
  4. File dialog now remembers the last-used directory
     (docs/manual_test_windows.md promised this; the code never did it).
  5. Play/Stop playback buttons are disabled until a result exists and
     during processing; stale play status icons reset on each new run.
  6. tests/test_smoke.py now validates the full committed fixture set
     (stereo WAV/MP4 + MP3 had drifted out of it).
  7. .claude/hooks/post_tool_use_ruff.py runs `--unfixable F401`:
     auto-removal of "unused" imports kept racing multi-edit changes
     (import added in one edit, usage in the next) — 4 incidents this
     session. F401 is still REPORTED by the hook and still fails CI.
  8. Cosmetics: hover color literal → theme.PRIMARY_HOVER; QThread
     imported from PySide6.QtCore directly; closeEvent typed (QCloseEvent).
- Test results: 143 passed (4 new tests), ruff + format clean.

### PHASE 5 (packaging) — 2026-07-05
- Done: replaced the ad-hoc inline pyinstaller command with a committed
  `heli_noise.spec` (entry point src/heli_noise/__main__.py; bundles the
  imageio-ffmpeg binary via `collect_data_files("imageio_ffmpeg")`;
  `matplotlib.backends.backend_qtagg` hidden import since matplotlib
  picks its Qt backend dynamically; single-file, windowed, named
  "HeliNoiseAnalyzer"). `.github/workflows/build-windows.yml` now just
  runs `pyinstaller --clean --noconfirm heli_noise.spec`; the stale
  TODO comments describing options the spec now already implements were
  removed (an icon/version-resource TODO remains — cosmetic, not
  blocking a working build).
- Sandbox sanity check (pyinstaller installed ad hoc for this, NOT added
  to requirements.txt — matches the existing convention of installing it
  separately in the workflow): built the spec in the Linux sandbox. This
  produces a throwaway Linux ELF, not a usable artifact, but it proves
  the spec itself is correct — Analysis resolved all imports, the
  ffmpeg binary was actually embedded (confirmed via `strings` on the
  output binary: `imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-...`
  present), and the built executable launched cleanly under
  `QT_QPA_PLATFORM=offscreen` for 5s with no traceback before being
  killed by the test harness. Build artifacts (build/, dist/) were
  deleted after the check; both are already gitignored.
- Test results: 139 passed headless, ruff clean (unchanged from PHASE 4
  — this phase touched no application code, only packaging config).
- Notes for next session / whoever has Windows access: this is the
  LAST remaining task in the entire project. Trigger build-windows.yml
  (workflow_dispatch or push a `v*` tag), download the
  HeliNoiseAnalyzer-windows artifact, and work through EVERY checkbox in
  docs/manual_test_windows.md. If the exe fails to launch or ffmpeg
  can't be found at runtime, the first things to check are: (1) whether
  imageio_ffmpeg's Windows wheel actually bundled a Windows ffmpeg.exe
  binary at spec-build time (rerun `pip show -f imageio-ffmpeg` on the
  Windows runner to confirm), and (2) PySide6 platform plugin bundling
  (PyInstaller has a built-in PySide6 hook, but if the window fails to
  show, try `--debug=imports` for a first diagnosis).

### PHASE 4 (integration) — 2026-07-05
- Done: broader end-to-end scenario coverage through the real MainWindow
  (never mocked below the sounddevice boundary), plus a stereo GoPro-
  shaped fixture.
- Files: scripts/make_fixtures.py gained `stereo_tone_440hz_48k.{wav,mp4}`
  (L=0.8·sin(440), R=0.4·sin(440) — makes the channel-averaging downmix
  independently verifiable); tests/test_integration.py (6 tests): stereo
  downmix end-to-end, concurrent-click guard, output-overwrite, a
  realistic multi-frequency rotor-harmonic notch chain via the UI text
  field, and two time-range boundary cases.
- **Real bug found and fixed**: writing the "processing twice in a row"
  test exposed a genuine race in MainWindow. The Process button was
  re-enabled in `_on_process_finished`/`_on_process_failed` (on the
  worker's `finished`/`failed` signal), but the QThread itself only
  fully stops later, on `QThread.finished`. A user (or this test)
  clicking Process again inside that gap creates a second QThread while
  `self._thread` still pointed at the first, not-yet-stopped one; the
  first thread's late `finished` signal then fired `_on_thread_stopped`,
  which nulled `self._thread`/`self._worker` out from under the *second*,
  still-running thread — dropping its last Python reference and letting
  the GC destroy a live QThread (hard abort, reproduced in the sandbox).
  Fixed by moving `_set_controls_enabled(True)` into `_on_thread_stopped`
  itself, so the button now stays disabled for the QThread's entire
  lifetime, not just until the worker signals completion — this makes
  the overlap structurally impossible rather than papering over it.
  `tests/test_main_window.py`'s end-to-end test was updated to check
  `isEnabled()` only after `_thread is None`, matching the real invariant.
- Also discovered (not a bug, a design boundary worth recording): the
  time-input field only keeps 3 fractional digits (`core/timefmt.parse_time`),
  so the finest cut a user can type is 1 ms — 48 samples at 48 kHz, always
  comfortably above `filtfilt`'s ~9-sample padlen for a biquad notch.
  The "signal too short to filter" `InvalidTimeRangeError` path is real
  and unit-tested (`test_dsp.py`), but is unreachable through the UI's
  own precision; `test_integration.py` asserts the smallest expressible
  cut succeeds instead of asserting an unreachable error.
- Docs: docs/manual_test_windows.md gained checks for the progress bar,
  safe close-during-processing, rapid double-click, output overwrite,
  and multi-channel/ambisonic GoPro 360 sources. README.md rewritten
  from "infrastructure only" to describe actual usage.
- Test results: 139 passed headless (repeated 3x with no flakiness),
  ruff clean.
- Notes for next session: PHASE 5 is packaging — the PyInstaller spec is
  still a TODO in build-windows.yml.

### PHASE 3 review fixes — 2026-07-05
- A post-PHASE-3 code review produced 4 findings; all fixed same-day:
  1. media.py audio-stream regex now tolerates surround/ambisonic channel
     layouts ("5.1(side)", "quad", "4.0", "7.1"); parsing extracted into
     pure `_parse_audio_stream()` unit-tested against real ffmpeg stderr
     samples. Unknown layouts fall back to 2 channels instead of
     rejecting the file (count is informational; extraction downmixes).
  2. MainWindow.closeEvent now quits+waits the worker thread and stops
     playback, so closing mid-processing no longer risks destroying a
     live QThread.
  3. process_recording gained progress_cb (0→100 stage reporting); the
     UI shows it in a QProgressBar (worker auto-injects the signal).
  4. PlaybackAdapter.play clips input to [-1, 1] (the un-normalized
     "before" signal can slightly exceed the range after DC removal).
- Crash caught while implementing fix 2: dropping the thread/worker
  Python references from the worker's `finished` handler let the GC
  destroy a still-running QThread → hard abort. References are now
  dropped from `QThread.finished` (thread fully stopped) instead —
  pattern to keep for any future worker wiring.
- Test results after fixes: 133 passed headless, ruff clean.

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
