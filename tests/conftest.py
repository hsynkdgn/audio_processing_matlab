"""Global pytest configuration.

Forces the Qt offscreen platform plugin BEFORE any Qt import so that all
GUI tests run headless in the cloud sandbox (no display available).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
