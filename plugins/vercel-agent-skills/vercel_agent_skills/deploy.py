from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .runtime import RunContext, relative, repo_root, write_handoff, write_json


def preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ooo vercel deploy-preview")
    parser.add_argument("project_path")
    parser.add_argument("--scope")
    parser.add_argument("--claimable", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Actually invoke vercel deploy after confirmation and token checks.")
    parser.add_argument("--out", type=Path)
    ns = parser.parse_args(argv)
    ctx = RunContext(command="deploy-preview", upstream_skill="deploy-to-vercel", risk="write", out=ns.out, argv=argv, permissions_used=["filesystem:read", "network:write", "vercel:deploy:preview"])
    project = (Path(ns.project_path) if Path(ns.project_path).is_absolute() else Path.cwd() / ns.project_path).resolve()
    limitations = []
    status = "blocked"
    planned = ["vercel", "deploy", str(project)]
    if ns.scope:
        planned += ["--scope", ns.scope]
    if ns.no_wait:
        planned.append("--no-wait")
    if not ns.confirm:
        limitations.append("Preview deployment requires --confirm for explicit write trust.")
    if not os.environ.get("VERCEL_TOKEN"):
        limitations.append("VERCEL_TOKEN must be supplied via environment, never command-line arguments.")
    if ns.execute and ns.confirm and os.environ.get("VERCEL_TOKEN"):
        limitations.append("Execution hook is intentionally not enabled in v0 tests; command is prepared for the trusted runtime to execute.")
    deployment = {"planned_command": planned, "execute_requested": ns.execute, "claimable": ns.claimable, "scope": ns.scope, "project_path": relative(project, repo_root(project))}
    write_json(ctx.run_dir / "deployment-plan.json", deployment)
    handoff = write_handoff(ctx, status, [{"kind": "deployment_plan", "path": str(ctx.run_dir / "deployment-plan.json")}], limitations=limitations, next_actions=[{"kind": "trust_gate", "summary": "Rerun with --confirm and VERCEL_TOKEN in the environment from a trusted AgentOS write context."}], provenance_extra={"project_path": deployment["project_path"]})
    print(json.dumps(handoff, indent=2))
    return 2


def production(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ooo vercel deploy-production")
    parser.add_argument("project_path")
    parser.add_argument("--scope")
    parser.add_argument("--out", type=Path)
    ns = parser.parse_args(argv)
    ctx = RunContext(command="deploy-production", upstream_skill="deploy-to-vercel", risk="destructive", out=ns.out, argv=argv, permissions_used=["filesystem:read", "vercel:deploy:production"])
    handoff = write_handoff(ctx, "blocked", [], limitations=["Production deployment is disabled in v0 until destructive trust UX, confirmation, audit, and rollback guidance are locked."], next_actions=[{"kind": "use_preview", "summary": "Use deploy-preview for non-production validation."}])
    print(json.dumps(handoff, indent=2))
    return 2
