"""Command entrypoint for the github-pr-ops reference skeleton."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="github-pr-ops")
    parser.add_argument("command", choices=["review", "merge"])
    parser.add_argument("pull_request_url")
    parser.add_argument("--policy", default="team-default")
    args = parser.parse_args(argv)

    result = {
        "plugin": "github-pr-ops",
        "command": args.command,
        "pull_request_url": args.pull_request_url,
        "policy": args.policy if args.command == "merge" else None,
        "status": "not_implemented",
        "message": "This reference plugin skeleton defines the boundary only.",
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
