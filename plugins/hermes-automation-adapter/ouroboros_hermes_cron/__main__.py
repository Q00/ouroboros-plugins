"""Command entrypoint for the Hermes cron/job automation adapter."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "hermes-automation-adapter"
PLUGIN_VERSION = "0.1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def resolve_jobs_file(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path.is_file():
        return path
    candidates = [path / "cron" / "jobs.json", path / "jobs.json"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"no Hermes jobs JSON found at {path} or {candidates[0]}")


def load_jobs(raw_path: str) -> tuple[Path, list[dict[str, Any]]]:
    jobs_file = resolve_jobs_file(raw_path)
    payload = json.loads(jobs_file.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs = payload["jobs"]
    else:
        raise ValueError("Hermes jobs JSON must be a list or an object with a jobs array")
    normalized: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ValueError(f"job at index {index} must be an object")
        copy = dict(job)
        copy.setdefault("id", f"job-{index + 1}")
        normalized.append(copy)
    return jobs_file, normalized


def classify_job(job: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(job, sort_keys=True).lower()
    risks: list[str] = []
    categories: set[str] = set()
    permissions: set[str] = {"filesystem:read"}
    rank = 0

    def bump(value: int, category: str, reason: str, *scopes: str) -> None:
        nonlocal rank
        rank = max(rank, value)
        categories.add(category)
        risks.append(reason)
        permissions.update(scopes)

    if job.get("scripts") or re.search(r"\b(shell|script|python|bash|curl|exec)\b", text):
        bump(2, "shell_execution", "job references scripts or shell-like execution", "shell:execute")
    if job.get("delivery") or re.search(r"\b(email|slack|discord|telegram|webhook)\b", text):
        bump(1, "external_delivery", "job may deliver output to an external system", "network:write")
    if re.search(r"https?://", text):
        bump(1, "network_read", "job references external network endpoints", "network:read")
    if job.get("workdir") or re.search(r"\b(write|out|report|file)\b", text):
        bump(1, "filesystem_write", "job uses workspace files or writes artifacts", "filesystem:write")
    if re.search(r"\b(delete|destroy|drop|prod|production)\b", text):
        bump(2, "destructive_or_production", "job may affect destructive or production resources", "shell:execute")

    labels = ["read_only", "write", "destructive"]
    return {"risk": labels[rank], "risk_categories": sorted(categories) or ["read_only_prompt"], "risk_reasons": risks or ["read-only scheduled prompt"], "permissions": sorted(permissions)}


def inspect_jobs(raw_path: str) -> dict[str, Any]:
    jobs_file, jobs = load_jobs(raw_path)
    inspected = []
    for job in jobs:
        risk = classify_job(job)
        inspected.append({
            "id": str(job.get("id")),
            "schedule": job.get("schedule"),
            "prompt": job.get("prompt"),
            "skills": job.get("skills", []),
            "scripts": job.get("scripts", []),
            "delivery": job.get("delivery"),
            "workdir": job.get("workdir"),
            "profile": job.get("profile"),
            "repeat": job.get("repeat"),
            "no_agent": job.get("no_agent", job.get("noAgent")),
            **risk,
            "raw": job,
        })
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ready",
        "source": {"jobs_file": str(jobs_file), "inspected_at": utc_now()},
        "summary": {"job_count": len(inspected)},
        "jobs": inspected,
        "safety": {"scheduled_jobs": False, "executed_scripts": False, "notes": ["Import is static and never schedules or runs Hermes jobs."]},
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = ["# Hermes cron import report", "", f"Source: `{payload['source']['jobs_file']}`", "", "## Summary", "", f"- Jobs inspected: {payload['summary']['job_count']}", "- Jobs scheduled: no", "- Scripts executed: no", ""]
    for job in payload["jobs"]:
        lines.extend([
            f"## Job: {job['id']}", "",
            f"- Schedule: `{job.get('schedule')}`",
            f"- Risk: `{job['risk']}`",
            f"- Risk categories: {', '.join(job.get('risk_categories', [])) or 'none'}",
            f"- Permissions: {', '.join(job['permissions'])}",
            f"- Skills: {', '.join(job.get('skills') or []) or 'none'}",
            f"- Scripts: {', '.join(job.get('scripts') or []) or 'none'}",
            f"- Delivery: `{job.get('delivery')}`",
            f"- Workdir: `{job.get('workdir')}`",
            f"- Profile: `{job.get('profile')}`",
            f"- Repeat: `{job.get('repeat')}`",
            f"- No-agent mode: `{job.get('no_agent')}`",
            f"- Reasons: {'; '.join(job['risk_reasons'])}", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def risk_map(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "ouroboros.hermes_cron_risk_map.v1",
        "source": payload["source"],
        "scheduled_jobs": False,
        "executed_scripts": False,
        "jobs": [{k: job[k] for k in ["id", "risk", "risk_categories", "risk_reasons", "permissions", "schedule", "delivery", "workdir", "profile", "repeat", "no_agent"]} for job in payload["jobs"]],
    }


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "job"


def render_seed_draft(job: dict[str, Any]) -> str:
    return f"""# Seed draft: Hermes cron job `{job['id']}`

## Objective

Review and optionally run the imported Hermes scheduled automation as an explicit Ouroboros workflow. Do not schedule it by default.

## Preserved Hermes metadata

- Schedule: `{job.get('schedule')}`
- Prompt: {job.get('prompt')!r}
- Skills: {job.get('skills') or []}
- Scripts: {job.get('scripts') or []}
- Delivery: {job.get('delivery')!r}
- Workdir: `{job.get('workdir')}`
- Profile: `{job.get('profile')}`
- Repeat policy: `{job.get('repeat')}`
- No-agent mode: `{job.get('no_agent')}`

## Risk review

- Risk: `{job['risk']}`
- Risk categories: {', '.join(job.get('risk_categories', [])) or 'none'}
- Permissions: {', '.join(job['permissions'])}
- Reasons: {'; '.join(job['risk_reasons'])}

## Execution gate

Before any run, explicitly approve filesystem, shell, network, model-provider, and delivery scopes. This draft is a review artifact only.
"""


def command_import(args: argparse.Namespace) -> int:
    payload = inspect_jobs(args.jobs_path)
    out = Path(args.out).expanduser().resolve()
    seed_dir = out / "seed-drafts"
    write_text_atomic(out / "hermes-cron-report.md", render_report(payload))
    write_json_atomic(out / "hermes-cron-risk-map.json", risk_map(payload))
    for job in payload["jobs"]:
        write_text_atomic(seed_dir / f"{slug(job['id'])}.md", render_seed_draft(job))
    handoff = f"# Hermes cron handoff\n\nGenerated {len(payload['jobs'])} Seed-compatible draft(s) under `seed-drafts/`. No jobs were scheduled or executed.\n"
    write_text_atomic(out / "handoff.md", handoff)
    sys.stdout.write(json.dumps({"status": "imported", "output_dir": str(out), "seed_drafts": sorted(p.name for p in seed_dir.iterdir())}, indent=2) + "\n")
    return 0


def command_plan(args: argparse.Namespace) -> int:
    payload = inspect_jobs(args.jobs_path)
    match = next((job for job in payload["jobs"] if job["id"] == args.job_id), None)
    if match is None:
        sys.stderr.write(f"error: job id not found: {args.job_id}\n")
        return 1
    out = Path(args.out).expanduser().resolve()
    write_text_atomic(out, render_seed_draft(match))
    sys.stdout.write(json.dumps({"status": "planned", "seed_draft": str(out), "job_id": args.job_id}, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-automation-adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("jobs_path")
    p_import = sub.add_parser("import")
    p_import.add_argument("jobs_path")
    p_import.add_argument("--out", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("jobs_path")
    p_plan.add_argument("--job-id", required=True)
    p_plan.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            sys.stdout.write(json.dumps(inspect_jobs(args.jobs_path), indent=2, sort_keys=True) + "\n")
            return 0
        if args.command == "import":
            return command_import(args)
        if args.command == "plan":
            return command_plan(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
