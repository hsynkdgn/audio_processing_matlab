"""Matplotlib spectrogram embedding for the Qt UI.

Uses the backend_qtagg backend (compatible with PySide6); never calls
matplotlib.pyplot, which would spin up its own figure manager. Heavy
computation (STFT) happens in core.dsp / the worker thread — this widget
only renders already-computed matrices.
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from heli_noise.core.dsp import SpectrogramResult
from heli_noise.ui import strings, theme


class SpectrogramCanvas(FigureCanvasQTAgg):
    """A matplotlib canvas rendering a single :class:`SpectrogramResult`."""

    def __init__(self, title: str = "") -> None:
        figure = Figure(facecolor=theme.BACKGROUND)
        self._axes = figure.add_subplot(111)
        self._title = title
        super().__init__(figure)
        self._style_axes()

    def _style_axes(self) -> None:
        self._axes.set_facecolor(theme.BACKGROUND)
        self._axes.set_xlabel(strings.LABEL_SPECTROGRAM_TIME_AXIS, color=theme.TEXT)
        self._axes.set_ylabel(strings.LABEL_SPECTROGRAM_FREQ_AXIS, color=theme.TEXT)
        self._axes.tick_params(colors=theme.TEXT)
        if self._title:
            self._axes.set_title(self._title, color=theme.TEXT)

    def show_spectrogram(self, result: SpectrogramResult) -> None:
        """Render a spectrogram, replacing whatever was previously shown.

        Args:
            result: The spectrogram to display.
        """
        self._axes.clear()
        self._style_axes()
        self._axes.pcolormesh(result.times, result.frequencies, result.magnitude_db, shading="auto")
        self.draw_idle()

    def clear(self) -> None:
        """Remove any displayed spectrogram."""
        self._axes.clear()
        self._style_axes()
        self.draw_idle()
