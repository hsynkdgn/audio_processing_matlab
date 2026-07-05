"""PostToolUse hook (Edit|Write): auto-lint and format changed .py files.

Reads the hook payload from stdin; if the touched file is a Python file,
runs `ruff check --fix <file>` followed by `ruff format <file>`.
Never blocks the tool call (always exits 0).
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return 0
    path = Path(file_path)
    if not path.is_file():
        return 0

    for cmd in (
        [sys.executable, "-m", "ruff", "check", "--fix", str(path)],
        [sys.executable, "-m", "ruff", "format", str(path)],
    ):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            print(f"[ruff hook] {' '.join(cmd[3:])}: {output[-800:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
