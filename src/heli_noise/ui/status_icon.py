"""StatusIcon: a small idle/ok/error indicator widget.

Widgets map core exceptions to error state + a log-panel message; they
never show exception text in popups (see qt-ui-conventions skill).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from heli_noise.ui import strings, theme


class StatusIcon(QLabel):
    """A QLabel that displays one of three states: idle, ok, or error."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(20, 20)
        self.set_idle()

    def set_idle(self) -> None:
        """Show the neutral idle state."""
        self.setText("○")
        self.setStyleSheet(f"color: {theme.STATUS_IDLE}; font-weight: bold;")
        self.setToolTip(strings.STATUS_TOOLTIP_IDLE)

    def set_ok(self) -> None:
        """Show the success state."""
        self.setText("✓")
        self.setStyleSheet(f"color: {theme.STATUS_OK}; font-weight: bold;")
        self.setToolTip(strings.STATUS_TOOLTIP_OK)

    def set_error(self, message: str) -> None:
        """Show the error state with a tooltip carrying the detail message.

        Args:
            message: Human-readable error detail (shown in the tooltip,
                not in a popup).
        """
        self.setText("✗")
        self.setStyleSheet(f"color: {theme.STATUS_ERROR}; font-weight: bold;")
        self.setToolTip(message)
