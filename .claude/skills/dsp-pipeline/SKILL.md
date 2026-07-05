---
name: dsp-pipeline
description: "Use when working on the audio processing chain (cut→WAV→STFT→notch→normalize). STFT parameters, iirnotch/filtfilt usage, Nyquist validation, and normalization rules."
---

# DSP pipeline rules (cut → WAV → STFT → notch → normalize)

## Pipeline order (fixed)

1. Decode/cut media to mono float WAV data (see ffmpeg-media skill).
2. STFT for the "before" spectrogram.
3. Notch-filter chain (one `iirnotch` per requested frequency).
4. Peak-normalize to [-1, 1].
5. STFT again for the "after" spectrogram.
6. Write mono 16-bit PCM WAV at the ORIGINAL sample rate.

## STFT / spectrogram

Defaults (must remain user-configurable):

```python
from scipy.signal import stft

f, t, Z = stft(
    x,                  # 1-D float64 mono signal in [-1, 1]
    fs=sample_rate,
    window="hann",
    nperseg=2048,
    noverlap=1536,      # 75% overlap
    boundary="zeros",
    padded=True,
)
magnitude_db = 20 * np.log10(np.abs(Z) + 1e-12)   # epsilon avoids log(0)
```

- Always add a small epsilon before `log10`; silence frames otherwise
  produce `-inf` and break matplotlib color scaling.
- Display range: clip dB to something like [max-90, max] for readable
  spectrograms; do NOT bake the clip into stored data.
- `noverlap` MUST be < `nperseg`; validate and raise `FilterConfigError`
  (or a dedicated STFT config error) instead of letting scipy raise.

## Notch (band-stop) chain

```python
from scipy.signal import iirnotch, filtfilt

def apply_notch(x: np.ndarray, fs: float, f0: float, q: float = 30.0) -> np.ndarray:
    nyquist = fs / 2.0
    if f0 <= 0.0:
        raise FilterConfigError(f"Notch frequency must be > 0 Hz, got {f0}")
    if f0 >= nyquist:
        raise FilterConfigError(
            f"Notch frequency {f0} Hz is >= Nyquist ({nyquist} Hz at fs={fs})"
        )
    b, a = iirnotch(w0=f0, Q=q, fs=fs)
    return filtfilt(b, a, x)
```

- One `iirnotch` per user frequency, applied sequentially (a chain).
- ALWAYS `filtfilt` (zero phase), NEVER `lfilter` (phase distortion is
  audible and shifts transients).
- `filtfilt` needs `len(x) > 3 * max(len(a), len(b))` (its default
  `padlen`); for iirnotch that is 9 samples — still validate signal
  length and raise a clear error for absurdly short segments.
- Nyquist violation is an ERROR (`FilterConfigError`) — never silently
  clamp or skip the frequency. The user must be told.

## Normalization

After the full filter chain:

```python
peak = np.max(np.abs(y))
if peak > 0:
    y = y / peak            # peak-normalize to [-1, 1]
```

- Normalize ONCE, after all notches — not per filter.
- All-zero signal (peak == 0): leave as-is, do not divide.
- Convert to int16 only at WAV-write time:
  `np.clip(y, -1.0, 1.0)` then scale by 32767 (soundfile subtype
  "PCM_16" handles this when given float in [-1, 1]).

## Edge cases to test every time

- **Segment shorter than nperseg**: `stft` pads, but the spectrogram has
  ~1 time column; make sure plotting/UI handles it. For segments shorter
  than `filtfilt`'s padlen, raise `InvalidTimeRangeError`.
- **DC offset**: GoPro tracks may carry DC. Remove mean before STFT
  display decisions and before normalization (`x = x - np.mean(x)`),
  otherwise the 0 Hz bin dominates the spectrogram.
- **0 Hz (or negative) notch input**: reject with `FilterConfigError`
  (iirnotch w0 must be in (0, Nyquist)).
- **Two notch frequencies very close together** (e.g. 100 Hz and 102 Hz
  at Q=30): the notches overlap and carve a wider band. This is allowed,
  but dedupe EXACT duplicates and consider warning in the log panel when
  |f1 - f2| < f1/Q.
- **44.1 kHz vs 48 kHz**: Nyquist differs (22050 vs 24000 Hz) — a 23 kHz
  notch is valid at 48 kHz and an ERROR at 44.1 kHz. Never hardcode a
  sample rate; always thread the actual `fs` from the decoded file.
  Fixture coverage exists for both rates in tests/fixtures/.

## General

- All core DSP functions: pure, typed, docstring'd, no PySide6 imports.
- Operate on float64 internally; convert at the boundaries.
- Use the committed fixtures (tests/fixtures/) for regression tests:
  a notch at 440 Hz on tone_440hz_48k.wav must reduce that bin's energy
  by tens of dB while leaving distant bins nearly untouched.
