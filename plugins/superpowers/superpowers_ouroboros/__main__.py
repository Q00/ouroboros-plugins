from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .skill_index import discover_skills, get_skill, write_index


def _json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _output_root(value: str | None) -> Path:
    return Path(value) if value else Path.cwd() / ".omx" / "superpowers"


def cmd_list(args: argparse.Namespace) -> int:
    root = _output_root(args.output_dir)
    index_path = write_index(root / "skill-index.json")
    _json({
        "status": "ok",
        "skill_count": len(discover_skills()),
        "skill_index_path": str(index_path),
        "skills": [s.to_json() for s in discover_skills()],
    })
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        skill = get_skill(args.skill)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _json({"status": "ok", "skill": skill.to_json()})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m superpowers_ouroboros")
    parser.add_argument("--output-dir", help="Artifact root; defaults to ./.omx/superpowers")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List pinned upstream Superpowers skills and command mappings")
    list_p.set_defaults(func=cmd_list)

    inspect_p = sub.add_parser("inspect", help="Inspect one Superpowers skill mapping")
    inspect_p.add_argument("skill")
    inspect_p.set_defaults(func=cmd_inspect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
