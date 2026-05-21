"""Command entrypoint for the Scientific Agent Skills AgentOS adapter."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
from importlib import resources
from pathlib import Path

PLUGIN_NAME = "scientific-agent-skills-adapter"
PLUGIN_VERSION = "0.1.0"
ARTIFACT_DIR = Path(".ouroboros") / "scientific-agent-skills"
RISK_ORDER = {"read_only": 0, "write": 1, "destructive": 2}


@dataclass(frozen=True)
class Registry:
    payload: dict

    @property
    def skills(self) -> list[dict]:
        return list(self.payload["skills"])

    @property
    def by_slug(self) -> dict[str, dict]:
        return {skill["slug"]: skill for skill in self.skills}

    @property
    def generated_from(self) -> dict:
        return dict(self.payload["generated_from"])


def load_registry() -> Registry:
    data = resources.files(__package__).joinpath("registry.generated.json").read_text(encoding="utf-8")
    return Registry(json.loads(data))


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def artifact_root(output: str | None = None) -> Path:
    if output:
        root = Path(output).expanduser().resolve()
    else:
        root = (Path.cwd() / ARTIFACT_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify_filename(text: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-") or "artifact"


def resolve_skill(registry: Registry, slug: str) -> dict:
    skills = registry.by_slug
    if slug in skills:
        return skills[slug]
    matches = get_close_matches(slug, sorted(skills), n=5, cutoff=0.45)
    hint = f" Did you mean: {', '.join(matches)}?" if matches else " Use `list` to see available skills."
    raise KeyError(f"unknown scientific skill {slug!r}.{hint}")


def list_payload(registry: Registry, *, domain: str | None, risk: str | None) -> dict:
    skills = registry.skills
    if domain:
        skills = [skill for skill in skills if skill["domain"] == domain]
    if risk:
        skills = [skill for skill in skills if skill["risk"] == risk]
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ok",
        "count": len(skills),
        "generated_from": registry.generated_from,
        "skills": [
            {
                "slug": skill["slug"],
                "description": skill["description"],
                "domain": skill["domain"],
                "risk": skill["risk"],
                "command": f"ooo scientific {skill['slug']} --task <goal>",
                "inspect": f"ooo scientific inspect {skill['slug']}",
                "prepare": f"ooo scientific prepare {skill['slug']} --task <goal>",
            }
            for skill in skills
        ],
    }


def inspect_payload(skill: dict) -> dict:
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ok",
        "skill": skill,
        "agentos_boundary": {
            "inspect": "read_only metadata/provenance inspection",
            "prepare": "writes only Seed-compatible handoff artifacts",
            "run": "dry-run by default; actual execution blocks unless future trust policy approves the skill path",
        },
    }


def explain_payload(skill: dict, task: str | None) -> dict:
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ok",
        "skill": skill["slug"],
        "task": task or "",
        "summary": skill["description"],
        "mapping": {
            "upstream_skill": skill["provenance"],
            "agentos_command": f"ooo scientific {skill['slug']} --task <goal>",
            "handoff_first": True,
            "non_goals": [
                "Do not vendor or execute upstream scripts from this reference adapter.",
                "Do not grant blanket shell/network/lab/cloud authority.",
                "Do not make ooo auto a scientific-domain router.",
            ],
            "required_permissions": [p for p in skill["permissions"] if p["required"]],
            "optional_permissions": [p for p in skill["permissions"] if not p["required"]],
            "risk_semantics": skill["security"],
        },
    }


def build_seed(skill: dict, task: str, handoff_path: Path) -> str:
    permissions = "\n".join(
        f"- {p['scope']} ({p['risk']}, required={p['required']}): {p['reason']}"
        for p in skill["permissions"]
    )
    expected = [
        "Seed-compatible handoff JSON",
        "audit event JSON",
        "provenance block with upstream repository, commit, skill path, and source hash",
    ]
    return "\n".join(
        [
            "# Scientific Agent Skill Handoff",
            "",
            f"generated_at: {datetime.now(timezone.utc).isoformat()}",
            f"plugin: {PLUGIN_NAME}@{PLUGIN_VERSION}",
            f"skill: {skill['slug']}",
            f"domain: {skill['domain']}",
            f"risk: {skill['risk']}",
            f"handoff_json: {handoff_path}",
            "",
            "## Task",
            "",
            task,
            "",
            "## Upstream Capability",
            "",
            skill["description"],
            "",
            "## Non-goals",
            "",
            "- Do not execute upstream scripts during preparation.",
            "- Do not access clinical, lab automation, cloud compute, credentialed APIs, shell, or network resources without explicit trust.",
            "- Do not hide state in terminal output; durable JSON artifacts are the source of truth.",
            "",
            "## Permission Plan",
            "",
            permissions,
            "",
            "## Expected Artifacts",
            "",
            *(f"- {item}" for item in expected),
            "",
            "## Verification Strategy",
            "",
            "- Inspect the generated handoff JSON and audit event.",
            "- Confirm risk classification and optional permissions before any execution path.",
            "- For destructive/write skills, require a manual trust review and keep execution blocked until approved.",
            "",
            "## Resume Instructions",
            "",
            f"- Re-run `ooo scientific inspect {skill['slug']}` to review metadata.",
            f"- Re-run `ooo scientific prepare {skill['slug']} --task <goal>` to regenerate this handoff.",
            "- Pass this handoff to `ooo auto` only as a prepared Seed; `ooo auto` remains domain-agnostic.",
            "",
        ]
    )


def audit_event(skill: dict, command: str, status: str, args: dict, artifacts: dict | None = None) -> dict:
    success = status == "completed"
    scopes = [p["scope"] for p in skill["permissions"] if p["required"]]
    message_parts = [f"skill={skill['slug']}", f"risk={skill['risk']}"]
    if artifacts:
        message_parts.extend(f"{name}={path}" for name, path in sorted(artifacts.items()))
    if args:
        message_parts.extend(f"arg.{name}={value}" for name, value in sorted(args.items()))
    return {
        "schema_version": "0.1",
        "event_type": "plugin.completed" if success else "plugin.failed",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "source_type": "local_path",
        },
        "command": {
            "namespace": "scientific",
            "name": command,
            "argv": [str(args[name]) for name in sorted(args)],
        },
        "trust_state": "installed" if success else "blocked",
        "capabilities_used": ["seed:write", "ledger:write", "state:write", "provenance:write", "handoff:attach"],
        "permissions_used": scopes,
        "provenance": {
            "repository": str(skill["provenance"]["repository"]),
            "commit": str(skill["provenance"]["commit"]),
            "skill_path": str(skill["provenance"]["skill_path"]),
            "source_hash": str(skill["provenance"]["source_hash"]),
        },
        "result": {
            "status": "success" if success else "blocked",
            "message": "; ".join(message_parts),
        },
    }


def prepare_payload(skill: dict, task: str, *, output: str | None = None, command: str = "prepare") -> dict:
    root = artifact_root(output)
    stem = slugify_filename(skill["slug"])
    handoff_path = root / f"{stem}-handoff.json"
    seed_path = root / f"{stem}-seed.md"
    audit_path = root / f"{stem}-audit.json"
    handoff = {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "prepared",
        "skill": {
            "slug": skill["slug"],
            "description": skill["description"],
            "domain": skill["domain"],
            "risk": skill["risk"],
            "security": skill["security"],
        },
        "task": task,
        "non_goals": [
            "No upstream script execution during prepare.",
            "No blanket shell/network/filesystem/API/lab/cloud authority.",
            "No hidden state outside the generated artifacts.",
        ],
        "permissions": {
            "required": [p for p in skill["permissions"] if p["required"]],
            "optional": [p for p in skill["permissions"] if not p["required"]],
        },
        "expected_artifacts": ["handoff_json", "seed_markdown", "audit_json"],
        "verification": [
            "Validate handoff JSON contains plugin, skill, task, permissions, provenance, and resume instructions.",
            "Review trust report before any non-dry-run execution.",
            "Block execution for write/destructive or manually unreviewed skill paths.",
        ],
        "resume": {
            "inspect": f"ooo scientific inspect {skill['slug']}",
            "prepare": f"ooo scientific prepare {skill['slug']} --task <goal>",
            "auto_handoff": f"ooo auto \"$(cat {seed_path})\"",
        },
        "provenance": skill["provenance"],
        "paths": {"handoff": str(handoff_path), "seed": str(seed_path), "audit": str(audit_path)},
    }
    seed = build_seed(skill, task, handoff_path)
    write_json_atomic(handoff_path, handoff)
    seed_path.write_text(seed, encoding="utf-8")
    event = audit_event(skill, command, "completed", {"task": task, "output": output or str(root)}, handoff["paths"])
    write_json_atomic(audit_path, event)
    return handoff


def run_payload(skill: dict, task: str, *, output: str | None, dry_run: bool, trusted: bool) -> tuple[int, dict]:
    if dry_run:
        payload = prepare_payload(skill, task, output=output, command="run-dry-run")
        payload["status"] = "dry_run_prepared"
        payload["execution"] = "not_executed"
        return 0, payload
    if not trusted or skill["risk"] != "read_only" or skill["security"].get("requires_manual_review"):
        root = artifact_root(output)
        audit_path = root / f"{slugify_filename(skill['slug'])}-blocked-audit.json"
        payload = {
            "plugin": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "status": "blocked",
            "skill": skill["slug"],
            "risk": skill["risk"],
            "reason": "Actual upstream skill execution is blocked unless a low-risk path has explicit trust; use --dry-run or prepare.",
            "recommended_next_step": f"ooo scientific prepare {skill['slug']} --task <goal>",
            "provenance": skill["provenance"],
            "audit_path": str(audit_path),
        }
        write_json_atomic(audit_path, audit_event(skill, "run", "failed", {"task": task, "dry_run": dry_run, "trusted": trusted}, {"blocked_audit": str(audit_path)}))
        return 1, payload
    payload = prepare_payload(skill, task, output=output, command="run")
    payload["status"] = "prepared_low_risk_execution_handoff"
    payload["execution"] = "handoff_only_reference_adapter"
    return 0, payload


def trust_report(skill: dict) -> dict:
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ok",
        "skill": skill["slug"],
        "risk": skill["risk"],
        "security": skill["security"],
        "permissions": skill["permissions"],
        "provenance": skill["provenance"],
        "policy": {
            "list_inspect_explain": "always read_only",
            "prepare": "writes only handoff/provenance/audit artifacts",
            "run_dry_run": "prepares artifacts without upstream execution",
            "run": "blocked for write/destructive/manual-review skills; no high-risk upstream script execution",
        },
    }


def doctor_payload(registry: Registry) -> dict:
    skills = registry.skills
    aliases = {skill["slug"] for skill in skills}
    risk_counts = {risk: sum(1 for skill in skills if skill["risk"] == risk) for risk in RISK_ORDER}
    return {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "ok" if len(skills) == len(aliases) else "error",
        "skill_count": len(skills),
        "alias_count": len(aliases),
        "risk_counts": risk_counts,
        "generated_from": registry.generated_from,
        "safety_defaults": {
            "all_skills_have_aliases": len(skills) == len(aliases),
            "actual_execution_default": "blocked unless explicitly trusted and low-risk",
            "handoff_first": True,
        },
    }


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_parser(registry: Registry) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scientific")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--domain")
    p_list.add_argument("--risk", choices=sorted(RISK_ORDER))

    for name in ("inspect", "trust-report"):
        p = sub.add_parser(name)
        p.add_argument("skill")

    p_explain = sub.add_parser("explain")
    p_explain.add_argument("skill")
    p_explain.add_argument("--task")

    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("skill")
    p_prepare.add_argument("--task", required=True)
    p_prepare.add_argument("--output")

    p_run = sub.add_parser("run")
    p_run.add_argument("skill")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--output")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--trusted", action="store_true", help="Acknowledge a future explicit trust grant for low-risk paths only.")

    sub.add_parser("doctor")

    for slug in sorted(registry.by_slug):
        p_alias = sub.add_parser(slug)
        p_alias.add_argument("--task", required=True)
        p_alias.add_argument("--output")
        p_alias.add_argument("--dry-run", action="store_true")
        p_alias.add_argument("--trusted", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    registry = load_registry()
    parser = build_parser(registry)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            emit(list_payload(registry, domain=args.domain, risk=args.risk))
            return 0
        if args.command == "doctor":
            payload = doctor_payload(registry)
            emit(payload)
            return 0 if payload["status"] == "ok" else 1

        if args.command in registry.by_slug:
            skill = resolve_skill(registry, args.command)
            code, payload = run_payload(skill, args.task, output=args.output, dry_run=args.dry_run or not args.trusted, trusted=args.trusted)
            emit(payload)
            return code

        skill = resolve_skill(registry, args.skill)
        if args.command == "inspect":
            emit(inspect_payload(skill))
            return 0
        if args.command == "explain":
            emit(explain_payload(skill, args.task))
            return 0
        if args.command == "prepare":
            emit(prepare_payload(skill, args.task, output=args.output))
            return 0
        if args.command == "run":
            code, payload = run_payload(skill, args.task, output=args.output, dry_run=args.dry_run, trusted=args.trusted)
            emit(payload)
            return code
        if args.command == "trust-report":
            emit(trust_report(skill))
            return 0
    except KeyError as exc:
        parser.exit(2, f"scientific: {exc.args[0]}\n")
    parser.error("unhandled command")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
