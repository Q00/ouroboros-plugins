from __future__ import annotations

import argparse

from . import audits, deploy, optimize, tokens

COMMANDS = [
    "optimize", "react-best-practices", "web-design-guidelines", "react-native-skills",
    "react-view-transitions", "composition-patterns", "deploy-preview", "deploy-production", "cli-with-tokens",
]
AUDIT_COMMANDS = {"react-best-practices", "web-design-guidelines", "react-native-skills", "react-view-transitions", "composition-patterns"}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooo vercel", description="Vercel Agent Skills AgentOS adapter")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.command in AUDIT_COMMANDS:
        return audits.run(ns.command, ns.args)
    if ns.command == "optimize":
        return optimize.run(ns.args)
    if ns.command == "cli-with-tokens":
        return tokens.run(ns.args)
    if ns.command == "deploy-preview":
        return deploy.preview(ns.args)
    if ns.command == "deploy-production":
        return deploy.production(ns.args)
    print(f"vercel-agent-skills command skeleton: {ns.command}")
    if ns.args:
        print("arguments:", " ".join(ns.args))
    return 0
