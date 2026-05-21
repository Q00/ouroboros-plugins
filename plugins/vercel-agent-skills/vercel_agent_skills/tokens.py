from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .runtime import RunContext, read_text, redact, relative, repo_root, write_handoff, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooo vercel cli-with-tokens")
    parser.add_argument("subcommand", choices=["preflight", "env-check"])
    parser.add_argument("project_path")
    parser.add_argument("--out", type=Path)
    return parser


def run(argv: list[str]) -> int:
    ns = build_parser().parse_args(argv)
    ctx = RunContext(command="cli-with-tokens", upstream_skill="vercel-cli-with-tokens", out=ns.out, argv=argv, permissions_used=["filesystem:read", "shell:execute"])
    project = (Path(ns.project_path) if Path(ns.project_path).is_absolute() else Path.cwd() / ns.project_path).resolve()
    result = _inspect(project)
    write_json(ctx.run_dir / "token-preflight.json", result)
    handoff = write_handoff(ctx, "success", [{"kind": "token_preflight", "path": str(ctx.run_dir / "token-preflight.json")}], limitations=result["limitations"], next_actions=[{"kind": "use_safe_env", "summary": "Pass VERCEL_TOKEN via environment, never argv, when a trusted write command is confirmed."}], provenance_extra={"project_path": relative(project, repo_root(project))})
    print(json.dumps(handoff, indent=2))
    return 0


def _inspect(project: Path) -> dict[str, object]:
    env_has_token = bool(os.environ.get("VERCEL_TOKEN"))
    env_preview = "[REDACTED]" if env_has_token else "missing"
    dot_vercel = project / ".vercel" / "project.json"
    project_link = {}
    if dot_vercel.exists():
        try:
            raw = json.loads(read_text(dot_vercel, 100_000))
            project_link = {k: redact(str(v)) for k, v in raw.items() if k in {"projectId", "orgId", "settings"}}
        except json.JSONDecodeError:
            project_link = {"error": "invalid .vercel/project.json"}
    env_hints = []
    for name in [".env", ".env.local", ".env.development", ".env.production"]:
        p = project / name
        if p.exists():
            text = read_text(p, 50_000)
            if "VERCEL_TOKEN" in text:
                env_hints.append({"file": name, "contains_vercel_token_key": True, "value": "[REDACTED]"})
    limitations = []
    if not env_has_token:
        limitations.append("VERCEL_TOKEN is not present in the process environment.")
    if not dot_vercel.exists():
        limitations.append("No .vercel/project.json link file detected.")
    return {"vercel_token": env_preview, "project_link": project_link, "env_hints": env_hints, "limitations": limitations}
