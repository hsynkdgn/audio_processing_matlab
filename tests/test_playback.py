"""Tests for ui.playback.PlaybackAdapter.

Real playback needs a physical audio device and cannot be exercised here
(see docs/manual_test_windows.md); these tests mock sounddevice to verify
the adapter's own state-tracking and error-wrapping logic.
"""

import builtins
import sys
import types

import numpy as np
import pytest

from heli_noise.ui.playback import PlaybackAdapter, PlaybackError


class _FakePortAudioError(Exception):
    pass


def _install_fake_sounddevice(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    fake = types.ModuleType("sounddevice")
    fake.PortAudioError = _FakePortAudioError
    fake.play = lambda data, sample_rate: None
    fake.stop = lambda: None
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    return fake


def test_play_starts_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sd = _install_fake_sounddevice(monkeypatch)
    calls = []
    fake_sd.play = lambda data, sample_rate: calls.append((data, sample_rate))

    adapter = PlaybackAdapter()
    data = np.zeros(100)
    adapter.play(data, 48_000)

    assert adapter.is_playing is True
    assert len(calls) == 1
    assert calls[0][1] == 48_000


def test_play_wraps_portaudio_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sd = _install_fake_sounddevice(monkeypatch)

    def _raise(data, sample_rate):
        raise fake_sd.PortAudioError("device busy")

    fake_sd.play = _raise

    adapter = PlaybackAdapter()
    with pytest.raises(PlaybackError, match="Could not start playback"):
        adapter.play(np.zeros(10), 48_000)
    assert adapter.is_playing is False


def test_stop_stops_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sd = _install_fake_sounddevice(monkeypatch)
    stop_calls = []
    fake_sd.stop = lambda: stop_calls.append(True)

    adapter = PlaybackAdapter()
    adapter.play(np.zeros(10), 48_000)
    assert adapter.is_playing is True

    adapter.stop()

    assert adapter.is_playing is False
    assert stop_calls == [True]


def test_stop_wraps_portaudio_error_and_still_clears_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sd = _install_fake_sounddevice(monkeypatch)
    adapter = PlaybackAdapter()
    adapter.play(np.zeros(10), 48_000)

    def _raise():
        raise fake_sd.PortAudioError("no active stream")

    fake_sd.stop = _raise

    with pytest.raises(PlaybackError, match="Could not stop playback"):
        adapter.stop()
    assert adapter.is_playing is False  # cleared even though stop() raised


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
