"""DSP primitives: spectrum/spectrogram computation, notch (band-stop)
filtering, DC-offset removal, and peak normalization.

Per .claude/skills/dsp-pipeline/SKILL.md: STFT defaults are window=hann,
nperseg=2048, noverlap=1536 (all configurable); notches always use
zero-phase filtfilt, never lfilter; Nyquist violations are hard errors,
never silently clamped.
"""

from dataclasses import dataclass

import numpy as np
from scipy.signal import filtfilt, iirnotch, stft, welch

from heli_noise.core.exceptions import FilterConfigError, InvalidTimeRangeError

DEFAULT_WINDOW = "hann"
DEFAULT_NPERSEG = 2048
DEFAULT_NOVERLAP = 1536
DEFAULT_Q = 30.0

_LOG_EPSILON = 1e-12


@dataclass(frozen=True)
class SpectrogramResult:
    """Result of an STFT spectrogram computation.

    Attributes:
        frequencies: 1-D array of frequency bins in Hz.
        times: 1-D array of time-segment centers in seconds.
        magnitude_db: 2-D array (frequencies x times) of magnitude in dB.
    """

    frequencies: np.ndarray
    times: np.ndarray
    magnitude_db: np.ndarray


@dataclass(frozen=True)
class SpectrumResult:
    """Result of a frequency-amplitude spectrum computation (no time axis).

    Attributes:
        frequencies: 1-D array of frequency bins in Hz.
        magnitude_db: 1-D array of magnitude in dB, one value per bin.
    """

    frequencies: np.ndarray
    magnitude_db: np.ndarray


def compute_spectrum(
    signal: np.ndarray,
    fs: float,
    window: str = DEFAULT_WINDOW,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> SpectrumResult:
    """Compute a frequency-amplitude spectrum in dB (Welch's method).

    Welch averaging over overlapping segments gives a stable amplitude
    estimate per frequency for noisy helicopter recordings — this is the
    "which frequencies are loud" view the UI shows before/after
    filtering, as opposed to the time-resolved spectrogram.

    Args:
        signal: 1-D float samples (mono).
        fs: Sample rate in Hz.
        window: scipy window name.
        nperseg: Samples per Welch segment.
        noverlap: Overlapping samples between segments; must be < nperseg.

    Returns:
        A :class:`SpectrumResult` with frequencies and dB magnitude.

    Raises:
        FilterConfigError: If ``nperseg`` is not positive or
            ``noverlap >= nperseg``.
    """
    if nperseg <= 0:
        raise FilterConfigError(f"nperseg must be > 0, got {nperseg}")
    if noverlap >= nperseg:
        raise FilterConfigError(f"noverlap ({noverlap}) must be less than nperseg ({nperseg})")

    # Same short-signal clamping rationale as compute_spectrogram: scipy
    # shrinks nperseg to the signal length but leaves noverlap untouched.
    effective_nperseg = min(nperseg, len(signal))
    effective_noverlap = min(noverlap, max(effective_nperseg - 1, 0))

    frequencies, power = welch(
        signal,
        fs=fs,
        window=window,
        nperseg=effective_nperseg,
        noverlap=effective_noverlap,
    )
    magnitude_db = 10 * np.log10(power + _LOG_EPSILON)  # power -> dB
    return SpectrumResult(frequencies=frequencies, magnitude_db=magnitude_db)


def remove_dc_offset(signal: np.ndarray) -> np.ndarray:
    """Subtract the mean from a signal.

    GoPro audio tracks may carry a DC offset; removing it keeps the 0 Hz
    bin from dominating spectrogram displays and keeps normalization
    meaningful.

    Args:
        signal: 1-D float samples.

    Returns:
        A new array with zero mean.
    """
    return signal - np.mean(signal)


def compute_spectrogram(
    signal: np.ndarray,
    fs: float,
    window: str = DEFAULT_WINDOW,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> SpectrogramResult:
    """Compute an STFT magnitude spectrogram in dB.

    Args:
        signal: 1-D float samples (mono).
        fs: Sample rate in Hz.
        window: scipy window name.
        nperseg: Samples per STFT segment.
        noverlap: Overlapping samples between segments; must be < nperseg.

    Returns:
        A :class:`SpectrogramResult` with frequencies, times, and dB magnitude.

    Raises:
        FilterConfigError: If ``nperseg`` is not positive or
            ``noverlap >= nperseg``.
    """
    if nperseg <= 0:
        raise FilterConfigError(f"nperseg must be > 0, got {nperseg}")
    if noverlap >= nperseg:
        raise FilterConfigError(f"noverlap ({noverlap}) must be less than nperseg ({nperseg})")

    # Segments shorter than nperseg: scipy clamps nperseg down to the
    # signal length internally but leaves noverlap untouched, which would
    # then violate noverlap < nperseg and crash inside scipy. Clamp both
    # ourselves so short segments still produce a (small) spectrogram.
    effective_nperseg = min(nperseg, len(signal))
    effective_noverlap = min(noverlap, max(effective_nperseg - 1, 0))

    frequencies, times, stft_matrix = stft(
        signal,
        fs=fs,
        window=window,
        nperseg=effective_nperseg,
        noverlap=effective_noverlap,
        boundary="zeros",
        padded=True,
    )
    magnitude_db = 20 * np.log10(np.abs(stft_matrix) + _LOG_EPSILON)
    return SpectrogramResult(frequencies=frequencies, times=times, magnitude_db=magnitude_db)


def apply_notch(
    signal: np.ndarray, fs: float, frequency: float, q: float = DEFAULT_Q
) -> np.ndarray:
    """Apply a single zero-phase notch (band-stop) filter.

    Uses ``scipy.signal.iirnotch`` + ``filtfilt`` (never ``lfilter``, to
    avoid phase distortion).

    Args:
        signal: 1-D float samples (mono).
        fs: Sample rate in Hz.
        frequency: Center frequency to suppress, in Hz. Must be in
            ``(0, fs / 2)``.
        q: Quality factor of the notch (higher = narrower).

    Returns:
        The filtered signal (same length as ``signal``).

    Raises:
        FilterConfigError: If ``frequency`` is <= 0 or >= the Nyquist
            frequency (``fs / 2``). Never silently clamped.
        InvalidTimeRangeError: If ``signal`` is too short for
            ``filtfilt``'s default padding.
    """
    nyquist = fs / 2.0
    if frequency <= 0:
        raise FilterConfigError(f"Notch frequency must be > 0 Hz, got {frequency}")
    if frequency >= nyquist:
        raise FilterConfigError(
            f"Notch frequency {frequency} Hz is >= Nyquist ({nyquist} Hz at fs={fs})"
        )

    b, a = iirnotch(w0=frequency, Q=q, fs=fs)
    padlen = 3 * max(len(a), len(b))
    if len(signal) <= padlen:
        raise InvalidTimeRangeError(
            f"Signal has {len(signal)} samples, too short to notch-filter at "
            f"{frequency} Hz (needs more than {padlen} samples)"
        )
    return filtfilt(b, a, signal)


def apply_notch_chain(
    signal: np.ndarray,
    fs: float,
    frequencies: list[float],
    q: float = DEFAULT_Q,
) -> np.ndarray:
    """Apply a sequential chain of notch filters.

    Exact duplicate frequencies are applied only once (repeating an
    identical notch is redundant, not a stronger notch). Frequencies that
    are merely close together are all applied — their overlapping notches
    are allowed to carve a wider suppressed band.

    Args:
        signal: 1-D float samples (mono).
        fs: Sample rate in Hz.
        frequencies: Center frequencies to suppress, in Hz.
        q: Quality factor applied to every notch in the chain.

    Returns:
        The signal after all notches have been applied in order.

    Raises:
        FilterConfigError: If any frequency is invalid (see :func:`apply_notch`).
        InvalidTimeRangeError: If the signal is too short for filtering.
    """
    deduped: list[float] = []
    for frequency in frequencies:
        if frequency not in deduped:
            deduped.append(frequency)

    result = signal
    for frequency in deduped:
        result = apply_notch(result, fs, frequency, q)
    return result


def parse_frequency_list(text: str) -> list[float]:
    """Parse a comma-separated list of notch frequencies.

    Only checks that each token is a number; Nyquist/positivity
    validation happens later in :func:`apply_notch`. Blank tokens
    (e.g. from a trailing comma) are ignored; an empty or blank
    ``text`` yields an empty list (no notches).

    Args:
        text: Comma-separated frequencies in Hz, e.g. ``"100, 250.5, 400"``.

    Returns:
        The parsed frequencies, in the order given.

    Raises:
        FilterConfigError: If any non-blank token is not a valid number.
    """
    frequencies: list[float] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            frequencies.append(float(token))
        except ValueError as exc:
            raise FilterConfigError(f"Invalid frequency value: {token!r}") from exc
    return frequencies


def normalize_peak(signal: np.ndarray) -> np.ndarray:
    """Peak-normalize a signal to [-1, 1] to prevent clipping.

    An all-zero signal is returned unchanged (no division by zero).

    Args:
        signal: 1-D float samples.

    Returns:
        The normalized signal, or an unchanged copy if the peak is zero.
    """
    peak = np.max(np.abs(signal))
    if peak == 0:
        return signal.copy()
    return signal / peak
