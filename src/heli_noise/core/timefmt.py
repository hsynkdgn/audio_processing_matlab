"""Time-string parsing and formatting.

The single shared helper for converting user-entered time strings
(mm:ss / hh:mm:ss with optional milliseconds) to float seconds — used by
both the ui layer and tests so validation behavior can never diverge.
"""

import re

from heli_noise.core.exceptions import InvalidTimeRangeError

#: Accepts "mm:ss", "hh:mm:ss", each with an optional ".mmm" fraction.
#: Minutes/seconds are bounded to 0-59; hours may be 1-2 digits.
TIME_RE = re.compile(r"^(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?:\.(\d{1,3}))?$")


def parse_time(text: str) -> float:
    """Convert a time string to seconds.

    Args:
        text: Time in ``mm:ss`` or ``hh:mm:ss`` form, optionally with a
            fractional part (e.g. ``"01:23"``, ``"1:02:03"``, ``"00:05.500"``).

    Returns:
        The time in seconds as a float.

    Raises:
        InvalidTimeRangeError: If ``text`` does not match the accepted
            time format.
    """
    match = TIME_RE.match(text.strip())
    if match is None:
        raise InvalidTimeRangeError(f"Invalid time format: {text!r} (expected mm:ss or hh:mm:ss)")
    hours, minutes, seconds, fraction = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours is not None:
        total += int(hours) * 3600
    if fraction is not None:
        total += float(f"0.{fraction}")
    return float(total)


def format_seconds(seconds: float) -> str:
    """Format seconds as ``hh:mm:ss.mmm`` (hours omitted when zero).

    Args:
        seconds: Non-negative time in seconds.

    Returns:
        A string like ``"01:23.500"`` or ``"1:02:03.000"``.

    Raises:
        InvalidTimeRangeError: If ``seconds`` is negative.
    """
    if seconds < 0:
        raise InvalidTimeRangeError(f"Cannot format negative time: {seconds}")
    whole = int(seconds)
    millis = round((seconds - whole) * 1000)
    if millis == 1000:  # rounding overflow, e.g. 59.9996
        whole += 1
        millis = 0
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"
