"""Thin, core-independent adapter around sounddevice playback.

sounddevice cannot be exercised in the Linux cloud sandbox (no audio
device / PortAudio), so this module imports it lazily inside each method
rather than at module load time — importing this module must always
succeed headlessly. Real playback is a manual Windows test
(see docs/manual_test_windows.md); the adapter's own logic (state
tracking, error wrapping) is unit-tested here with a mocked sounddevice.
"""

from typing import Any

import numpy as np


class PlaybackError(Exception):
    """Raised when audio playback cannot be started or stopped."""


class PlaybackAdapter:
    """Wraps sounddevice.play/stop with a small, testable state machine."""

    def __init__(self) -> None:
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        """Whether playback is currently active."""
        return self._is_playing

    def play(self, data: np.ndarray, sample_rate: int) -> None:
        """Start playing a mono float signal through the default output device.

        Args:
            data: 1-D float samples in [-1, 1].
            sample_rate: Sample rate in Hz.

        Raises:
            PlaybackError: If sounddevice/PortAudio is unavailable or the
                backend refuses to start playback.
        """
        sd = self._import_sounddevice()
        try:
            sd.play(data, sample_rate)
        except sd.PortAudioError as exc:
            raise PlaybackError(f"Could not start playback: {exc}") from exc
        self._is_playing = True

    def stop(self) -> None:
        """Stop any playback in progress.

        Raises:
            PlaybackError: If sounddevice/PortAudio is unavailable or the
                backend refuses to stop.
        """
        sd = self._import_sounddevice()
        try:
            sd.stop()
        except sd.PortAudioError as exc:
            raise PlaybackError(f"Could not stop playback: {exc}") from exc
        finally:
            self._is_playing = False

    @staticmethod
    def _import_sounddevice() -> Any:
        try:
            import sounddevice as sd
        except OSError as exc:
            raise PlaybackError(f"Audio playback is unavailable: {exc}") from exc
        return sd
