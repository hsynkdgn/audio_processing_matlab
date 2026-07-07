"""End-to-end processing pipeline tying media.py and dsp.py together.

GUI-independent by rule: this is the single composition point between
extraction, DSP, and file output, so it can be unit-tested without Qt and
reused unchanged by the ui-layer worker thread.
"""

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from heli_noise.core.dsp import (
    DEFAULT_NOVERLAP,
    DEFAULT_NPERSEG,
    DEFAULT_Q,
    SpectrumResult,
    apply_notch_chain,
    compute_spectrum,
    normalize_peak,
    remove_dc_offset,
)
from heli_noise.core.media import extract_audio, load_wav, save_wav


@dataclass(frozen=True)
class ProcessResult:
    """Outcome of a full extract -> filter -> normalize -> save run.

    Attributes:
        output_path: Where the final filtered WAV was written.
        sample_rate: Sample rate in Hz shared by both signals.
        original_signal: DC-removed audio before notch filtering (for
            "before" playback).
        processed_signal: Filtered and peak-normalized audio (for
            "after" playback; identical to what was written to disk).
        before_spectrum: Frequency-amplitude spectrum of ``original_signal``.
        after_spectrum: Frequency-amplitude spectrum of ``processed_signal``.
    """

    output_path: Path
    sample_rate: int
    original_signal: np.ndarray
    processed_signal: np.ndarray
    before_spectrum: SpectrumResult
    after_spectrum: SpectrumResult


def process_recording(
    input_path: Path,
    start_s: float,
    stop_s: float,
    notch_frequencies: list[float],
    output_path: Path,
    q: float = DEFAULT_Q,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
    progress_cb: Callable[[int], None] | None = None,
) -> ProcessResult:
    """Cut, analyze, filter, normalize, and save a recording.

    Steps: extract the requested interval's audio track to a temporary
    WAV, remove DC offset, compute the "before" spectrum, apply the
    notch chain, peak-normalize, compute the "after" spectrum, and
    write the result to ``output_path``. Nothing is written to
    ``output_path`` if any earlier step raises.

    Args:
        input_path: Source media file (MP4/MP3/WAV/...).
        start_s: Interval start in seconds.
        stop_s: Interval stop in seconds.
        notch_frequencies: Frequencies (Hz) to suppress, in order.
        output_path: Destination WAV path.
        q: Quality factor applied to every notch.
        nperseg: Welch samples per segment (before/after spectra).
        noverlap: Welch overlap samples (before/after spectra).
        progress_cb: Optional callable receiving coarse progress in
            percent (monotonic, ends at 100). The ui worker injects its
            progress signal here automatically.

    Returns:
        A :class:`ProcessResult` describing the outcome.

    Raises:
        MediaDecodeError: If the source cannot be probed or decoded.
        InvalidTimeRangeError: If the time range or a filtered segment
            is invalid.
        FilterConfigError: If a notch frequency or STFT parameter is invalid.
    """

    def _report(percent: int) -> None:
        if progress_cb is not None:
            progress_cb(percent)

    _report(0)
    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted_path = Path(tmp_dir) / "extracted.wav"
        extract_audio(input_path, start_s, stop_s, extracted_path)
        _report(30)
        raw_signal, sample_rate = load_wav(extracted_path)

    original_signal = remove_dc_offset(raw_signal)
    _report(40)
    before_spectrum = compute_spectrum(
        original_signal, sample_rate, nperseg=nperseg, noverlap=noverlap
    )
    _report(55)

    filtered_signal = apply_notch_chain(original_signal, sample_rate, notch_frequencies, q=q)
    _report(75)
    processed_signal = normalize_peak(filtered_signal)
    after_spectrum = compute_spectrum(
        processed_signal, sample_rate, nperseg=nperseg, noverlap=noverlap
    )
    _report(90)

    save_wav(output_path, processed_signal, sample_rate)
    _report(100)

    return ProcessResult(
        output_path=output_path,
        sample_rate=sample_rate,
        original_signal=original_signal,
        processed_signal=processed_signal,
        before_spectrum=before_spectrum,
        after_spectrum=after_spectrum,
    )
