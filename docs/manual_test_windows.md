# Manual test plan — Windows 10+ only

These checks CANNOT be performed in the Linux cloud sandbox (no display,
no audio device, no Windows). They must be run by hand on a real
Windows 10 or 11 machine before every release, and after any change to
playback, file dialogs, or packaging.

## Environment
- [ ] Windows 10 (and ideally Windows 11), no Python installed — test the
      packaged exe, not a dev environment.
- [ ] A machine with a default audio output device, and once with NO
      audio device (playback must fail gracefully, not crash).

## Audio playback (sounddevice)
- [ ] Filtered audio plays through the default output device.
- [ ] Play → Stop → Play again works without device errors.
- [ ] Seek slider advances smoothly during playback; dragging it jumps
      the audio to the released position without clicks or crashes
      (OutputStream-based playback was only mock-tested in the sandbox).
- [ ] Seeking to the very end stops playback cleanly.
- [ ] Changing the Windows default device between plays is handled
      (at worst a clear error message, never a crash).
- [ ] Playback of the "before" and "after" audio sounds correct: notched
      frequencies audibly attenuated, no clicks/pops from clipping.
- [ ] No-audio-device machine: playback shows red ✗ + log message.

## File dialogs & paths
- [ ] Open dialog accepts MP4, MP3, WAV filters and remembers the last folder.
- [ ] Paths with spaces AND non-ASCII characters work end-to-end,
      e.g. `C:\Users\Hüseyin\Yeni Klasör\uçuş kaydı 1.mp4`.
- [ ] Files on a different drive (D:\) and on OneDrive-synced folders work.
- [ ] Output WAV is written next to the source file with the expected
      name; a read-only source folder produces a clear error, not a crash.
- [ ] Overwriting an existing output WAV behaves as designed.

## ffmpeg (bundled via imageio-ffmpeg)
- [ ] Audio extraction works on a machine with NO system-installed ffmpeg
      (verify nothing on PATH is used).
- [ ] Real GoPro MP4 (long recording, AAC stereo 48 kHz) extracts and cuts
      correctly; cut boundaries match the requested hh:mm:ss times.
- [ ] A GoPro 360 / multi-channel (ambisonic, e.g. 4.0) recording probes
      and downmixes without error (channel-layout parsing was extended
      for this in PHASE 4; only a plain stereo fixture was testable in
      the sandbox).
- [ ] No console window flashes during conversion.

## Packaged exe (PyInstaller, PHASE 5)
- [ ] Single .exe launches on a clean Windows 10 machine (no Python, no
      VC++ assumptions beyond what Windows ships).
- [ ] First launch is not blocked silently by SmartScreen/AV (document
      the expected SmartScreen prompt for users).
- [ ] Spectrum plots render correctly (matplotlib Qt backend inside the
      frozen app); window scales on 125%/150% display scaling.
- [ ] exe works from a path with spaces and non-ASCII characters.
- [ ] Exit leaves no orphaned ffmpeg/worker processes (check Task Manager).

## UI sanity (visual, not headless-testable)
- [ ] Cockpit theme renders as designed (dark background, amber buttons,
      cyan readouts, green/red status icons) on light AND dark Windows themes.
- [ ] Spectrum charts render in the MATLAB-style light look (white axes,
      MATLAB-blue curve, boxed axes) — a deliberate contrast with the dark
      cockpit theme around them, not a rendering bug.
- [ ] Spectrum toolbar zoom/pan/home works with the mouse; the cursor
      readout under each chart live-updates with "NNN.N Hz, ±N.N dB"
      while hovering and resets when the mouse leaves the plot.
- [ ] Data tips: left-clicking the curve (with no toolbar zoom/pan tool
      active) pins a pale-yellow callout with the exact Hz/dB at the
      nearest point; multiple clicks pin multiple tips; right-click clears
      them all. Clicking while the toolbar's Pan or Zoom tool is active
      does NOT drop a data tip (the tool keeps the click).
- [ ] "Minor grid" checkbox toggles fine gridlines on/off instantly.
- [ ] "Peak markers" checkbox toggles orange triangle markers + Hz labels
      on the spectrum's most prominent peaks; unchecking removes them
      cleanly (no leftover markers/labels).
- [ ] Long operations show progress and the window stays responsive
      (can move/resize during conversion of a large MP4).
- [ ] Progress bar advances visibly (0→100) across the extract/analyze/
      filter/normalize/save stages instead of jumping straight to 100.
- [ ] Closing the window WHILE a conversion is running: the window waits
      briefly and closes cleanly (no crash, no zombie ffmpeg process left
      in Task Manager) — verifies the sandbox-tested close-during-
      processing behavior holds on real Windows threading too.
- [ ] Clicking "Process" again immediately after a run finishes (rapid
      double-click) starts a fresh run cleanly; the button stays disabled
      for the full duration of the previous run, not just until the
      status icon updates (a real race here was found and fixed in the
      sandbox — see checkpoints.md PHASE 4 notes).
- [ ] Processing the same input twice in a row (e.g. different notch
      frequencies) correctly overwrites `<name>_filtered.wav` with the
      new result.

Record results (date, machine, Windows version, pass/fail notes) at the
bottom of this file when a run is completed.

## Test runs
(none yet)
