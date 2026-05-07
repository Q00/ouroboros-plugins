"""Command entrypoint for the github-pr-ops reference skeleton.

v0 only ships the read-only `review` command. The `merge` command is
deliberately deferred until the destructive trust UX lands
(see Q00/ouroboros-plugins#9).
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="github-pr-ops")
    parser.add_argument("command", choices=["review"])
    parser.add_argument("pull_request_url")
    args = parser.parse_args(argv)

    result = {
        "plugin": "github-pr-ops",
        "command": args.command,
        "pull_request_url": args.pull_request_url,
        "status": "not_implemented",
        "message": "This reference plugin skeleton defines the boundary only.",
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
