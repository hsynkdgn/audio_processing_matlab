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
    def test_successful_run_updates_status_and_spectra(self, qtbot, tmp_path: Path) -> None:
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
        assert len(window._before_panel.canvas._axes.lines) >= 1
        assert len(window._after_panel.canvas._axes.lines) >= 1
        qtbot.waitUntil(lambda: window._progress_bar.value() == 100, timeout=2000)
        # The button only re-enables once the QThread has actually
        # stopped (not merely when the worker's finished signal fires) —
        # see main_window._on_thread_stopped for why that gap matters.
        qtbot.waitUntil(lambda: window._thread is None, timeout=2000)
        assert window._process_button.isEnabled()

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

    def test_playback_buttons_disabled_until_a_result_exists(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._play_before_button.isEnabled() is False
        assert window._play_after_button.isEnabled() is False
        assert window._stop_playback_button.isEnabled() is False

        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._on_process_clicked()
        # disabled while the run is in flight too
        assert window._play_before_button.isEnabled() is False
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)

        assert window._play_before_button.isEnabled() is True
        assert window._play_after_button.isEnabled() is True
        assert window._stop_playback_button.isEnabled() is True

    def test_new_run_resets_playback_status_icons(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)
        window._on_play_after_clicked()  # sandbox: sets ✗
        assert window._play_after_status.text() == "✗"

        window._on_process_clicked()  # second run must clear stale play statuses
        assert window._play_after_status.text() == "○"
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)


class TestControlLifecycleOnFailure:
    def test_button_reenables_after_failed_run_only_when_thread_stops(
        self, qtbot, tmp_path: Path
    ) -> None:
        """The failure path must use the same QThread.finished gating as
        the success path (an early re-enable here was a real race, found
        in a project-wide review after PHASE 5)."""
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._notch_edit.setText("24000")  # >= Nyquist -> FilterConfigError in worker

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._process_status.text() == "✗", timeout=5000)
        qtbot.waitUntil(lambda: window._thread is None, timeout=2000)
        assert window._process_button.isEnabled() is True


class TestBrowseDirectoryMemory:
    def test_last_directory_follows_the_selected_file(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._last_dir == ""
        nested = tmp_path / "Kayıtlar" / "Temmuz"
        nested.mkdir(parents=True)
        source = nested / "uçuş.mp4"
        shutil.copy(TONE_MP4, source)

        window._set_input_path(source)

        assert window._last_dir == str(nested)


class TestSeekSlider:
    def test_slider_disabled_until_a_result_exists(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._seek_slider.isEnabled() is False
        assert window._seek_label.text() == "00:00.000 / 00:00.000"

    def test_slider_enabled_after_processing(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)

        assert window._seek_slider.isEnabled() is True

    def test_slider_release_seeks_the_adapter(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        seeks: list[float] = []
        window._playback.seek = seeks.append  # type: ignore[method-assign]
        window._seek_slider.setRange(0, 5000)
        window._seek_slider.setValue(1500)

        window._on_seek_slider_released()

        assert seeks == [1.5]

    def test_slider_drag_updates_label_without_seeking(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        seeks: list[float] = []
        window._playback.seek = seeks.append  # type: ignore[method-assign]

        window._on_seek_slider_moved(2500)

        assert seeks == []
        assert window._seek_label.text().startswith("00:02.500 /")

    def test_format_seek_label(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert window._format_seek_label(1.25, 5.0) == "00:01.250 / 00:05.000"
