from __future__ import annotations

import json
import sys

COMMANDS = [
    "run",
    "run-replay",
    "inspect",
    "quick-stats",
    "collect-artifacts",
    "handoff",
    "verify-artifacts",
]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: python -m swe_agent_harness {" + ",".join(COMMANDS) + "} ...")
        return 0
    print(json.dumps({"status": "failed", "error": f"command not implemented in skeleton: {argv[0]}", "exit_code": 2}, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
