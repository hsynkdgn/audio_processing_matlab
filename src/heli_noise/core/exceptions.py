"""Dedicated exception classes for the core layer.

The ui layer catches these and converts them into status icons (✓/✗) and
log-panel messages; core functions never raise bare built-in exceptions
for expected failure modes.
"""


class HeliNoiseError(Exception):
    """Base class for all application-specific errors."""


class MediaDecodeError(HeliNoiseError):
    """Raised when a media file cannot be probed or decoded.

    Covers: missing/unreadable input file, no audio stream, unparsable
    ffmpeg output, and non-zero ffmpeg exit codes.
    """


class InvalidTimeRangeError(HeliNoiseError):
    """Raised when a requested time value or interval is invalid.

    Covers: malformed hh:mm:ss input, negative start, stop <= start, and
    intervals extending past the media duration.
    """


class FilterConfigError(HeliNoiseError):
    """Raised when a filter configuration is invalid.

    Covers: notch frequency <= 0 or >= Nyquist, invalid Q, and invalid
    STFT parameters (e.g. noverlap >= nperseg). Never silently clamp —
    the user must be told.
    """
