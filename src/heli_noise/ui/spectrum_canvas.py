"""Interactive frequency-amplitude spectrum plot for the Qt UI.

A matplotlib line plot (frequency -> dB) with the standard navigation
toolbar (zoom/pan/reset) and a live cursor readout showing the frequency
and amplitude under the mouse. Heavy computation happens in core.dsp /
the worker thread — this widget only renders ready-made spectra.

Uses the backend_qtagg backend (compatible with PySide6); never calls
matplotlib.pyplot, which would spin up its own figure manager.
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from heli_noise.core.dsp import SpectrumResult
from heli_noise.ui import strings, theme


def format_cursor_readout(frequency_hz: float, magnitude_db: float) -> str:
    """Format the hover readout text (shared with tests)."""
    return strings.SPECTRUM_CURSOR_READOUT.format(frequency=frequency_hz, magnitude=magnitude_db)


class SpectrumCanvas(FigureCanvasQTAgg):
    """A matplotlib canvas rendering a single :class:`SpectrumResult`."""

    def __init__(self, title: str = "") -> None:
        figure = Figure(facecolor=theme.BACKGROUND)
        self._axes = figure.add_subplot(111)
        self._title = title
        super().__init__(figure)
        self._style_axes()

    def _style_axes(self) -> None:
        self._axes.set_facecolor(theme.BACKGROUND)
        self._axes.set_xlabel(strings.LABEL_SPECTRUM_FREQ_AXIS, color=theme.TEXT)
        self._axes.set_ylabel(strings.LABEL_SPECTRUM_AMPLITUDE_AXIS, color=theme.TEXT)
        self._axes.tick_params(colors=theme.TEXT)
        self._axes.grid(True, color=theme.BORDER, linewidth=0.5, alpha=0.6)
        for spine in self._axes.spines.values():
            spine.set_color(theme.BORDER)
        if self._title:
            self._axes.set_title(self._title, color=theme.TEXT)

    def show_spectrum(self, result: SpectrumResult) -> None:
        """Render a spectrum, replacing whatever was previously shown.

        Args:
            result: The spectrum to display.
        """
        self._axes.clear()
        self._style_axes()
        self._axes.plot(result.frequencies, result.magnitude_db, color=theme.READOUT, linewidth=0.9)
        self._axes.set_xlim(float(result.frequencies[0]), float(result.frequencies[-1]))
        self.draw_idle()

    def clear(self) -> None:
        """Remove any displayed spectrum."""
        self._axes.clear()
        self._style_axes()
        self.draw_idle()


class SpectrumPanel(QWidget):
    """SpectrumCanvas + navigation toolbar + live cursor readout label."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = SpectrumCanvas(title=title)
        self._toolbar = NavigationToolbar2QT(self.canvas, self)
        self._readout = QLabel(strings.SPECTRUM_CURSOR_EMPTY)
        self._readout.setStyleSheet(f"color: {theme.READOUT};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self._readout)

        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)

    def show_spectrum(self, result: SpectrumResult) -> None:
        """Render a spectrum in the embedded canvas."""
        self.canvas.show_spectrum(result)

    def _on_mouse_move(self, event) -> None:
        """Update the readout with the frequency/amplitude under the cursor."""
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            self._readout.setText(strings.SPECTRUM_CURSOR_EMPTY)
            return
        self._readout.setText(format_cursor_readout(event.xdata, event.ydata))
