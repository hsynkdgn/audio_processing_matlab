"""All user-facing UI strings. Hardcoded strings in widget code are forbidden."""

WINDOW_TITLE = "Helicopter Noise Analyzer"

LABEL_INPUT_FILE = "Recording file"
BUTTON_BROWSE = "Browse…"
FILE_DIALOG_TITLE = "Select a recording"
FILE_DIALOG_FILTER = "Audio/Video (*.mp4 *.mp3 *.wav);;All files (*)"

LABEL_START_TIME = "Start (hh:mm:ss)"
LABEL_STOP_TIME = "Stop (hh:mm:ss)"
LABEL_NOTCH_FREQUENCIES = "Notch frequencies (Hz, comma-separated)"

BUTTON_PROCESS = "Process"
BUTTON_PLAY_BEFORE = "Play before"
BUTTON_PLAY_AFTER = "Play after"
BUTTON_STOP_PLAYBACK = "Stop"

LABEL_BEFORE_SPECTRUM = "Before"
LABEL_AFTER_SPECTRUM = "After"
LABEL_SPECTRUM_FREQ_AXIS = "Frequency (Hz)"
LABEL_SPECTRUM_AMPLITUDE_AXIS = "Amplitude (dB)"
SPECTRUM_CURSOR_READOUT = "{frequency:.1f} Hz, {magnitude:.1f} dB"
SPECTRUM_CURSOR_EMPTY = "— Hz, — dB"

LABEL_SEEK_POSITION = "{position} / {duration}"

LABEL_LOG_PANEL = "Log"

STATUS_TOOLTIP_IDLE = "Not run yet"
STATUS_TOOLTIP_OK = "Completed successfully"

LOG_PROCESSING_STARTED = "Processing started…"
LOG_PROCESSING_DONE = "Processing complete: {output_path}"
LOG_PROCESSING_FAILED = "Processing failed: {error}"
LOG_PLAYBACK_FAILED = "Playback failed: {error}"

ERROR_NO_INPUT_FILE = "Choose a recording file first."
ERROR_INVALID_TIME_RANGE = "Invalid time range: {error}"
ERROR_INVALID_NOTCH_FREQUENCIES = "Invalid notch frequencies: {error}"
