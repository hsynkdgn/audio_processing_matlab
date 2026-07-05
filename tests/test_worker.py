"""Tests for ui.worker — the QThread worker pattern (headless via pytest-qt)."""

from heli_noise.core.exceptions import FilterConfigError
from heli_noise.ui.worker import start_worker


def _add(a: int, b: int) -> int:
    return a + b


def _boom(message: str) -> None:
    raise FilterConfigError(message)


def test_successful_job_emits_finished(qtbot) -> None:
    results: list[int] = []
    thread, worker = start_worker(_add, 2, 3, on_finished=results.append)
    with qtbot.waitSignal(thread.finished, timeout=2000):
        pass
    assert results == [5]


def test_heli_noise_error_emits_failed_with_message(qtbot) -> None:
    errors: list[str] = []
    thread, worker = start_worker(_boom, "notch frequency too high", on_failed=errors.append)
    with qtbot.waitSignal(thread.finished, timeout=2000):
        pass
    assert errors == ["notch frequency too high"]


def test_kwargs_are_forwarded(qtbot) -> None:
    results: list[int] = []
    thread, worker = start_worker(_add, a=10, b=32, on_finished=results.append)
    with qtbot.waitSignal(thread.finished, timeout=2000):
        pass
    assert results == [42]


def test_progress_cb_is_injected_when_job_accepts_it(qtbot) -> None:
    def _job_with_progress(progress_cb) -> str:
        progress_cb(25)
        progress_cb(100)
        return "done"

    progress_values: list[int] = []
    results: list[str] = []
    thread, worker = start_worker(
        _job_with_progress, on_finished=results.append, on_progress=progress_values.append
    )
    with qtbot.waitSignal(thread.finished, timeout=2000):
        pass
    assert results == ["done"]
    assert progress_values == [25, 100]


def test_job_without_progress_cb_parameter_still_works(qtbot) -> None:
    results: list[int] = []
    thread, worker = start_worker(_add, 1, 1, on_finished=results.append)
    with qtbot.waitSignal(thread.finished, timeout=2000):
        pass
    assert results == [2]
