"""PreToolUse hook (Bash): block destructive / history-rewriting commands.

Exit code 2 blocks the tool call; the reason on stderr is fed back to
Claude. Plain `git push` to the working branch is ALLOWED — it is how
results reach GitHub in this workflow.
"""

import json
import re
import sys

_NO_REWRITE = "is forbidden (never rewrite published history)."
BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/(?:\s|$)", "rm -rf / is destructive and forbidden."),
    (r"\bgit\s+push\b[^&|;]*--force\b", f"git push --force {_NO_REWRITE}"),
    (r"\bgit\s+push\b[^&|;]*\s-f\b", f"git push -f {_NO_REWRITE}"),
    (r"\bgit\s+rebase\b", "git rebase is forbidden (never rewrite history in this workflow)."),
    (r"\bgit\s+reset\s+[^&|;]*--hard\b", "git reset --hard is forbidden (destroys work)."),
    (
        r"\bgit\s+merge\s+(origin/)?main\b",
        "git merge main is forbidden (the user merges via PR review).",
    ),
]

# `git checkout main` combined with commit intent in the same command line
# (e.g. `git checkout main && git commit ...`) — committing on main is the
# user's job, via PR review.
CHECKOUT_MAIN = re.compile(r"\bgit\s+(checkout|switch)\s+(origin/)?main\b")
COMMIT_INTENT = re.compile(r"\bgit\s+(commit|merge|cherry-pick|am|apply)\b|\bgit\s+push\b")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    for pattern, reason in BLOCKED_PATTERNS:
        if re.search(pattern, command):
            print(f"BLOCKED by pre_tool_use_guard: {reason}", file=sys.stderr)
            return 2

    if CHECKOUT_MAIN.search(command) and COMMIT_INTENT.search(command):
        print(
            "BLOCKED by pre_tool_use_guard: switching to main combined with "
            "commit/push intent is forbidden — work happens on the session "
            "branch; the user merges to main via PR review.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
