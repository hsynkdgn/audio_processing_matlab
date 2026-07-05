"""QThread worker pattern: run a core function in the background.

Keeps the UI thread responsive during long-running core operations
(ffmpeg conversion, STFT, filtering). Per CLAUDE.md, only the dedicated
HeliNoiseError family is converted into a user-facing failure signal;
any other exception is a programming bug and is left to propagate/crash
normally rather than being silently reported as a user error.
"""

import inspect
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from heli_noise.core.exceptions import HeliNoiseError


class Worker(QObject):
    """Runs a single callable and reports its outcome via signals."""

    progress = Signal(int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, job: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._job = job
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        """Execute the wrapped job, emitting ``finished`` or ``failed``.

        If ``job`` accepts a ``progress_cb`` parameter, it is supplied
        automatically as ``self.progress.emit`` so the job can report
        incremental progress without depending on Qt itself.
        """
        kwargs = dict(self._kwargs)
        if "progress_cb" in inspect.signature(self._job).parameters:
            kwargs.setdefault("progress_cb", self.progress.emit)
        try:
            result = self._job(*self._args, **kwargs)
        except HeliNoiseError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


def start_worker(
    job: Callable[..., Any],
    *args: Any,
    on_finished: Callable[[Any], None] | None = None,
    on_failed: Callable[[str], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
    on_stopped: Callable[[], None] | None = None,
    **kwargs: Any,
) -> tuple[QThread, Worker]:
    """Run ``job(*args, **kwargs)`` on a background QThread.

    Object lifetime is owned by PYTHON, deliberately: there are no
    ``deleteLater`` connections here. Mixing ``deleteLater`` with
    Python-side reference drops gave the same QThread two independent
    destruction paths, and the pending DeferredDelete event could fire
    against an already-collected object (intermittent segfault, caught
    by the test suite). Instead the contract is:

    - The caller MUST keep the returned ``(thread, worker)`` pair alive
      (e.g. as instance attributes) while the thread runs, or the
      garbage collector will destroy a live QThread (hard abort).
    - The caller drops those references from ``on_stopped`` (or later),
      never earlier: ``on_stopped`` fires on ``QThread.finished``, i.e.
      only once the thread has fully stopped, at which point garbage
      collection of both objects is safe and deterministic.

    Args:
        job: The callable to run off the UI thread (typically a
            core.pipeline function).
        *args: Positional arguments forwarded to ``job``.
        on_finished: Connected to the worker's ``finished`` signal.
        on_failed: Connected to the worker's ``failed`` signal.
        on_progress: Connected to the worker's ``progress`` signal.
        on_stopped: Connected to ``QThread.finished`` — the safe point
            to drop references and re-enable UI controls.
        **kwargs: Keyword arguments forwarded to ``job``.

    Returns:
        The ``(thread, worker)`` pair backing this run.
    """
    thread = QThread()
    worker = Worker(job, *args, **kwargs)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    if on_progress is not None:
        worker.progress.connect(on_progress)
    if on_finished is not None:
        worker.finished.connect(on_finished)
    if on_failed is not None:
        worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    if on_stopped is not None:
        thread.finished.connect(on_stopped)

    thread.start()
    return thread, worker
