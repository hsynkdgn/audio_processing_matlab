"""End-to-end processing pipeline tying media.py and dsp.py together.

GUI-independent by rule: this is the single composition point between
extraction, DSP, and file output, so it can be unit-tested without Qt and
reused unchanged by the ui-layer worker thread.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from heli_noise.core.dsp import (
    DEFAULT_NOVERLAP,
    DEFAULT_NPERSEG,
    DEFAULT_Q,
    SpectrogramResult,
    apply_notch_chain,
    compute_spectrogram,
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
        before_spectrogram: Spectrogram of ``original_signal``.
        after_spectrogram: Spectrogram of ``processed_signal``.
    """

    output_path: Path
    sample_rate: int
    original_signal: np.ndarray
    processed_signal: np.ndarray
    before_spectrogram: SpectrogramResult
    after_spectrogram: SpectrogramResult


def process_recording(
    input_path: Path,
    start_s: float,
    stop_s: float,
    notch_frequencies: list[float],
    output_path: Path,
    q: float = DEFAULT_Q,
    nperseg: int = DEFAULT_NPERSEG,
    noverlap: int = DEFAULT_NOVERLAP,
) -> ProcessResult:
    """Cut, analyze, filter, normalize, and save a recording.

    Steps: extract the requested interval's audio track to a temporary
    WAV, remove DC offset, compute the "before" spectrogram, apply the
    notch chain, peak-normalize, compute the "after" spectrogram, and
    write the result to ``output_path``. Nothing is written to
    ``output_path`` if any earlier step raises.

    Args:
        input_path: Source media file (MP4/MP3/WAV/...).
        start_s: Interval start in seconds.
        stop_s: Interval stop in seconds.
        notch_frequencies: Frequencies (Hz) to suppress, in order.
        output_path: Destination WAV path.
        q: Quality factor applied to every notch.
        nperseg: STFT samples per segment (before/after spectrograms).
        noverlap: STFT overlap samples (before/after spectrograms).

    Returns:
        A :class:`ProcessResult` describing the outcome.

    Raises:
        MediaDecodeError: If the source cannot be probed or decoded.
        InvalidTimeRangeError: If the time range or a filtered segment
            is invalid.
        FilterConfigError: If a notch frequency or STFT parameter is invalid.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted_path = Path(tmp_dir) / "extracted.wav"
        extract_audio(input_path, start_s, stop_s, extracted_path)
        raw_signal, sample_rate = load_wav(extracted_path)

    original_signal = remove_dc_offset(raw_signal)
    before_spectrogram = compute_spectrogram(
        original_signal, sample_rate, nperseg=nperseg, noverlap=noverlap
    )

    filtered_signal = apply_notch_chain(original_signal, sample_rate, notch_frequencies, q=q)
    processed_signal = normalize_peak(filtered_signal)
    after_spectrogram = compute_spectrogram(
        processed_signal, sample_rate, nperseg=nperseg, noverlap=noverlap
    )

    save_wav(output_path, processed_signal, sample_rate)

    return ProcessResult(
        output_path=output_path,
        sample_rate=sample_rate,
        original_signal=original_signal,
        processed_signal=processed_signal,
        before_spectrogram=before_spectrogram,
        after_spectrogram=after_spectrogram,
    )
