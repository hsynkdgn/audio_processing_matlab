"""Application entry point: ``python -m heli_noise`` (Windows target)."""

import sys

from PySide6.QtWidgets import QApplication

from heli_noise.ui.main_window import MainWindow


def main() -> int:
    """Launch the main window and run the Qt event loop."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
