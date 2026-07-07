"""Tests for ui.playback.PlaybackAdapter (seekable OutputStream version).

Real playback needs a physical audio device and cannot be exercised here
(see docs/manual_test_windows.md); these tests mock sounddevice with a
fake OutputStream whose callback we drive by hand, verifying the
adapter's position tracking, seeking, clipping, and error wrapping.
"""

import builtins
import sys
import types

import numpy as np
import pytest

from heli_noise.ui.playback import PlaybackAdapter, PlaybackError


class _FakePortAudioError(Exception):
    pass


class _FakeCallbackStop(Exception):
    pass


class _FakeOutputStream:
    """Captures the callback and lets tests pump audio blocks manually."""

    def __init__(self, samplerate, channels, dtype, callback, finished_callback):
        self.samplerate = samplerate
        self.channels = channels
        self.callback = callback
        self.finished_callback = finished_callback
        self.active = False
        self.raise_on_start: Exception | None = None
        self.raise_on_stop: Exception | None = None

    def start(self):
        if self.raise_on_start is not None:
            raise self.raise_on_start
        self.active = True

    def stop(self):
        if self.raise_on_stop is not None:
            raise self.raise_on_stop
        self.active = False

    def close(self):
        self.active = False

    def pump(self, frames: int) -> np.ndarray:
        """Invoke the callback like PortAudio would; returns the block."""
        outdata = np.zeros((frames, 1), dtype=np.float32)
        try:
            self.callback(outdata, frames, None, None)
        except _FakeCallbackStop:
            self.active = False
            self.finished_callback()
        return outdata


def _install_fake_sounddevice(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    fake = types.ModuleType("sounddevice")
    fake.PortAudioError = _FakePortAudioError
    fake.CallbackStop = _FakeCallbackStop
    fake.streams: list[_FakeOutputStream] = []

    def _make_stream(**kwargs):
        stream = _FakeOutputStream(**kwargs)
        fake.streams.append(stream)
        return stream

    fake.OutputStream = _make_stream
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    return fake


def test_play_starts_stream_and_reports_state(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(48_000), 48_000)

    assert adapter.is_playing is True
    assert adapter.duration_seconds == pytest.approx(1.0)
    assert adapter.position_seconds == pytest.approx(0.0)
    assert len(fake.streams) == 1


def test_position_advances_as_callback_consumes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    signal = np.linspace(-0.5, 0.5, 48_000)
    adapter.play(signal, 48_000)

    block = fake.streams[0].pump(4_800)  # 0.1 s

    assert adapter.position_seconds == pytest.approx(0.1)
    assert np.allclose(block[:, 0], signal[:4_800].astype(np.float32))


def test_playback_finishes_at_end_of_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(1_000), 48_000)

    fake.streams[0].pump(4_800)  # larger than the signal -> CallbackStop

    assert adapter.is_playing is False
    assert adapter.position_seconds == pytest.approx(1_000 / 48_000)


def test_seek_moves_position_mid_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    signal = np.arange(48_000, dtype=np.float64) / 48_000
    adapter.play(signal, 48_000)
    fake.streams[0].pump(4_800)

    adapter.seek(0.5)

    assert adapter.position_seconds == pytest.approx(0.5)
    block = fake.streams[0].pump(10)
    assert block[0, 0] == pytest.approx(signal[24_000], abs=1e-6)


def test_seek_clamps_to_valid_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(48_000), 48_000)

    adapter.seek(-5.0)
    assert adapter.position_seconds == pytest.approx(0.0)
    adapter.seek(99.0)
    assert adapter.position_seconds == pytest.approx(1.0)


def test_seek_before_any_play_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.seek(1.0)  # must not raise
    assert adapter.position_seconds == pytest.approx(0.0)


def test_play_from_start_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(48_000), 48_000, start_s=0.25)
    assert adapter.position_seconds == pytest.approx(0.25)


def test_play_clips_out_of_range_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """The un-normalized 'before' signal can exceed [-1, 1] after DC removal."""
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.array([1.3, -1.7, 0.5]), 48_000)

    block = fake.streams[0].pump(3)

    assert np.max(np.abs(block)) <= 1.0
    assert block[2, 0] == pytest.approx(0.5)


def test_restarting_play_stops_previous_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(100), 48_000)
    first = fake.streams[0]

    adapter.play(np.zeros(100), 48_000)

    assert first.active is False
    assert len(fake.streams) == 2
    assert adapter.is_playing is True


def test_stop_when_idle_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.stop()  # must not raise


def test_play_wraps_portaudio_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    original_factory = fake.OutputStream

    def _failing_stream(**kwargs):
        stream = original_factory(**kwargs)
        stream.raise_on_start = _FakePortAudioError("device busy")
        return stream

    fake.OutputStream = _failing_stream

    adapter = PlaybackAdapter()
    with pytest.raises(PlaybackError, match="Could not start playback"):
        adapter.play(np.zeros(10), 48_000)
    assert adapter.is_playing is False


def test_stop_wraps_portaudio_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(10), 48_000)
    fake.streams[0].raise_on_stop = _FakePortAudioError("no active stream")

    with pytest.raises(PlaybackError, match="Could not stop playback"):
        adapter.stop()
    assert adapter.is_playing is False  # reference dropped even on failure


def test_unavailable_backend_raises_playback_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates the real sandbox failure: PortAudio missing at import time."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "sounddevice", raising=False)

    adapter = PlaybackAdapter()
    with pytest.raises(PlaybackError, match="unavailable"):
        adapter.play(np.zeros(10), 48_000)
    assert adapter.is_playing is False
