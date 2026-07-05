"""Tests for core.timefmt — the shared time-string helper."""

import pytest

from heli_noise.core.exceptions import InvalidTimeRangeError
from heli_noise.core.timefmt import format_seconds, parse_time


class TestParseTime:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("00:00", 0.0),
            ("01:23", 83.0),
            ("59:59", 3599.0),
            ("1:02:03", 3723.0),
            ("12:00:00", 43200.0),
            ("00:05.500", 5.5),
            ("1:02:03.250", 3723.25),
            ("  01:23  ", 83.0),  # surrounding whitespace tolerated
        ],
    )
    def test_valid(self, text: str, expected: float) -> None:
        assert parse_time(text) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "text",
        ["", "99", "1:99:00", "00:60", "abc", "1:2:3:4", "-01:00", "01:23,500"],
    )
    def test_invalid_raises(self, text: str) -> None:
        with pytest.raises(InvalidTimeRangeError):
            parse_time(text)


class TestFormatSeconds:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0.0, "00:00.000"),
            (83.0, "01:23.000"),
            (5.5, "00:05.500"),
            (3723.25, "1:02:03.250"),
            (59.9996, "01:00.000"),  # millisecond rounding overflow
        ],
    )
    def test_valid(self, seconds: float, expected: str) -> None:
        assert format_seconds(seconds) == expected

    def test_negative_raises(self) -> None:
        with pytest.raises(InvalidTimeRangeError):
            format_seconds(-1.0)

    def test_roundtrip(self) -> None:
        assert parse_time(format_seconds(3723.25)) == pytest.approx(3723.25)
