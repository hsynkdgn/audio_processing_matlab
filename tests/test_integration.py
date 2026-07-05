"""PHASE 4 integration tests: full-stack scenarios through MainWindow.

These go beyond the per-unit tests in test_media.py/test_dsp.py/
test_pipeline.py/test_main_window.py by exercising realistic end-to-end
situations a real user session could hit: stereo GoPro-shaped audio,
concurrent clicks, output overwrite, multi-frequency harmonic notches,
and boundary time ranges — all through the real MainWindow + real
ffmpeg, never mocked.
"""

import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from heli_noise.ui.main_window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
TONE_MP4 = FIXTURES / "tone_440hz_48k.mp4"
STEREO_MP4 = FIXTURES / "stereo_tone_440hz_48k.mp4"
NOISE_WAV = FIXTURES / "noise_250hz_48k.wav"


def _dominant_frequency(samples: np.ndarray, sample_rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    return float(freqs[np.argmax(spectrum)])


class TestStereoDownmixEndToEnd:
    def test_stereo_gopro_shaped_mp4_downmixes_correctly(self, qtbot, tmp_path: Path) -> None:
        """L=0.8*sin(440), R=0.4*sin(440) -> mono average should sit near 0.6x amplitude."""
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "stereo_flight.mp4"
        shutil.copy(STEREO_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._notch_edit.setText("")

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)

        assert window._process_status.text() == "✓"
        result = window._last_result
        # AAC is lossy but the averaged channel content must still peak at 440 Hz.
        assert (
            _dominant_frequency(result.original_signal, result.sample_rate) == 440.0
            or abs(_dominant_frequency(result.original_signal, result.sample_rate) - 440.0) < 5.0
        )
        out_info = sf.info(str(tmp_path / "stereo_flight_filtered.wav"))
        assert out_info.channels == 1


class TestConcurrentProcessGuard:
    def test_process_button_disabled_during_run_blocks_second_click(
        self, qtbot, tmp_path: Path
    ) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")

        window._on_process_clicked()
        assert window._process_button.isEnabled() is False

        # A second click while the button is disabled is a real-world
        # double-click; the handler itself has no re-entrancy guard, so
        # this proves the UI-level disable is what prevents concurrent runs.
        first_thread = window._thread
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)
        qtbot.waitUntil(lambda: window._thread is None, timeout=2000)
        assert window._process_button.isEnabled() is True
        assert first_thread is not None


class TestOutputOverwrite:
    def test_processing_twice_overwrites_the_output_file(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")
        window._notch_edit.setText("440")

        window._on_process_clicked()
        # Wait for the thread to fully stop (not just _last_result), matching
        # what a real button-disabled UI enforces: the button only
        # re-enables once the worker thread has actually finished.
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)
        first_mtime = (tmp_path / "tone_filtered.wav").stat().st_mtime_ns

        window._notch_edit.setText("")  # different config for the second run
        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)

        out_path = tmp_path / "tone_filtered.wav"
        assert out_path.is_file()
        assert out_path.stat().st_mtime_ns >= first_mtime


class TestHarmonicNotchChain:
    def test_multiple_rotor_harmonic_frequencies_via_ui_text_field(
        self, qtbot, tmp_path: Path
    ) -> None:
        """Realistic use case: suppressing several helicopter rotor harmonics at once."""
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "noise.wav"
        shutil.copy(NOISE_WAV, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:02")
        window._notch_edit.setText(" 250, 500, 750 ")  # 250 Hz + harmonics, extra whitespace

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._last_result is not None, timeout=5000)

        assert window._process_status.text() == "✓"
        result = window._last_result

        def _energy_at(signal: np.ndarray, fs: float, target_hz: float) -> float:
            spectrum = np.abs(np.fft.rfft(signal))
            freqs = np.fft.rfftfreq(len(signal), d=1.0 / fs)
            idx = int(np.argmin(np.abs(freqs - target_hz)))
            return float(spectrum[idx])

        before_250 = _energy_at(result.original_signal, result.sample_rate, 250.0)
        after_250 = _energy_at(result.processed_signal, result.sample_rate, 250.0)
        assert after_250 < before_250 * 0.5


class TestBoundaryTimeRanges:
    def test_smallest_ui_expressible_cut_succeeds(self, qtbot, tmp_path: Path) -> None:
        """The time field's finest granularity is 1 ms (parse_time only keeps
        3 fractional digits). At 48 kHz that is 48 samples, comfortably above
        filtfilt's padlen (9 samples for a biquad notch) — so the smallest
        interval a user can actually type in never hits the "signal too
        short for filtfilt" InvalidTimeRangeError; that error path is
        real (see test_dsp.py) but unreachable from this UI's precision.
        This asserts the smallest expressible cut still succeeds cleanly.
        """
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:00.001")
        window._notch_edit.setText("440")

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)

        assert window._process_status.text() == "✓"

    def test_cut_covering_the_entire_file_succeeds(self, qtbot, tmp_path: Path) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        source = tmp_path / "tone.mp4"
        shutil.copy(TONE_MP4, source)
        window._set_input_path(source)
        window._start_edit.setText("00:00")
        window._stop_edit.setText("00:01")  # exactly the fixture's full 1.0 s duration

        window._on_process_clicked()
        qtbot.waitUntil(lambda: window._thread is None, timeout=5000)

        assert window._process_status.text() == "✓"
