"""Tests for ui.main_window.MainWindow (headless via pytest-qt).

Runs the real pipeline against the committed MP4 fixture — fast enough
(sub-second clips) to exercise end-to-end in CI without mocking core.
"""

import shutil
from pathlib import Path

from heli_noise.ui.main_window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
TONE_MP4 = FIXTURES / "tone_440hz_48k.mp4"


class TestInitialState:
    def test_window_title(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.windowTitle() == "Helicopter Noise Analyzer"

    def test_process_status_starts_idle(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._process_status.text() == "○"


class TestProcessValidation:
    def test_process_without_input_file_shows_error(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window._on_process_clicked()
        assert window._process_status.text() == "✗"
        assert "recording file" in window._log_edit.toPlainText().lower()

    def test_process_with_invalid_time_shows_error(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("not-a-time")
        window._stop_edit.setText("00:01")

        window._on_process_clicked()

        assert window._process_status.text() == "✗"
        assert "invalid time" in window._log_edit.toPlainText().lower()

    def test_process_with_invalid_notch_frequency_shows_error(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._notch_edit.setText("abc")

        window._on_process_clicked()

        assert window._process_status.text() == "✗"
        assert "notch" in window._log_edit.toPlainText().lower()


class TestProcessEndToEnd:
    def test_successful_run_updates_status_and_spectrograms(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00.2")
        window._stop_edit.setText("00:00.7")
        window._notch_edit.setText("440")

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)

        assert window._process_status.text() == "✓"
        assert window._last_result is not None
        assert (tmp_path / "tone_filtered.wav").is_file()
        assert len(window._before_canvas._axes.collections) >= 1
        assert len(window._after_canvas._axes.collections) >= 1
        assert window._process_button.isEnabled()
        qtbot.waitUntil(lambda: window._progress_bar.value() == 100, timeout=2000)
        # references are dropped once the QThread actually stops
        qtbot.waitUntil(lambda: window._thread is None, timeout=2000)

    def test_empty_notch_frequencies_still_succeeds(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._notch_edit.setText("")

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)

        assert window._process_status.text() == "✓"


class TestCloseDuringProcessing:
    def test_close_while_processing_does_not_crash(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")

        window._on_process_clicked()
        assert window._thread is not None  # run is in flight

        window.close()  # must wait for the worker, not crash

        assert window._thread is None

    def test_close_when_idle_does_not_crash(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.close()


class TestPlayback:
    def test_play_before_without_result_is_a_noop(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window._on_play_before_clicked()  # must not raise
        assert window._play_before_status.text() == "○"

    def test_play_after_processing_shows_error_in_sandbox(self, qtbot, tmp_path: Path) -> None:
        """No audio device in the sandbox: playback must degrade to a status icon, never crash."""
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)

        window._on_play_after_clicked()  # must not raise

        assert window._play_after_status.text() == "✗"

    def test_stop_playback_without_active_playback_does_not_raise(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window._on_stop_playback_clicked()  # must not raise
