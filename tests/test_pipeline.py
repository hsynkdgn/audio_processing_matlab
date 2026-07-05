"""Tests for core.pipeline — the end-to-end extract/filter/normalize/save flow."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from heli_noise.core.dsp import SpectrogramResult
from heli_noise.core.exceptions import FilterConfigError, InvalidTimeRangeError, MediaDecodeError
from heli_noise.core.pipeline import ProcessResult, process_recording

FIXTURES = Path(__file__).parent / "fixtures"
TONE_MP4 = FIXTURES / "tone_440hz_48k.mp4"


class TestProcessRecording:
    def test_end_to_end_mp4(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        result = process_recording(TONE_MP4, 0.2, 0.7, [440.0], out)

        assert isinstance(result, ProcessResult)
        assert result.output_path == out
        assert out.is_file()
        assert result.sample_rate == 48_000
        assert isinstance(result.before_spectrogram, SpectrogramResult)
        assert isinstance(result.after_spectrogram, SpectrogramResult)

        info = sf.info(str(out))
        assert info.channels == 1
        assert info.subtype == "PCM_16"
        assert info.samplerate == 48_000

    def test_notch_reduces_energy_in_after_spectrogram(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        result = process_recording(TONE_MP4, 0.0, 1.0, [440.0], out)

        def _avg_db_near(spectrogram: SpectrogramResult, target_hz: float) -> float:
            idx = int(np.argmin(np.abs(spectrogram.frequencies - target_hz)))
            return float(spectrogram.magnitude_db[idx].mean())

        before_db = _avg_db_near(result.before_spectrogram, 440.0)
        after_db = _avg_db_near(result.after_spectrogram, 440.0)
        assert after_db < before_db - 10  # meaningful attenuation, in dB

    def test_no_notch_frequencies_still_normalizes(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        result = process_recording(TONE_MP4, 0.0, 1.0, [], out)
        assert np.max(np.abs(result.processed_signal)) == pytest.approx(1.0, abs=1e-6)

    def test_processed_signal_matches_saved_file(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        result = process_recording(TONE_MP4, 0.0, 1.0, [440.0], out)
        saved, sr = sf.read(str(out), dtype="float64")
        assert sr == result.sample_rate
        assert np.allclose(saved, result.processed_signal, atol=1e-3)

    def test_invalid_time_range_propagates_and_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        with pytest.raises(InvalidTimeRangeError):
            process_recording(TONE_MP4, 0.0, 5.0, [440.0], out)
        assert not out.exists()

    def test_invalid_notch_frequency_propagates_and_writes_nothing(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        with pytest.raises(FilterConfigError):
            process_recording(TONE_MP4, 0.0, 1.0, [24_000.0], out)
        assert not out.exists()

    def test_missing_input_propagates(self, tmp_path: Path) -> None:
        out = tmp_path / "filtered.wav"
        with pytest.raises(MediaDecodeError):
            process_recording(tmp_path / "missing.mp4", 0.0, 1.0, [440.0], out)
        assert not out.exists()
