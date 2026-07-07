"""Thin, core-independent adapter around sounddevice playback.

Built on ``sounddevice.OutputStream`` with a pull callback so the UI can
read the current playback position and seek while playing (the plain
``sd.play`` API is fire-and-forget and supports neither).

sounddevice cannot be exercised in the Linux cloud sandbox (no audio
device / PortAudio), so this module imports it lazily inside each method
rather than at module load time — importing this module must always
succeed headlessly. Real playback is a manual Windows test
(see docs/manual_test_windows.md); the adapter's own logic (position
tracking, seeking, error wrapping) is unit-tested with a mocked
sounddevice.
"""

import threading
from typing import Any

import numpy as np


class PlaybackError(Exception):
    """Raised when audio playback cannot be started, stopped, or seeked."""


class PlaybackAdapter:
    """Seekable playback of a mono float signal via sounddevice.

    The stream callback reads from ``self._data`` at ``self._position``
    (a sample index); seeking simply moves that index under a lock, so it
    works both while playing and while stopped.
    """

    def __init__(self) -> None:
        self._stream: Any = None
        self._data: np.ndarray | None = None
        self._sample_rate: int = 0
        self._position: int = 0
        self._lock = threading.Lock()

    # -- state ------------------------------------------------------------

    @property
    def is_playing(self) -> bool:
        """Whether a stream is currently open and active."""
        return self._stream is not None and bool(self._stream.active)

    @property
    def duration_seconds(self) -> float:
        """Length of the loaded signal in seconds (0.0 when nothing loaded)."""
        if self._data is None or self._sample_rate <= 0:
            return 0.0
        return len(self._data) / self._sample_rate

    @property
    def position_seconds(self) -> float:
        """Current playback position in seconds."""
        if self._sample_rate <= 0:
            return 0.0
        with self._lock:
            return self._position / self._sample_rate

    # -- control ----------------------------------------------------------

    def play(self, data: np.ndarray, sample_rate: int, start_s: float = 0.0) -> None:
        """Start playing a mono float signal through the default output device.

        Input is clipped to [-1, 1] as a safety net: the un-normalized
        "before" signal can slightly exceed the range after DC removal,
        and out-of-range samples would distort at the device.

        Args:
            data: 1-D float samples, nominally in [-1, 1].
            sample_rate: Sample rate in Hz.
            start_s: Position to start from, in seconds (clamped to the
                signal's duration).

        Raises:
            PlaybackError: If sounddevice/PortAudio is unavailable or the
                backend refuses to start playback.
        """
        sd = self._import_sounddevice()
        self.stop()

        clipped = np.clip(np.asarray(data, dtype=np.float32), -1.0, 1.0)
        with self._lock:
            self._data = clipped
            self._sample_rate = int(sample_rate)
            self._position = min(max(int(start_s * sample_rate), 0), len(clipped))

        try:
            stream = sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                callback=self._stream_callback,
                finished_callback=self._on_stream_finished,
            )
            stream.start()
        except sd.PortAudioError as exc:
            raise PlaybackError(f"Could not start playback: {exc}") from exc
        self._stream = stream

    def stop(self) -> None:
        """Stop playback and release the output stream (no-op when idle).

        Raises:
            PlaybackError: If the backend refuses to stop.
        """
        stream = self._stream
        if stream is None:
            return
        sd = self._import_sounddevice()
        self._stream = None
        try:
            stream.stop()
            stream.close()
        except sd.PortAudioError as exc:
            raise PlaybackError(f"Could not stop playback: {exc}") from exc

    def seek(self, seconds: float) -> None:
        """Move the playback position (effective immediately if playing).

        Args:
            seconds: Target position; clamped to [0, duration].
        """
        if self._data is None or self._sample_rate <= 0:
            return
        with self._lock:
            self._position = min(max(int(seconds * self._sample_rate), 0), len(self._data))

    # -- internals ----------------------------------------------------------

    def _stream_callback(self, outdata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        """Feed the next block from the buffer; zero-pad and finish at the end."""
        sd = self._import_sounddevice()
        with self._lock:
            data = self._data
            start = self._position
            if data is None:
                outdata[:] = 0
                raise sd.CallbackStop
            chunk = data[start : start + frames]
            self._position = start + len(chunk)
        outdata[: len(chunk), 0] = chunk
        if len(chunk) < frames:
            outdata[len(chunk) :, 0] = 0
            raise sd.CallbackStop

    def _on_stream_finished(self) -> None:
        """Drop the stream reference once the backend reports completion."""
        self._stream = None

    @staticmethod
    def _import_sounddevice() -> Any:
        try:
            import sounddevice as sd
        except OSError as exc:
            raise PlaybackError(f"Audio playback is unavailable: {exc}") from exc
        return sd
