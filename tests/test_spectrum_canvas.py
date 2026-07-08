"""Tests for ui.spectrum_canvas (headless via pytest-qt)."""

from pathlib import Path

from heli_noise.core.dsp import compute_spectrum
from heli_noise.core.media import load_wav
from heli_noise.ui import theme
from heli_noise.ui.spectrum_canvas import SpectrumPanel, format_cursor_readout, format_datatip

FIXTURES = Path(__file__).parent / "fixtures"


def _tone_spectrum():
    signal, fs = load_wav(FIXTURES / "tone_440hz_48k.wav")
    return compute_spectrum(signal, fs)


class _FakeEvent:
    """Minimal stand-in for a matplotlib MouseEvent."""

    def __init__(self, inaxes=None, xdata=None, ydata=None, button=1):
        self.inaxes = inaxes
        self.xdata = xdata
        self.ydata = ydata
        self.button = button


def test_show_spectrum_plots_a_line(qtbot) -> None:
    panel = SpectrumPanel(title="Before")
    qtbot.addWidget(panel)
    panel._peak_markers_checkbox.setChecked(False)  # isolate the curve itself

    panel.show_spectrum(_tone_spectrum())

    assert len(panel.canvas._axes.lines) == 1


def test_show_spectrum_twice_does_not_accumulate_lines(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)
    panel._peak_markers_checkbox.setChecked(False)  # isolate the curve itself
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

    panel._on_mouse_move(_FakeEvent(inaxes=None, xdata=None, ydata=None))
    assert panel._readout.text() == "— Hz, — dB"


def test_mouse_move_inside_axes_updates_readout(qtbot) -> None:
    panel = SpectrumPanel()
    qtbot.addWidget(panel)

    panel._on_mouse_move(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, ydata=-20.0))
    assert panel._readout.text() == "440.0 Hz, -20.0 dB"


class TestMatlabStyle:
    def test_line_uses_matlab_blue(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)

        panel.show_spectrum(_tone_spectrum())

        line = panel.canvas._axes.lines[0]
        assert line.get_color() == theme.PLOT_LINE

    def test_axes_background_is_white(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        assert panel.canvas._axes.get_facecolor() == (1.0, 1.0, 1.0, 1.0)


class TestDataTips:
    def test_left_click_on_axes_adds_a_datatip(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())

        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=1))

        assert len(panel.canvas._datatips) == 1

    def test_left_click_twice_adds_two_datatips(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())

        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=1))
        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=1000.0, button=1))

        assert len(panel.canvas._datatips) == 2

    def test_right_click_clears_all_datatips(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())
        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=1))

        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=3))

        assert panel.canvas._datatips == []

    def test_click_outside_axes_is_a_noop(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())

        panel._on_mouse_click(_FakeEvent(inaxes=None, xdata=None, button=1))

        assert panel.canvas._datatips == []

    def test_click_while_a_toolbar_tool_is_active_does_not_add_a_datatip(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())
        panel._toolbar.pan()  # activates zoom/pan mode

        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=1))

        assert panel.canvas._datatips == []

    def test_add_datatip_before_any_spectrum_is_a_noop(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)

        panel.canvas.add_datatip(440.0)

        assert panel.canvas._datatips == []

    def test_datatip_formatting(self) -> None:
        assert format_datatip(440.0, -12.34) == "Frequency: 440.0 Hz\nAmplitude: -12.3 dB"


class TestMinorGridToggle:
    def test_minor_grid_enabled_by_default(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        assert panel._minor_grid_checkbox.isChecked() is True
        assert panel.canvas._minor_grid_enabled is True

    def test_unchecking_disables_minor_grid(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)

        panel._minor_grid_checkbox.setChecked(False)

        assert panel.canvas._minor_grid_enabled is False


class TestPeakMarkers:
    def test_peak_markers_enabled_by_default_and_drawn_after_show(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        assert panel._peak_markers_checkbox.isChecked() is True

        panel.show_spectrum(_tone_spectrum())

        assert len(panel.canvas._peak_artists) > 0

    def test_unchecking_removes_peak_artists(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())
        assert len(panel.canvas._peak_artists) > 0

        panel._peak_markers_checkbox.setChecked(False)

        assert panel.canvas._peak_artists == []

    def test_rechecking_redraws_peak_artists(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())
        panel._peak_markers_checkbox.setChecked(False)

        panel._peak_markers_checkbox.setChecked(True)

        assert len(panel.canvas._peak_artists) > 0


class TestClearResetsEverything:
    def test_clear_also_removes_datatips_and_peaks(self, qtbot) -> None:
        panel = SpectrumPanel()
        qtbot.addWidget(panel)
        panel.show_spectrum(_tone_spectrum())
        panel._on_mouse_click(_FakeEvent(inaxes=panel.canvas._axes, xdata=440.0, button=1))
        assert len(panel.canvas._peak_artists) > 0
        assert len(panel.canvas._datatips) == 1

        panel.canvas.clear()

        assert panel.canvas._peak_artists == []
        assert panel.canvas._datatips == []
