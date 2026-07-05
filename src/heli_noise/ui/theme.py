"""Cockpit theme: dark instrument-panel color palette and stylesheet.

Central source of truth for colors — widget code must never hardcode a
color literal; import the constants (or the stylesheet) from here.
"""

BACKGROUND = "#0d1117"
PRIMARY = "#ffb020"  # amber — main action buttons
PRIMARY_HOVER = "#ffc350"  # lighter amber for button hover
READOUT = "#29d6e8"  # cyan — numeric readouts, time displays
STATUS_IDLE = "#6e7681"  # muted gray
STATUS_OK = "#35d07f"  # green
STATUS_ERROR = "#ff4d4d"  # red
TEXT = "#c9d1d9"
BORDER = "#30363d"


def build_stylesheet() -> str:
    """Return the QSS stylesheet applying the cockpit palette globally."""
    return f"""
        QWidget {{
            background-color: {BACKGROUND};
            color: {TEXT};
        }}
        QPushButton {{
            background-color: {PRIMARY};
            color: {BACKGROUND};
            border: none;
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: 600;
        }}
        QPushButton:disabled {{
            background-color: {BORDER};
            color: {STATUS_IDLE};
        }}
        QPushButton:hover:!disabled {{
            background-color: {PRIMARY_HOVER};
        }}
        QLineEdit, QPlainTextEdit, QListWidget {{
            background-color: #161b22;
            color: {READOUT};
            border: 1px solid {BORDER};
            border-radius: 3px;
            padding: 3px;
            font-family: "Consolas", "DejaVu Sans Mono", monospace;
        }}
        QLabel {{
            color: {TEXT};
        }}
    """
