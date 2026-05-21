"""Command entrypoint for the Ouroboros superpowers plugin.

The module intentionally implements a handoff-first adapter. It projects an
Agent Skill catalog into Ouroboros command targets, records provenance, and
blocks writes/destructive external work unless trust is explicit.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "openai-skills-superpowers"
PLUGIN_VERSION = "0.1.0"
DEFAULT_REPOSITORY = "openai/skills"
DEFAULT_REF = "590b49edc158611a2b2ed715ae73f27eb70d251a"
DEFAULT_CATALOG_PATH = Path(".ouroboros") / PLUGIN_NAME / "catalog.json"
DEFAULT_AUDIT_PATH = Path(".ouroboros") / PLUGIN_NAME / "audit.jsonl"
READ_ONLY_SKILLS = {"openai-docs", "aspnet-core", "security-best-practices", "security-threat-model"}
TASK_READ_ONLY_OVERRIDES = {"pdf"}
READ_ONLY_TASK_WORDS = ("read", "review", "inspect", "extract", "summarize", "summarise", "analyze", "analyse")
WRITE_TASK_WORDS = ("create", "generate", "write", "edit", "render", "export", "save", "produce")
EXTERNAL_SKILL_KEYWORDS = {
    "gh-": "github:write",
    "github": "github:write",
    "figma": "figma:write",
    "linear": "linear:write",
    "notion": "notion:write",
    "sentry": "sentry:write",
    "cloudflare": "cloudflare:write",
    "netlify": "netlify:write",
    "render": "render:write",
    "vercel": "vercel:write",
    "deploy": "external:write",
    "yeet": "github:write",
}
DESTRUCTIVE_WORDS = ("deploy", "delete", "merge", "push", "commit", "pr", "write", "create", "update")


@dataclass(frozen=True)
class SkillProjection:
    name: str
    bucket: str
    source_path: str
    command_target: str
    source_repository: str
    source_ref: str
    description: str
    license_present: bool
    license_path: str | None
    resources: dict[str, Any]
    permissions: dict[str, Any]
    exposure: dict[str, Any]
    duplicate: bool = False


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json_dump(data) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bounded_write_path(raw_path: str, *, base: Path, label: str) -> Path:
    """Resolve a plugin write path without allowing cwd escape.

    The plugins repository has no standalone plugin-manager trust context that
    can grant arbitrary filesystem writes. Until that exists, all adapter writes
    stay inside the invocation cwd.
    """
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        raise SystemExit(f"{label} must be relative to the current working directory")
    resolved_base = base.resolve()
    resolved = (resolved_base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise SystemExit(f"{label} must stay inside the current working directory") from exc
    return resolved


def audit_log_path(args: argparse.Namespace) -> Path:
    return bounded_write_path(args.audit_log, base=Path.cwd(), label="--audit-log")


def repo_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    meta: dict[str, str] = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        meta[key.strip()] = value
    return meta


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return text


def component_inventory(skill_dir: Path, catalog_root: Path) -> dict[str, Any]:
    def listing(name: str) -> list[str]:
        folder = skill_dir / name
        if not folder.exists():
            return []
        return sorted(repo_relative(p, catalog_root) for p in folder.rglob("*") if p.is_file())

    agents = skill_dir / "agents" / "openai.yaml"
    skill_md = skill_dir / "SKILL.md"
    return {
        "skill_md": skill_md.is_file(),
        "skill_md_path": repo_relative(skill_md, catalog_root),
        "scripts": listing("scripts"),
        "references": listing("references"),
        "assets": listing("assets"),
        "agents_openai_yaml": agents.is_file(),
        "agents_openai_yaml_path": repo_relative(agents, catalog_root) if agents.is_file() else None,
    }


def infer_permissions(name: str, description: str, resources: dict[str, Any]) -> dict[str, Any]:
    haystack = f"{name} {description}".lower()
    required = ["filesystem:read"]
    optional: list[str] = []
    risk = "read_only"
    reasons = ["Read SKILL.md and progressively selected local resources."]

    if resources["scripts"]:
        optional.append("shell:execute")
        reasons.append("Bundled scripts are present; shell execution is gated until trust.")
        risk = "write"
    artifact_words = (
        "generate",
        "create",
        "migrate",
        "notebook",
        "pdf",
        "speech",
        "transcribe",
        "image",
    )
    if any(word in haystack for word in artifact_words):
        optional.append("filesystem:write")
        risk = max_risk(risk, "write")
        reasons.append("Skill may create local artifacts or generated media.")
    for keyword, scope in EXTERNAL_SKILL_KEYWORDS.items():
        if keyword in haystack:
            optional.append(scope)
            risk = "destructive" if any(w in haystack for w in DESTRUCTIVE_WORDS) else max_risk(risk, "write")
            reasons.append(f"External scope inferred from {keyword!r}.")
    external_markers = ("deploy", "github", "figma", "linear", "notion", "sentry", "yeet")
    if name in READ_ONLY_SKILLS and not any(marker in haystack for marker in external_markers):
        # Some read-only guidance skills ship helper scripts for optional
        # resolution/fallbacks. The skill remains read-only unless the caller
        # explicitly opts into shell execution.
        risk = "read_only"
        optional = [p for p in optional if p != "filesystem:write"]
    # Stable order/dedupe.
    required = sorted(dict.fromkeys(required))
    optional = sorted(dict.fromkeys(optional))
    return {"required": required, "optional": optional, "risk": risk, "reasons": reasons}


def max_risk(left: str, right: str) -> str:
    order = {"read_only": 0, "write": 1, "destructive": 2}
    return left if order[left] >= order[right] else right


def runtime_risk(skill: dict[str, Any], task: str) -> str:
    """Apply task-scoped read-only overrides without weakening catalog risk."""
    risk = skill["permissions"]["risk"]
    if skill["name"] not in TASK_READ_ONLY_OVERRIDES or risk != "write":
        return risk
    lowered = task.lower()
    if any(word in lowered for word in WRITE_TASK_WORDS):
        return risk
    if any(word in lowered for word in READ_ONLY_TASK_WORDS):
        return "read_only"
    return risk


def resolve_source(source: str, ref: str | None, work_dir: Path | None = None) -> tuple[Path, str, str]:
    candidate = Path(source).expanduser()
    if candidate.exists():
        root = candidate.resolve()
        sha = git_rev_parse(root) or (ref or "local")
        return root, source, sha

    repo_url = source if source.startswith("http") else f"https://github.com/{source}.git"
    ref = ref or DEFAULT_REF
    tmp_parent = Path(tempfile.mkdtemp(prefix="superpowers-skills-", dir=str(work_dir) if work_dir else None))
    root = tmp_parent / "skills"
    subprocess.run(["git", "clone", "--depth", "1", repo_url, str(root)], check=True, capture_output=True, text=True)
    if ref not in {"main", "master", "HEAD"}:
        # Fetch exact commits/tags when the shallow default does not already contain them.
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", ref],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "checkout", ref], cwd=root, check=True, capture_output=True, text=True)
    sha = git_rev_parse(root) or ref
    return root, source, sha


def git_rev_parse(root: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception:
        return None


def find_license(root: Path, skill_dir: Path) -> tuple[bool, str | None]:
    for base in (skill_dir, root):
        for name in ("LICENSE", "LICENSE.md", "COPYING", "NOTICE"):
            candidate = base / name
            if candidate.is_file():
                return True, repo_relative(candidate, root)
    return False, None


def build_catalog(source_root: Path, *, repository: str, ref: str) -> dict[str, Any]:
    skills_root = source_root / "skills"
    if not skills_root.is_dir():
        raise SystemExit(f"{source_root}: expected skills/ directory")

    projections: list[SkillProjection] = []
    names: dict[str, int] = {}
    for skill_md in sorted(skills_root.glob(".*/**/SKILL.md")):
        skill_dir = skill_md.parent
        bucket = skill_dir.parent.name.lstrip(".")
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        name = meta.get("name") or skill_dir.name
        description = meta.get("description", "")
        resources = component_inventory(skill_dir, source_root)
        license_present, license_path = find_license(source_root, skill_dir)
        permissions = infer_permissions(name, description, resources)
        names[name] = names.get(name, 0) + 1
        target = name if bucket == "curated" else f"{bucket}/{name}"
        projections.append(
            SkillProjection(
                name=name,
                bucket=bucket,
                source_path=repo_relative(skill_dir, source_root),
                command_target=target,
                source_repository=repository,
                source_ref=ref,
                description=description,
                license_present=license_present,
                license_path=license_path,
                resources=resources,
                permissions=permissions,
                exposure={
                    "run": f"ooo superpower run {target} -- <task>",
                    "inspect": f"ooo superpower inspect {target}",
                    "handoff": f"ooo superpower handoff {target} --task <task> --out <path>",
                    "direct_alias": "deferred",
                },
            )
        )

    out = []
    for projection in projections:
        item = asdict(projection)
        item["duplicate"] = names[projection.name] > 1
        if projection.duplicate or names[projection.name] > 1:
            item["duplicate_resolution"] = "curated bucket wins unqualified lookup; use system/<skill-name> for system duplicate."
        out.append(item)
    return {
        "schema_version": "0.1",
        "kind": "superpowers_catalog",
        "generated_at": now(),
        "source": {"repository": repository, "ref": ref, "path": str(source_root)},
        "skill_count": len(out),
        "curated_count": sum(1 for i in out if i["bucket"] == "curated"),
        "system_count": sum(1 for i in out if i["bucket"] == "system"),
        "duplicates": sorted(n for n, count in names.items() if count > 1),
        "skills": out,
    }


def load_catalog(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"catalog not found: {path}. Run `superpower catalog refresh` first or pass --catalog.")
    return read_json(path)


def resolve_skill(catalog: dict[str, Any], raw_name: str) -> dict[str, Any]:
    bucket: str | None = None
    name = raw_name
    if "/" in raw_name:
        bucket, name = raw_name.split("/", 1)
    matches = [s for s in catalog["skills"] if s["name"] == name]
    if bucket:
        matches = [s for s in matches if s["bucket"] == bucket.lstrip(".")]
    if not matches:
        raise SystemExit(f"unknown skill: {raw_name}")
    curated = [s for s in matches if s["bucket"] == "curated"]
    return curated[0] if curated else matches[0]


def catalog_source_root(catalog: dict[str, Any]) -> Path:
    return Path(catalog["source"].get("path", ".")).expanduser().resolve()


def read_skill_body(catalog: dict[str, Any], skill: dict[str, Any], limit: int = 12000) -> tuple[str, str]:
    root = catalog_source_root(catalog)
    path = root / skill["resources"]["skill_md_path"]
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    body = strip_frontmatter(text)
    if len(body) > limit:
        body = body[:limit].rstrip() + "\n\n[SKILL.md truncated for handoff/run projection]"
    return repo_relative(path, root), body


def selected_resources(skill: dict[str, Any], task: str, *, include_scripts: bool = False) -> dict[str, Any]:
    task_l = task.lower()
    resources = skill["resources"]
    references = []
    for ref in resources.get("references", []):
        stem = Path(ref).stem.lower()
        if any(part and part in task_l for part in re.split(r"[-_ ]+", stem)) or skill["permissions"]["risk"] == "read_only":
            references.append(ref)
    return {
        "skill_md": [resources["skill_md_path"]] if resources.get("skill_md") else [],
        "references": references[:8],
        "scripts": resources.get("scripts", []) if include_scripts else [],
        "assets": [],
        "agents": [resources["agents_openai_yaml_path"]] if resources.get("agents_openai_yaml") else [],
    }


def audit_event(
    event_type: str,
    command_name: str,
    argv: list[str],
    status: str,
    message: str,
    *,
    skill: dict[str, Any] | None = None,
    permissions_used: list[str] | None = None,
) -> dict[str, Any]:
    provenance = {"adapter": PLUGIN_NAME}
    if skill:
        provenance.update({
            "skill": skill["name"],
            "bucket": skill["bucket"],
            "source_repository": skill["source_repository"],
            "source_ref": skill["source_ref"],
            "source_path": skill["source_path"],
        })
    return {
        "schema_version": "0.1",
        "event_type": event_type,
        "occurred_at": now(),
        "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION, "source_type": "local_path"},
        "command": {"namespace": "superpower", "name": command_name, "argv": argv},
        "trust_state": "trusted" if status == "success" else ("blocked" if status == "blocked" else "installed"),
        "capabilities_used": ["provenance", "ledger"] + (["handoff"] if command_name == "handoff" else []),
        "permissions_used": permissions_used or [],
        "provenance": provenance,
        "result": {"status": status, "message": message},
    }


def append_audit(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def handoff_payload(
    catalog: dict[str, Any],
    skill: dict[str, Any],
    task: str,
    *,
    include_scripts: bool = False,
) -> dict[str, Any]:
    skill_path, instructions = read_skill_body(catalog, skill)
    loaded = selected_resources(skill, task, include_scripts=include_scripts)
    return {
        "schema_version": "0.1",
        "kind": "superpower_handoff",
        "source": {"repository": skill["source_repository"], "ref": skill["source_ref"], "path": skill["source_path"]},
        "skill": {
            "name": skill["name"],
            "bucket": skill["bucket"],
            "description": skill["description"],
            "components": {
                "skill_md": skill["resources"]["skill_md"],
                "scripts": bool(skill["resources"].get("scripts")),
                "references": bool(skill["resources"].get("references")),
                "assets": bool(skill["resources"].get("assets")),
                "agents": bool(skill["resources"].get("agents_openai_yaml")),
            },
        },
        "task": task,
        "permissions": skill["permissions"],
        "instructions": {"skill_md_path": skill_path, "excerpt": instructions},
        "outputs": {"human_summary": "Prepared Agent Skill handoff for Ouroboros execution.", "next_steps": ["Review permissions", "Run through Ouroboros firewall", "Attach result to Seed or ledger if needed"], "artifacts": []},
        "provenance": {"catalog_commit": skill["source_ref"], "loaded_files": sum((v for v in loaded.values() if isinstance(v, list)), []), "executed_scripts": []},
    }


def command_catalog_refresh(args: argparse.Namespace) -> int:
    source = args.source_path or args.source
    out = bounded_write_path(args.out, base=Path.cwd(), label="--out")
    work_dir = (
        bounded_write_path(args.work_dir, base=Path.cwd(), label="--work-dir")
        if args.work_dir
        else None
    )
    root, repository, ref = resolve_source(source, args.ref, work_dir=work_dir)
    try:
        catalog = build_catalog(root, repository=repository, ref=ref)
        write_json(out, catalog)
        print(
            json_dump(
                {
                    "status": "ok",
                    "catalog_path": str(out),
                    "skill_count": catalog["skill_count"],
                    "source_ref": ref,
                }
            )
        )
        return 0
    finally:
        if not args.keep_source and root.parent.name.startswith("superpowers-skills-"):
            shutil.rmtree(root.parent, ignore_errors=True)


def command_catalog_list(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    rows = []
    for s in catalog["skills"]:
        if s["bucket"] == "system" and not args.include_system:
            continue
        rows.append({"target": s["command_target"], "risk": s["permissions"]["risk"], "bucket": s["bucket"], "resources": {k: bool(s["resources"].get(k)) for k in ("skill_md", "scripts", "references", "assets", "agents_openai_yaml")}})
    print(json_dump({"skill_count": len(rows), "duplicates": catalog.get("duplicates", []), "skills": rows}))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    skill = resolve_skill(catalog, args.skill_name)
    print(json_dump(skill))
    return 0


def command_handoff(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    skill = resolve_skill(catalog, args.skill_name)
    out = bounded_write_path(args.out, base=Path.cwd(), label="--out")
    payload = handoff_payload(catalog, skill, args.task, include_scripts=False)
    write_json(out, payload)
    event = audit_event("plugin.completed", "handoff", [args.skill_name, "--task", args.task, "--out", str(out)], "success", f"handoff written to {out}", skill=skill, permissions_used=["filesystem:read", "filesystem:write"])
    append_audit(audit_log_path(args), event)
    print(json_dump({"status": "success", "handoff_path": str(out), "audit_log": args.audit_log, "risk": skill["permissions"]["risk"]}))
    return 0


def command_trust_plan(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    skill = resolve_skill(catalog, args.skill_name)
    plan = {
        "skill": skill["command_target"],
        "risk": skill["permissions"]["risk"],
        "required_before_run": skill["permissions"]["required"],
        "conditional_permissions": skill["permissions"]["optional"],
        "script_backed": bool(skill["resources"].get("scripts")),
        "external_write_blocked_until_trusted": any(scope.endswith(":write") or scope == "external:write" for scope in skill["permissions"].get("optional", [])),
        "direct_alias": "deferred until namespace collision policy is stronger",
        "recommended_command": f"ouroboros plugin trust openai-skills-superpowers {' '.join('--scope ' + p for p in skill['permissions']['required'] + skill['permissions']['optional'])}",
    }
    print(json_dump(plan))
    return 0


def emit_blocked_run(
    *,
    args: argparse.Namespace,
    skill: dict[str, Any],
    argv: list[str],
    message: str,
) -> int:
    append_audit(
        audit_log_path(args),
        audit_event("plugin.failed", "run", argv, "blocked", message, skill=skill),
    )
    print(
        json_dump(
            {
                "status": "blocked",
                "reason": message,
                "trust_plan": f"ooo superpower trust-plan {skill['command_target']}",
            }
        )
    )
    return 3


def command_run(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    skill = resolve_skill(catalog, args.skill_name)
    args.trusted = bool(getattr(args, "trusted", False))
    args.allow_shell = bool(getattr(args, "allow_shell", False))
    task_parts = list(args.task)
    # argparse.REMAINDER preserves flags after the skill name. Treat
    # self-attested trust flags as blocked requests, not authority grants.
    if "--trusted" in task_parts:
        args.trusted = True
        task_parts = [p for p in task_parts if p != "--trusted"]
    if "--allow-shell" in task_parts:
        args.allow_shell = True
        task_parts = [p for p in task_parts if p != "--allow-shell"]
    if task_parts and task_parts[0] == "--":
        task_parts = task_parts[1:]
    task = " ".join(task_parts).strip()
    if not task:
        raise SystemExit("task is required after --")
    argv = [args.skill_name, "--", task]
    risk = runtime_risk(skill, task)
    has_scripts = bool(skill["resources"].get("scripts"))
    if args.trusted:
        msg = "blocked: --trusted is not an authority source; use plugin-manager trust"
        return emit_blocked_run(args=args, skill=skill, argv=argv, message=msg)
    if args.allow_shell:
        msg = "blocked: shell-enabled script access requires plugin-manager trust"
        return emit_blocked_run(args=args, skill=skill, argv=argv, message=msg)
    if risk == "destructive":
        msg = "blocked: external-write or destructive skill requires plugin-manager trust"
        return emit_blocked_run(args=args, skill=skill, argv=argv, message=msg)
    if has_scripts and risk != "read_only":
        msg = "blocked: script-backed skill requires plugin-manager trust"
        return emit_blocked_run(args=args, skill=skill, argv=argv, message=msg)
    if risk != "read_only":
        msg = "blocked: write-capable skill requires plugin-manager trust"
        return emit_blocked_run(args=args, skill=skill, argv=argv, message=msg)

    include_scripts = False
    append_audit(
        audit_log_path(args),
        audit_event(
            "plugin.invoked",
            "run",
            argv,
            "success",
            "superpower invocation accepted after policy evaluation",
            skill=skill,
            permissions_used=["filesystem:read"],
        ),
    )

    payload = handoff_payload(catalog, skill, task, include_scripts=include_scripts)
    payload["kind"] = "superpower_run_projection"
    payload["outputs"]["human_summary"] = "Run projected safely. Execute the attached instructions in the active agent context; no hidden external mutation was performed by this adapter."
    if include_scripts:
        payload["provenance"]["executed_scripts"] = []
        payload["outputs"]["next_steps"].append("Scripts are available to the trusted caller; execute only the needed script and append executed path/provenance.")
    permissions_used = skill["permissions"]["required"] + (
        ["shell:execute"] if include_scripts else []
    )
    append_audit(
        audit_log_path(args),
        audit_event(
            "plugin.permission_used",
            "run",
            argv,
            "success",
            "permissions evaluated",
            skill=skill,
            permissions_used=permissions_used,
        ),
    )
    append_audit(
        audit_log_path(args),
        audit_event(
            "plugin.completed",
            "run",
            argv,
            "success",
            "run projection completed",
            skill=skill,
            permissions_used=permissions_used,
        ),
    )
    print(json_dump({"status": "success", "skill": skill["command_target"], "risk": risk, "audit_log": args.audit_log, "handoff": payload}))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    path = Path(args.catalog)
    report: dict[str, Any] = {"catalog_path": str(path), "catalog_present": path.is_file()}
    if path.is_file():
        catalog = load_catalog(path)
        report.update({"skill_count": catalog.get("skill_count"), "curated_count": catalog.get("curated_count"), "system_count": catalog.get("system_count"), "duplicates": catalog.get("duplicates", [])})
        report["ready"] = catalog.get("skill_count", 0) >= 43
    else:
        report["ready"] = False
        report["next_step"] = "ooo superpower catalog refresh --source openai/skills --ref <pinned-sha>"
    print(json_dump(report))
    return 0 if report["ready"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ouroboros_superpowers")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)
    refresh = catalog_sub.add_parser("refresh")
    refresh.add_argument("--source", default=DEFAULT_REPOSITORY)
    refresh.add_argument("--source-path")
    refresh.add_argument("--ref", default=DEFAULT_REF)
    refresh.add_argument("--out", default=str(DEFAULT_CATALOG_PATH))
    refresh.add_argument("--work-dir")
    refresh.add_argument("--keep-source", action="store_true")
    refresh.set_defaults(func=command_catalog_refresh)
    list_cmd = catalog_sub.add_parser("list")
    list_cmd.add_argument("--include-system", action="store_true")
    list_cmd.set_defaults(func=command_catalog_list)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("skill_name")
    inspect.set_defaults(func=command_inspect)

    handoff = sub.add_parser("handoff")
    handoff.add_argument("skill_name")
    handoff.add_argument("--task", required=True)
    handoff.add_argument("--out", required=True)
    handoff.set_defaults(func=command_handoff)

    run = sub.add_parser("run")
    run.add_argument("skill_name")
    run.add_argument("task", nargs=argparse.REMAINDER)
    run.set_defaults(func=command_run)

    trust = sub.add_parser("trust-plan")
    trust.add_argument("skill_name")
    trust.set_defaults(func=command_trust_plan)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
