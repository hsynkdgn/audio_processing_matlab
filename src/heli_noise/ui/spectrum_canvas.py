"""Interactive frequency-amplitude spectrum plot for the Qt UI.

Styled after MATLAB's default ``plot`` look (white axes, MATLAB blue line,
light grid, boxed axes) per user request, so the before/after spectra read
the way a MATLAB user expects. On top of the standard matplotlib
navigation toolbar (zoom/pan/reset) this adds three MATLAB-style
inspection tools:

- **Data tips**: left-click the curve to pin a callout with the exact
  Hz/dB at the nearest sample (MATLAB's ``datacursormode``); right-click
  clears all pinned tips. Suppressed while a toolbar zoom/pan tool is
  active so clicks aren't fought over.
- **Minor grid**: toggleable fine gridlines (MATLAB's ``grid minor``).
- **Peak markers**: toggleable auto-detected spectral peaks (rotor
  fundamental/harmonics), reusing core.dsp.find_spectrum_peaks.

Heavy computation happens in core.dsp / the worker thread — this widget
only renders ready-made spectra and derives peak markers from them.

Uses the backend_qtagg backend (compatible with PySide6); never calls
matplotlib.pyplot, which would spin up its own figure manager.
"""

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from heli_noise.core.dsp import SpectrumResult, find_spectrum_peaks
from heli_noise.ui import strings, theme


def format_cursor_readout(frequency_hz: float, magnitude_db: float) -> str:
    """Format the hover readout text (shared with tests)."""
    return strings.SPECTRUM_CURSOR_READOUT.format(frequency=frequency_hz, magnitude=magnitude_db)


def format_datatip(frequency_hz: float, magnitude_db: float) -> str:
    """Format a pinned data-tip callout's text (shared with tests)."""
    return strings.SPECTRUM_DATATIP.format(frequency=frequency_hz, magnitude=magnitude_db)


class SpectrumCanvas(FigureCanvasQTAgg):
    """A matplotlib canvas rendering a single :class:`SpectrumResult`."""

    def __init__(self, title: str = "") -> None:
        figure = Figure(facecolor=theme.PLOT_BG)
        self._axes = figure.add_subplot(111)
        self._title = title
        self._frequencies: np.ndarray | None = None
        self._magnitude_db: np.ndarray | None = None
        self._minor_grid_enabled = True
        self._peak_markers_enabled = True
        self._datatips: list[tuple] = []
        self._peak_artists: list = []
        super().__init__(figure)
        self._style_axes()

    def _style_axes(self) -> None:
        """Apply the MATLAB-style light look (grid state re-applied every
        time, since `Axes.clear()` wipes it along with everything else)."""
        self._axes.set_facecolor(theme.PLOT_BG)
        self._axes.set_xlabel(strings.LABEL_SPECTRUM_FREQ_AXIS, color=theme.PLOT_TEXT)
        self._axes.set_ylabel(strings.LABEL_SPECTRUM_AMPLITUDE_AXIS, color=theme.PLOT_TEXT)
        self._axes.tick_params(colors=theme.PLOT_TEXT, direction="in", which="both")
        self._axes.grid(True, which="major", color=theme.PLOT_GRID, linewidth=0.6)
        if self._minor_grid_enabled:
            self._axes.minorticks_on()
            self._axes.grid(True, which="minor", color=theme.PLOT_GRID_MINOR, linewidth=0.4)
        else:
            self._axes.minorticks_off()
        for spine in self._axes.spines.values():
            spine.set_color(theme.PLOT_AXES)
            spine.set_linewidth(0.8)
        if self._title:
            self._axes.set_title(self._title, color=theme.PLOT_TEXT)

    def show_spectrum(self, result: SpectrumResult) -> None:
        """Render a spectrum, replacing whatever was previously shown.

        Args:
            result: The spectrum to display.
        """
        self._axes.clear()
        self._datatips = []
        self._peak_artists = []
        self._frequencies = result.frequencies
        self._magnitude_db = result.magnitude_db
        self._style_axes()
        self._axes.plot(
            result.frequencies, result.magnitude_db, color=theme.PLOT_LINE, linewidth=1.0
        )
        self._axes.set_xlim(float(result.frequencies[0]), float(result.frequencies[-1]))
        self._draw_peaks()
        self.draw_idle()

    def clear(self) -> None:
        """Remove any displayed spectrum, data tips, and peak markers."""
        self._axes.clear()
        self._frequencies = None
        self._magnitude_db = None
        self._datatips = []
        self._peak_artists = []
        self._style_axes()
        self.draw_idle()

    def set_minor_grid_enabled(self, enabled: bool) -> None:
        """Toggle the MATLAB-style fine gridlines (``grid minor``)."""
        self._minor_grid_enabled = enabled
        self._style_axes()
        self.draw_idle()

    def set_peak_markers_enabled(self, enabled: bool) -> None:
        """Toggle auto-detected spectral peak markers/labels."""
        self._peak_markers_enabled = enabled
        self._draw_peaks()
        self.draw_idle()

    def add_datatip(self, x_data: float) -> None:
        """Pin a data tip at the sample nearest ``x_data`` (MATLAB-style
        click-to-inspect). No-op if no spectrum is currently displayed."""
        if self._frequencies is None or self._magnitude_db is None:
            return
        if len(self._frequencies) == 0:
            return
        index = int(np.argmin(np.abs(self._frequencies - x_data)))
        frequency = float(self._frequencies[index])
        magnitude = float(self._magnitude_db[index])

        (marker,) = self._axes.plot(
            [frequency],
            [magnitude],
            marker="o",
            markersize=5,
            markerfacecolor=theme.PLOT_BG,
            markeredgecolor=theme.PLOT_TEXT,
            zorder=5,
        )
        annotation = self._axes.annotate(
            format_datatip(frequency, magnitude),
            xy=(frequency, magnitude),
            xytext=(12, 12),
            textcoords="offset points",
            fontsize=8,
            color=theme.PLOT_TEXT,
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": theme.PLOT_DATATIP_BG,
                "edgecolor": theme.PLOT_TEXT,
                "linewidth": 0.6,
            },
            arrowprops={"arrowstyle": "-", "color": theme.PLOT_TEXT, "linewidth": 0.6},
            zorder=6,
        )
        self._datatips.append((marker, annotation))
        self.draw_idle()

    def clear_datatips(self) -> None:
        """Remove every pinned data tip."""
        for marker, annotation in self._datatips:
            marker.remove()
            annotation.remove()
        self._datatips = []
        self.draw_idle()

    def _draw_peaks(self) -> None:
        for artist in self._peak_artists:
            artist.remove()
        self._peak_artists = []
        if (
            not self._peak_markers_enabled
            or self._frequencies is None
            or self._magnitude_db is None
        ):
            return
        peaks = find_spectrum_peaks(
            SpectrumResult(frequencies=self._frequencies, magnitude_db=self._magnitude_db)
        )
        for peak in peaks:
            (marker,) = self._axes.plot(
                [peak.frequency],
                [peak.magnitude_db],
                marker="v",
                markersize=6,
                color=theme.PLOT_PEAK,
                linestyle="none",
                zorder=4,
            )
            label = self._axes.annotate(
                strings.SPECTRUM_PEAK_LABEL.format(frequency=peak.frequency),
                xy=(peak.frequency, peak.magnitude_db),
                xytext=(0, 8),
                textcoords="offset points",
                fontsize=7,
                color=theme.PLOT_PEAK,
                ha="center",
                zorder=4,
            )
            self._peak_artists.append(marker)
            self._peak_artists.append(label)


class SpectrumPanel(QWidget):
    """SpectrumCanvas + navigation toolbar + MATLAB-style inspection tools.

    Adds, alongside the standard zoom/pan/reset toolbar: a live hover
    readout, click-to-pin data tips, and checkboxes toggling the minor
    grid and peak markers.
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = SpectrumCanvas(title=title)
        self._toolbar = NavigationToolbar2QT(self.canvas, self)
        self._readout = QLabel(strings.SPECTRUM_CURSOR_EMPTY)
        self._readout.setStyleSheet(f"color: {theme.READOUT};")
        self._readout.setToolTip(strings.SPECTRUM_CURSOR_TOOLTIP)

        self._minor_grid_checkbox = QCheckBox(strings.CHECKBOX_MINOR_GRID)
        self._minor_grid_checkbox.setChecked(True)
        self._minor_grid_checkbox.toggled.connect(self.canvas.set_minor_grid_enabled)

        self._peak_markers_checkbox = QCheckBox(strings.CHECKBOX_PEAK_MARKERS)
        self._peak_markers_checkbox.setChecked(True)
        self._peak_markers_checkbox.toggled.connect(self.canvas.set_peak_markers_enabled)

        controls_row = QHBoxLayout()
        controls_row.addWidget(self._toolbar)
        controls_row.addStretch(1)
        controls_row.addWidget(self._minor_grid_checkbox)
        controls_row.addWidget(self._peak_markers_checkbox)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls_row)
        layout.addWidget(self.canvas)
        layout.addWidget(self._readout)

        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.canvas.mpl_connect("button_press_event", self._on_mouse_click)

    def show_spectrum(self, result: SpectrumResult) -> None:
        """Render a spectrum in the embedded canvas."""
        self.canvas.show_spectrum(result)

    def _on_mouse_move(self, event) -> None:
        """Update the readout with the frequency/amplitude under the cursor."""
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            self._readout.setText(strings.SPECTRUM_CURSOR_EMPTY)
            return
        self._readout.setText(format_cursor_readout(event.xdata, event.ydata))

    def _on_mouse_click(self, event) -> None:
        """Left-click pins a data tip, right-click clears them all.

        Ignored while a toolbar zoom/pan tool is active so clicks keep
        doing what the toolbar button promises instead of also dropping
        a data tip underneath.
        """
        if event.inaxes is None or event.xdata is None:
            return
        if self._toolbar.mode:
            return
        if event.button == 1:
            self.canvas.add_datatip(event.xdata)
        elif event.button == 3:
            self.canvas.clear_datatips()
