"""SessionStart hook: install dependencies in the fresh (ephemeral) sandbox.

The cloud VM is recreated each session, so every session must start with
`pip install -r requirements.txt`. Output is kept short; full pip logs go
to a scratch file only when something fails.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = REPO_ROOT / "requirements.txt"


def ensure_qt_system_libs() -> None:
    """Best-effort install of Qt6 runtime libs on the Linux sandbox.

    PySide6 needs libEGL & friends even with QT_QPA_PLATFORM=offscreen;
    the ephemeral VM does not ship them. No-op on non-Linux / on failure.
    """
    if sys.platform != "linux" or Path("/usr/lib/x86_64-linux-gnu/libEGL.so.1").exists():
        return
    subprocess.run(["apt-get", "update", "-q"], capture_output=True, check=False)
    result = subprocess.run(
        ["apt-get", "install", "-y", "-q", "libegl1", "libgl1", "libxkbcommon0", "libdbus-1-3"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    status = "installed" if result.returncode == 0 else "FAILED (Qt tests may not run)"
    print(f"session_start hook: Qt system libs (libEGL etc.) {status}")


def main() -> int:
    ensure_qt_system_libs()
    if not REQUIREMENTS.is_file():
        print("session_start hook: requirements.txt not found, skipping install")
        return 0

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        print("session_start hook: dependencies installed (pip install -r requirements.txt)")
    else:
        # Never block the session on install failure; report the tail.
        print("session_start hook: pip install FAILED — tail of output:")
        print((result.stdout + result.stderr)[-1500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
