---
name: qt-ui-conventions
description: "Use when writing or modifying PySide6 interface code."
---

# PySide6 UI conventions

## Cockpit theme palette

Dark "cockpit instrument" look. Central constants (e.g. `ui/theme.py`):

| Role                | Hex       | Usage                                   |
|---------------------|-----------|-----------------------------------------|
| Background          | `#0d1117` | dark anthracite window/panel background |
| Primary button      | `#ffb020` | amber — main action buttons             |
| Readout / values    | `#29d6e8` | cyan — numeric readouts, time displays  |
| Status OK           | `#35d07f` | green ✓ status icons                    |
| Status error        | `#ff4d4d` | red ✗ status icons                      |

- Apply via one central QSS stylesheet; never scatter per-widget
  `setStyleSheet` color literals.
- All user-facing strings come from `src/heli_noise/ui/strings.py` —
  hardcoded strings in widget code are forbidden (CLAUDE.md rule).

## QThread worker pattern (UI thread is NEVER blocked)

```python
from PySide6.QtCore import QObject, QThread, Signal

class Worker(QObject):
    progress = Signal(int)          # 0-100
    finished = Signal(object)       # result payload
    failed = Signal(str)            # user-readable error text

    def __init__(self, job, *args):
        super().__init__()
        self._job, self._args = job, args

    def run(self) -> None:
        try:
            result = self._job(*self._args, progress_cb=self.progress.emit)
            self.finished.emit(result)
        except HeliNoiseError as exc:        # dedicated core exceptions
            self.failed.emit(str(exc))

# in the window:
self._thread = QThread(self)
self._worker = Worker(core_fn, arg1)
self._worker.moveToThread(self._thread)
self._thread.started.connect(self._worker.run)
self._worker.finished.connect(self._thread.quit)
self._worker.failed.connect(self._thread.quit)
```

- Keep references (`self._thread`, `self._worker`) or Python GC kills
  the thread mid-run.
- Workers call CORE functions only; core never imports Qt.
- Widgets are updated only from signals on the UI thread — never touch
  widgets from the worker.
- Disable the triggering button while a worker runs; re-enable in both
  finished and failed handlers.

## Status-icon component (idle / ✓ / ✗)

One small reusable widget (e.g. `StatusIcon(QLabel)`) with three states:

- `idle`: neutral dot/dash, muted gray
- `ok`: ✓ in `#35d07f`
- `error`: ✗ in `#ff4d4d` (tooltip carries the error message)

The UI maps core exceptions → `error` + log-panel entry; successful step
→ `ok`. No exception text in popups; the log panel is the detail view.

## Matplotlib embedding (spectrogram)

```python
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class SpectrogramCanvas(FigureCanvasQTAgg):
    def __init__(self) -> None:
        fig = Figure(facecolor="#0d1117")
        self._ax = fig.add_subplot(111)
        super().__init__(fig)

    def show_spectrogram(self, f, t, mag_db) -> None:
        self._ax.clear()
        mesh = self._ax.pcolormesh(t, f, mag_db, shading="auto")
        self.draw_idle()
```

- Use the `backend_qtagg` backend (works with PySide6); never call
  `matplotlib.pyplot` in app code — it spins up its own figure manager.
- Redraw with `draw_idle()`, not `draw()`, from signal handlers.
- Heavy computation (STFT) happens in the worker; the canvas only renders
  ready-made matrices.

## Time input validation (hh:mm:ss)

```python
import re

TIME_RE = re.compile(r"^(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?:\.(\d{1,3}))?$")
# accepts mm:ss, hh:mm:ss, optional .millis — reject anything else
```

- Validate on editing-finished AND before starting the job; invalid input
  → red ✗ status + log message, never a crash.
- Convert to float seconds in ONE helper shared by UI and tests.

## Headless testing rule

- Every UI test must run without a display:
  `QT_QPA_PLATFORM=offscreen` (enforced in tests/conftest.py).
- Use pytest-qt's `qtbot` for widget tests; never `app.exec()` in tests.
- sounddevice playback is NOT testable in the sandbox — playback lives
  behind a thin adapter, tests mock it, and real checks are listed in
  docs/manual_test_windows.md.
