from __future__ import annotations

import argparse

COMMANDS = [
    "optimize",
    "react-best-practices",
    "web-design-guidelines",
    "react-native-skills",
    "react-view-transitions",
    "composition-patterns",
    "deploy-preview",
    "deploy-production",
    "cli-with-tokens",
]

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooo vercel", description="Vercel Agent Skills AgentOS adapter")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    print(f"vercel-agent-skills command skeleton: {ns.command}")
    if ns.args:
        print("arguments:", " ".join(ns.args))
    return 0
