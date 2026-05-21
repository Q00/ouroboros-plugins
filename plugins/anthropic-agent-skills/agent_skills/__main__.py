from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import load_catalog
from .handoff import make_handoff, write_handoff
from .inspect import catalog_path, dumps, inspect_skill
from .manifest_adapter import validate_path
from .router import resolve
from .runner import invoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_skills")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect")
    p.add_argument("skill_dir", type=Path)

    p = sub.add_parser("catalog")
    p.add_argument("repo_or_path", nargs="?", type=Path)
    p.add_argument("--builtin", action="store_true")

    p = sub.add_parser("validate")
    p.add_argument("path", type=Path)

    p = sub.add_parser("resolve")
    p.add_argument("request", nargs="+")

    p = sub.add_parser("prepare-handoff")
    p.add_argument("skill")
    p.add_argument("skill_command")
    p.add_argument("--status", required=True, choices=["success", "failed", "blocked", "cancelled"])
    p.add_argument("--summary", default="")
    p.add_argument("--out", type=Path)

    p = sub.add_parser("invoke")
    p.add_argument("skill")
    p.add_argument("skill_command")
    p.add_argument("--repo", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", type=Path)
    p.add_argument("--artifact-dir", type=Path)
    p.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            sys.stdout.write(dumps(inspect_skill(args.skill_dir)))
        elif args.command == "catalog":
            if args.builtin or args.repo_or_path is None:
                sys.stdout.write(json.dumps(load_catalog(), indent=2, sort_keys=True) + "\n")
            else:
                sys.stdout.write(dumps(catalog_path(args.repo_or_path)))
        elif args.command == "validate":
            sys.stdout.write(dumps(validate_path(args.path)))
        elif args.command == "resolve":
            sys.stdout.write(json.dumps(resolve(" ".join(args.request)), indent=2, sort_keys=True) + "\n")
        elif args.command == "prepare-handoff":
            payload = make_handoff(args.skill, args.skill_command, status=args.status, summary=args.summary)
            sys.stdout.write(write_handoff(payload, args.out))
        elif args.command == "invoke":
            rest = list(args.args)
            repo = args.repo
            dry_run = args.dry_run
            out = args.out
            artifact_dir = args.artifact_dir
            passthrough: list[str] = []
            i = 0
            while i < len(rest):
                token = rest[i]
                if token == "--dry-run":
                    dry_run = True
                    i += 1
                elif token in {"--repo", "--out", "--artifact-dir"} and i + 1 < len(rest):
                    value = Path(rest[i + 1])
                    if token == "--repo":
                        repo = value
                    elif token == "--out":
                        out = value
                    else:
                        artifact_dir = value
                    i += 2
                else:
                    passthrough.append(token)
                    i += 1
            payload = invoke(args.skill, args.skill_command, passthrough, repo=repo, dry_run=dry_run, artifact_dir=artifact_dir)
            sys.stdout.write(write_handoff(payload, out))
        return 0
    except Exception as exc:
        sys.stderr.write(f"agent_skills: error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
