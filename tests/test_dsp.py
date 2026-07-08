"""Tests for core.dsp — spectrogram, notch chain, DC removal, normalization.

Uses the committed WAV fixtures under tests/fixtures/ (via core.media.load_wav)
plus synthetic arrays for edge cases that don't need real audio.
"""

from pathlib import Path

import numpy as np
import pytest

from heli_noise.core.dsp import (
    DEFAULT_NPERSEG,
    SpectrogramResult,
    SpectrumPeak,
    SpectrumResult,
    apply_notch,
    apply_notch_chain,
    compute_spectrogram,
    compute_spectrum,
    find_spectrum_peaks,
    normalize_peak,
    parse_frequency_list,
    remove_dc_offset,
)
from heli_noise.core.exceptions import FilterConfigError, InvalidTimeRangeError
from heli_noise.core.media import load_wav

FIXTURES = Path(__file__).parent / "fixtures"


def _bin_index(frequencies: np.ndarray, target_hz: float) -> int:
    return int(np.argmin(np.abs(frequencies - target_hz)))


def _energy_at(signal: np.ndarray, fs: float, target_hz: float) -> float:
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / fs)
    return float(spectrum[_bin_index(freqs, target_hz)])


class TestComputeSpectrogram:
    def test_shape_and_dtype(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrogram(signal, fs)
        assert isinstance(result, SpectrogramResult)
        assert result.magnitude_db.shape == (len(result.frequencies), len(result.times))
        assert result.magnitude_db.dtype == np.float64

    def test_no_nan_or_inf(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrogram(signal, fs)
        assert np.all(np.isfinite(result.magnitude_db))

    def test_silence_has_no_inf(self) -> None:
        silence = np.zeros(8192)
        result = compute_spectrogram(silence, fs=48_000)
        assert np.all(np.isfinite(result.magnitude_db))

    def test_tone_peaks_at_its_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrogram(signal, fs)
        avg_db = result.magnitude_db.mean(axis=1)
        peak_freq = result.frequencies[np.argmax(avg_db)]
        assert peak_freq == pytest.approx(440.0, abs=result.frequencies[1])

    def test_default_parameters(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrogram(signal, fs)
        # nperseg=2048 -> 1025 one-sided frequency bins
        assert len(result.frequencies) == DEFAULT_NPERSEG // 2 + 1

    def test_segment_shorter_than_nperseg_does_not_crash(self) -> None:
        short_signal = np.sin(2 * np.pi * 440 * np.arange(500) / 48_000)
        result = compute_spectrogram(short_signal, fs=48_000)
        assert np.all(np.isfinite(result.magnitude_db))
        assert result.magnitude_db.shape[1] >= 1

    def test_noverlap_must_be_less_than_nperseg(self) -> None:
        signal = np.zeros(4096)
        with pytest.raises(FilterConfigError, match="noverlap"):
            compute_spectrogram(signal, fs=48_000, nperseg=1024, noverlap=1024)

    def test_noverlap_greater_than_nperseg(self) -> None:
        signal = np.zeros(4096)
        with pytest.raises(FilterConfigError):
            compute_spectrogram(signal, fs=48_000, nperseg=1024, noverlap=2048)

    def test_nperseg_must_be_positive(self) -> None:
        signal = np.zeros(4096)
        with pytest.raises(FilterConfigError, match="nperseg"):
            compute_spectrogram(signal, fs=48_000, nperseg=0, noverlap=0)

    def test_configurable_parameters_change_resolution(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrogram(signal, fs, nperseg=512, noverlap=256)
        default_result = compute_spectrogram(signal, fs)
        assert len(result.frequencies) == 512 // 2 + 1
        assert len(result.frequencies) != len(default_result.frequencies)


class TestApplyNotch:
    def test_reduces_energy_at_target_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        before = _energy_at(signal, fs, 440.0)
        after_signal = apply_notch(signal, fs, 440.0)
        after = _energy_at(after_signal, fs, 440.0)
        assert after < before * 0.1  # at least ~20 dB reduction

    def test_leaves_distant_frequencies_mostly_untouched(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        before_100 = _energy_at(signal, fs, 100.0)
        before_1000 = _energy_at(signal, fs, 1000.0)
        filtered = apply_notch(signal, fs, 400.0)
        after_100 = _energy_at(filtered, fs, 100.0)
        after_1000 = _energy_at(filtered, fs, 1000.0)
        assert after_100 == pytest.approx(before_100, rel=0.1)
        assert after_1000 == pytest.approx(before_1000, rel=0.1)

    def test_zero_frequency_rejected(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        with pytest.raises(FilterConfigError):
            apply_notch(signal, fs, 0.0)

    def test_negative_frequency_rejected(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        with pytest.raises(FilterConfigError):
            apply_notch(signal, fs, -100.0)

    def test_nyquist_violation_at_48k(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")  # fs=48000, Nyquist=24000
        with pytest.raises(FilterConfigError, match="Nyquist"):
            apply_notch(signal, fs, 24_000.0)

    def test_23khz_valid_at_48k_but_invalid_at_44k1(self) -> None:
        # 48 kHz: Nyquist = 24000 Hz -> 23000 Hz is valid
        signal_48k = np.sin(2 * np.pi * 100 * np.arange(48_000) / 48_000)
        apply_notch(signal_48k, 48_000.0, 23_000.0)  # must not raise

        # 44.1 kHz: Nyquist = 22050 Hz -> 23000 Hz is invalid
        signal_44k1 = np.sin(2 * np.pi * 100 * np.arange(44_100) / 44_100)
        with pytest.raises(FilterConfigError, match="Nyquist"):
            apply_notch(signal_44k1, 44_100.0, 23_000.0)

    def test_signal_too_short_raises_invalid_time_range(self) -> None:
        short_signal = np.sin(2 * np.pi * 440 * np.arange(5) / 48_000)
        with pytest.raises(InvalidTimeRangeError):
            apply_notch(short_signal, 48_000.0, 440.0)

    def test_never_uses_lfilter_phase_is_zero(self) -> None:
        # filtfilt is zero-phase: a symmetric pulse centered in the buffer
        # should stay (approximately) centered after filtering.
        fs = 48_000
        n = 4096
        signal = np.zeros(n)
        signal[n // 2] = 1.0
        filtered = apply_notch(signal, fs, 1000.0, q=5.0)
        assert np.argmax(np.abs(filtered)) == pytest.approx(n // 2, abs=2)


class TestApplyNotchChain:
    def test_empty_chain_returns_signal_unchanged(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = apply_notch_chain(signal, fs, [])
        assert np.array_equal(result, signal)

    def test_removes_multiple_frequencies(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        before_400 = _energy_at(signal, fs, 400.0)
        before_1000 = _energy_at(signal, fs, 1000.0)
        filtered = apply_notch_chain(signal, fs, [400.0, 1000.0])
        assert _energy_at(filtered, fs, 400.0) < before_400 * 0.1
        assert _energy_at(filtered, fs, 1000.0) < before_1000 * 0.1

    def test_exact_duplicate_frequencies_deduped(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        once = apply_notch_chain(signal, fs, [440.0])
        thrice = apply_notch_chain(signal, fs, [440.0, 440.0, 440.0])
        assert np.allclose(once, thrice)

    def test_close_frequencies_both_applied_without_crash(self) -> None:
        fs = 48_000
        t = np.arange(fs) / fs  # 1 s, long enough for filtfilt padding
        signal = np.sin(2 * np.pi * 100.0 * t) + np.sin(2 * np.pi * 102.0 * t)
        before_100 = _energy_at(signal, fs, 100.0)
        filtered = apply_notch_chain(signal, fs, [100.0, 102.0], q=30.0)
        assert np.all(np.isfinite(filtered))
        after_100 = _energy_at(filtered, fs, 100.0)
        assert after_100 < before_100 * 0.5  # overlapping notches still attenuate

    def test_invalid_frequency_in_chain_raises(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        with pytest.raises(FilterConfigError):
            apply_notch_chain(signal, fs, [440.0, 24_000.0])


class TestRemoveDcOffset:
    def test_removes_constant_offset(self) -> None:
        signal = np.ones(1000) * 0.5 + np.sin(2 * np.pi * 10 * np.arange(1000) / 1000)
        result = remove_dc_offset(signal)
        assert np.mean(result) == pytest.approx(0.0, abs=1e-10)

    def test_does_not_mutate_input(self) -> None:
        signal = np.ones(100) * 0.5
        original = signal.copy()
        remove_dc_offset(signal)
        assert np.array_equal(signal, original)

    def test_zero_mean_signal_is_noop(self) -> None:
        signal = np.array([1.0, -1.0, 1.0, -1.0])
        assert np.allclose(remove_dc_offset(signal), signal)


class TestNormalizePeak:
    def test_peak_becomes_one(self) -> None:
        signal = np.array([0.1, -0.4, 0.2, -0.05])
        result = normalize_peak(signal)
        assert np.max(np.abs(result)) == pytest.approx(1.0)

    def test_preserves_relative_shape(self) -> None:
        signal = np.array([0.1, -0.4, 0.2])
        result = normalize_peak(signal)
        assert np.allclose(result, signal / 0.4)

    def test_all_zero_signal_unchanged(self) -> None:
        signal = np.zeros(10)
        result = normalize_peak(signal)
        assert np.array_equal(result, signal)

    def test_does_not_mutate_input(self) -> None:
        signal = np.array([0.5, -0.2])
        original = signal.copy()
        normalize_peak(signal)
        assert np.array_equal(signal, original)

    def test_already_normalized_signal(self) -> None:
        signal = np.array([1.0, -1.0, 0.5])
        result = normalize_peak(signal)
        assert np.allclose(result, signal)


class TestParseFrequencyList:
    def test_single_value(self) -> None:
        assert parse_frequency_list("440") == [440.0]

    def test_multiple_values(self) -> None:
        assert parse_frequency_list("100, 250.5, 400") == [100.0, 250.5, 400.0]

    def test_extra_whitespace_and_trailing_comma(self) -> None:
        assert parse_frequency_list("  100 ,  200,  ") == [100.0, 200.0]

    def test_empty_string_yields_no_notches(self) -> None:
        assert parse_frequency_list("") == []

    def test_blank_string_yields_no_notches(self) -> None:
        assert parse_frequency_list("   ") == []

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(FilterConfigError, match="abc"):
            parse_frequency_list("100, abc, 400")


class TestComputeSpectrum:
    def test_tone_peaks_at_its_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrum(signal, fs)
        assert isinstance(result, SpectrumResult)
        assert result.magnitude_db.shape == result.frequencies.shape
        peak_freq = result.frequencies[np.argmax(result.magnitude_db)]
        assert peak_freq == pytest.approx(440.0, abs=float(result.frequencies[1]))

    def test_mixture_shows_all_three_peaks(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        result = compute_spectrum(signal, fs)
        floor_db = float(np.median(result.magnitude_db))
        for target in (100.0, 400.0, 1000.0):
            idx = int(np.argmin(np.abs(result.frequencies - target)))
            assert result.magnitude_db[idx] > floor_db + 20  # clearly above the floor

    def test_silence_is_finite(self) -> None:
        result = compute_spectrum(np.zeros(8192), fs=48_000)
        assert np.all(np.isfinite(result.magnitude_db))

    def test_short_signal_does_not_crash(self) -> None:
        short_signal = np.sin(2 * np.pi * 440 * np.arange(500) / 48_000)
        result = compute_spectrum(short_signal, fs=48_000)
        assert np.all(np.isfinite(result.magnitude_db))

    def test_invalid_noverlap_rejected(self) -> None:
        with pytest.raises(FilterConfigError, match="noverlap"):
            compute_spectrum(np.zeros(4096), fs=48_000, nperseg=1024, noverlap=1024)

    def test_invalid_nperseg_rejected(self) -> None:
        with pytest.raises(FilterConfigError, match="nperseg"):
            compute_spectrum(np.zeros(4096), fs=48_000, nperseg=0, noverlap=0)

    def test_notched_spectrum_dips_at_notch_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        filtered = apply_notch(signal, fs, 440.0)
        before = compute_spectrum(signal, fs)
        after = compute_spectrum(filtered, fs)
        idx = int(np.argmin(np.abs(before.frequencies - 440.0)))
        assert after.magnitude_db[idx] < before.magnitude_db[idx] - 10


class TestFindSpectrumPeaks:
    def test_single_tone_yields_one_peak_near_its_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
        result = compute_spectrum(signal, fs)
        peaks = find_spectrum_peaks(result)
        assert len(peaks) == 1
        assert isinstance(peaks[0], SpectrumPeak)
        assert peaks[0].frequency == pytest.approx(440.0, abs=float(result.frequencies[1]))

    def test_mixture_yields_three_peaks_at_correct_frequencies(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        result = compute_spectrum(signal, fs)
        peaks = find_spectrum_peaks(result)
        found = sorted(peak.frequency for peak in peaks)
        assert len(found) == 3
        for target, actual in zip((100.0, 400.0, 1000.0), found, strict=True):
            assert actual == pytest.approx(target, abs=float(result.frequencies[1]) * 2)

    def test_peaks_sorted_by_ascending_frequency(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        result = compute_spectrum(signal, fs)
        peaks = find_spectrum_peaks(result)
        frequencies = [peak.frequency for peak in peaks]
        assert frequencies == sorted(frequencies)

    def test_silence_yields_no_peaks(self) -> None:
        result = compute_spectrum(np.zeros(8192), fs=48_000)
        assert find_spectrum_peaks(result) == []

    def test_flat_spectrum_yields_no_peaks(self) -> None:
        result = SpectrumResult(
            frequencies=np.linspace(0, 24_000, 100), magnitude_db=np.full(100, -40.0)
        )
        assert find_spectrum_peaks(result) == []

    def test_too_few_bins_yields_no_peaks(self) -> None:
        result = SpectrumResult(
            frequencies=np.array([0.0, 100.0]), magnitude_db=np.array([1.0, 2.0])
        )
        assert find_spectrum_peaks(result) == []

    def test_max_peaks_caps_the_result(self) -> None:
        signal, fs = load_wav(FIXTURES / "mix_100_400_1000hz_44k1.wav")
        result = compute_spectrum(signal, fs)
        peaks = find_spectrum_peaks(result, max_peaks=2)
        assert len(peaks) == 2

    def test_min_distance_hz_merges_nearby_peaks(self) -> None:
        # Two adjacent bins bumped up close together should collapse to a
        # single reported peak once min_distance_hz spans several bins.
        frequencies = np.linspace(0, 1000, 501)  # 2 Hz/bin
        magnitude_db = np.full(501, -60.0)
        magnitude_db[100] = 0.0
        magnitude_db[102] = -1.0  # 4 Hz away from the first bump
        result = SpectrumResult(frequencies=frequencies, magnitude_db=magnitude_db)

        peaks = find_spectrum_peaks(result, min_distance_hz=50.0)

        assert len(peaks) == 1
        assert peaks[0].frequency == pytest.approx(200.0, abs=1.0)
