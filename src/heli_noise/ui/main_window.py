"""MainWindow: assembles the file picker, time/notch inputs, before/after
spectrogram canvases, playback controls, status icons, and log panel.

Wires user actions to core.pipeline.process_recording via a background
QThread (ui.worker) so the UI thread is never blocked; core exceptions
are caught here and converted into status icons + log messages, never
into popups showing raw exception text.
"""

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from heli_noise.core.dsp import parse_frequency_list
from heli_noise.core.exceptions import FilterConfigError, InvalidTimeRangeError
from heli_noise.core.pipeline import ProcessResult, process_recording
from heli_noise.core.timefmt import parse_time
from heli_noise.ui import strings, theme
from heli_noise.ui.playback import PlaybackAdapter, PlaybackError
from heli_noise.ui.spectrogram_canvas import SpectrogramCanvas
from heli_noise.ui.status_icon import StatusIcon
from heli_noise.ui.worker import QThread, Worker, start_worker


class MainWindow(QMainWindow):
    """The application's single window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(strings.WINDOW_TITLE)
        self.setStyleSheet(theme.build_stylesheet())

        self._input_path: Path | None = None
        self._last_result: ProcessResult | None = None
        self._playback = PlaybackAdapter()
        self._thread: QThread | None = None
        self._worker: Worker | None = None

        self._build_ui()

    # -- construction ---------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addLayout(self._build_file_row())
        layout.addLayout(self._build_params_row())
        layout.addLayout(self._build_process_row())
        layout.addLayout(self._build_spectrogram_row())
        layout.addLayout(self._build_playback_row())
        layout.addWidget(QLabel(strings.LABEL_LOG_PANEL))
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        layout.addWidget(self._log_edit)

    def _build_file_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(strings.LABEL_INPUT_FILE))
        self._file_edit = QLineEdit()
        self._file_edit.setReadOnly(True)
        row.addWidget(self._file_edit)
        browse_button = QPushButton(strings.BUTTON_BROWSE)
        browse_button.clicked.connect(self._on_browse_clicked)
        row.addWidget(browse_button)
        return row

    def _build_params_row(self) -> QGridLayout:
        grid = QGridLayout()
        grid.addWidget(QLabel(strings.LABEL_START_TIME), 0, 0)
        self._start_edit = QLineEdit()
        grid.addWidget(self._start_edit, 0, 1)
        grid.addWidget(QLabel(strings.LABEL_STOP_TIME), 0, 2)
        self._stop_edit = QLineEdit()
        grid.addWidget(self._stop_edit, 0, 3)
        grid.addWidget(QLabel(strings.LABEL_NOTCH_FREQUENCIES), 1, 0)
        self._notch_edit = QLineEdit()
        grid.addWidget(self._notch_edit, 1, 1, 1, 3)
        return grid

    def _build_process_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._process_button = QPushButton(strings.BUTTON_PROCESS)
        self._process_button.clicked.connect(self._on_process_clicked)
        row.addWidget(self._process_button)
        self._process_status = StatusIcon()
        row.addWidget(self._process_status)
        row.addStretch(1)
        return row

    def _build_spectrogram_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._before_canvas = SpectrogramCanvas(title=strings.LABEL_BEFORE_SPECTROGRAM)
        self._after_canvas = SpectrogramCanvas(title=strings.LABEL_AFTER_SPECTROGRAM)
        row.addWidget(self._before_canvas)
        row.addWidget(self._after_canvas)
        return row

    def _build_playback_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        play_before_button = QPushButton(strings.BUTTON_PLAY_BEFORE)
        play_before_button.clicked.connect(self._on_play_before_clicked)
        row.addWidget(play_before_button)
        self._play_before_status = StatusIcon()
        row.addWidget(self._play_before_status)

        play_after_button = QPushButton(strings.BUTTON_PLAY_AFTER)
        play_after_button.clicked.connect(self._on_play_after_clicked)
        row.addWidget(play_after_button)
        self._play_after_status = StatusIcon()
        row.addWidget(self._play_after_status)

        stop_button = QPushButton(strings.BUTTON_STOP_PLAYBACK)
        stop_button.clicked.connect(self._on_stop_playback_clicked)
        row.addWidget(stop_button)

        row.addStretch(1)
        return row

    # -- helpers ----------------------------------------------------------

    def _log(self, message: str) -> None:
        self._log_edit.appendPlainText(message)

    def _set_input_path(self, path: Path) -> None:
        """Apply a chosen input path (shared by the browse dialog and tests)."""
        self._input_path = path
        self._file_edit.setText(str(path))

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._process_button.setEnabled(enabled)

    # -- file selection ---------------------------------------------------

    def _on_browse_clicked(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self, strings.FILE_DIALOG_TITLE, "", strings.FILE_DIALOG_FILTER
        )
        if file_name:
            self._set_input_path(Path(file_name))

    # -- processing ---------------------------------------------------------

    def _on_process_clicked(self) -> None:
        if self._input_path is None:
            self._process_status.set_error(strings.ERROR_NO_INPUT_FILE)
            self._log(strings.ERROR_NO_INPUT_FILE)
            return

        try:
            start_s = parse_time(self._start_edit.text())
            stop_s = parse_time(self._stop_edit.text())
        except InvalidTimeRangeError as exc:
            message = strings.ERROR_INVALID_TIME_RANGE.format(error=exc)
            self._process_status.set_error(message)
            self._log(message)
            return

        try:
            frequencies = parse_frequency_list(self._notch_edit.text())
        except FilterConfigError as exc:
            message = strings.ERROR_INVALID_NOTCH_FREQUENCIES.format(error=exc)
            self._process_status.set_error(message)
            self._log(message)
            return

        output_path = self._input_path.parent / f"{self._input_path.stem}_filtered.wav"
        self._process_status.set_idle()
        self._log(strings.LOG_PROCESSING_STARTED)
        self._set_controls_enabled(False)
        self._thread, self._worker = start_worker(
            process_recording,
            self._input_path,
            start_s,
            stop_s,
            frequencies,
            output_path,
            on_finished=self._on_process_finished,
            on_failed=self._on_process_failed,
        )

    def _on_process_finished(self, result: ProcessResult) -> None:
        self._last_result = result
        self._process_status.set_ok()
        self._log(strings.LOG_PROCESSING_DONE.format(output_path=result.output_path))
        self._before_canvas.show_spectrogram(result.before_spectrogram)
        self._after_canvas.show_spectrogram(result.after_spectrogram)
        self._set_controls_enabled(True)

    def _on_process_failed(self, message: str) -> None:
        self._process_status.set_error(message)
        self._log(strings.LOG_PROCESSING_FAILED.format(error=message))
        self._set_controls_enabled(True)

    # -- playback ---------------------------------------------------------

    def _on_play_before_clicked(self) -> None:
        if self._last_result is None:
            return
        self._play(self._last_result.original_signal, self._play_before_status)

    def _on_play_after_clicked(self) -> None:
        if self._last_result is None:
            return
        self._play(self._last_result.processed_signal, self._play_after_status)

    def _play(self, signal: np.ndarray, status: StatusIcon) -> None:
        try:
            self._playback.play(signal, self._last_result.sample_rate)
        except PlaybackError as exc:
            status.set_error(str(exc))
            self._log(strings.LOG_PLAYBACK_FAILED.format(error=exc))
            return
        status.set_ok()

    def _on_stop_playback_clicked(self) -> None:
        try:
            self._playback.stop()
        except PlaybackError as exc:
            self._log(strings.LOG_PLAYBACK_FAILED.format(error=exc))
