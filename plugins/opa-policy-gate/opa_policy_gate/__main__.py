"""Placeholder entrypoint for the OPA policy gate reference plugin.

The contract/docs PR intentionally lands the manifest, examples, and UX boundary
before the bounded OPA bridge implementation. Runtime commands are implemented
in the follow-up bridge PR in this stack.
"""

from __future__ import annotations

import argparse
import json

from . import PLUGIN_NAME, PLUGIN_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(prog="opa_policy_gate")
    parser.add_argument("command", choices=["eval", "test", "check", "build-handoff"])
    parser.add_argument("--config", help="Repo-relative OPA policy gate config file.")
    args = parser.parse_args()
    print(json.dumps({
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "command": args.command,
        "status": "blocked",
        "reason": "bridge_not_implemented_yet",
        "message": "This PR defines the contract and docs; the bounded OPA bridge lands in the next stacked PR.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
