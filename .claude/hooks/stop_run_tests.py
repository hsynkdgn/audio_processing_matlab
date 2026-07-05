"""Stop hook: informational test summary at the end of a turn.

If tests/ contains any test files, runs the suite headless with a terse
summary. NEVER blocks (always exits 0) — this is a status readout only.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"


def main() -> int:
    if not TESTS_DIR.is_dir() or not any(TESTS_DIR.rglob("test_*.py")):
        return 0

    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    tail = (result.stdout + result.stderr).strip().splitlines()
    summary = "\n".join(tail[-5:]) if tail else "(no pytest output)"
    print(f"[stop hook — test summary, informational]\n{summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
