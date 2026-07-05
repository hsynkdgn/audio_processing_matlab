"""Tests for ui.spectrogram_canvas.SpectrogramCanvas (headless via pytest-qt)."""

from pathlib import Path

from heli_noise.core.dsp import compute_spectrogram
from heli_noise.core.media import load_wav
from heli_noise.ui.spectrogram_canvas import SpectrogramCanvas

FIXTURES = Path(__file__).parent / "fixtures"


def test_show_spectrogram_adds_a_mesh(qtbot) -> None:
    canvas = SpectrogramCanvas(title="Before")
    qtbot.addWidget(canvas)
    signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
    result = compute_spectrogram(signal, fs)

    canvas.show_spectrogram(result)

    assert len(canvas._axes.collections) >= 1


def test_clear_removes_the_mesh(qtbot) -> None:
    canvas = SpectrogramCanvas()
    qtbot.addWidget(canvas)
    signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
    canvas.show_spectrogram(compute_spectrogram(signal, fs))

    canvas.clear()

    assert len(canvas._axes.collections) == 0


def test_show_spectrogram_twice_does_not_accumulate_meshes(qtbot) -> None:
    canvas = SpectrogramCanvas()
    qtbot.addWidget(canvas)
    signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
    result = compute_spectrogram(signal, fs)

    canvas.show_spectrogram(result)
    canvas.show_spectrogram(result)

    assert len(canvas._axes.collections) == 1
