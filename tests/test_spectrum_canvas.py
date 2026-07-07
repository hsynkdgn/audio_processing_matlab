"""Tests for ui.spectrum_canvas (headless via pytest-qt)."""

from pathlib import Path

from heli_noise.core.dsp import compute_spectrum
from heli_noise.core.media import load_wav
from heli_noise.ui.spectrum_canvas import SpectrumPanel, format_cursor_readout

FIXTURES = Path(__file__).parent / "fixtures"


def _tone_spectrum():
    signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
    return compute_spectrum(signal, fs)


def test_show_spectrum_plots_a_line(qtbot) -> None:
    panel = SpectrumPanel(title="Before")
    qtbot.addWidget(panel)

    panel.show_spectrum(_tone_spectrum())

    assert len(panel.canvas._axes.lines) == 1


def test_show_spectrum_twice_does_not_accumulate_lines(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)
    spectrum = _tone_spectrum()

    panel.show_spectrum(spectrum)
    panel.show_spectrum(spectrum)

    assert len(panel.canvas._axes.lines) == 1


def test_clear_removes_the_line(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)
    panel.show_spectrum(_tone_spectrum())

    panel.canvas.clear()

    assert len(panel.canvas._axes.lines) == 0


def test_panel_has_navigation_toolbar_and_readout(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)
    assert panel._toolbar is not None  # zoom/pan/reset interactivity
    assert panel._readout.text() == "— Hz, — dB"


def test_cursor_readout_formatting() -> None:
    assert format_cursor_readout(440.0, -12.34) == "440.0 Hz, -12.3 dB"
    assert format_cursor_readout(1234.56, 3.0) == "1234.6 Hz, 3.0 dB"


def test_mouse_move_outside_axes_resets_readout(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)

    class _FakeEvent:
        inaxes = None
        xdata = None
        ydata = None

    panel._on_mouse_move(_FakeEvent())
    assert panel._readout.text() == "— Hz, — dB"


def test_mouse_move_inside_axes_updates_readout(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)

    class _FakeEvent:
        inaxes = panel.canvas._axes
        xdata = 440.0
        ydata = -20.0

    panel._on_mouse_move(_FakeEvent())
    assert panel._readout.text() == "440.0 Hz, -20.0 dB"
