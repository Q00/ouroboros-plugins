"""Bounded command entrypoint for the target-capabilities reference plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "target-capabilities"
PLUGIN_VERSION = "0.1.0"
ENV_TARGET_ROOT = "TARGET_CAPABILITIES_ROOT"
ARTIFACT_ROOT = Path(".ouroboros") / "artifacts" / PLUGIN_NAME
HANDOFF_ROOT = Path(".ouroboros") / "handoffs" / PLUGIN_NAME
STANDARD_ARTIFACTS = [
    "result.json",
    "report.md",
    "stdout.txt",
    "stderr.txt",
    "provenance.json",
    "handoff.json",
]


@dataclass(frozen=True)
class CommandSpec:
    name: str
    summary: str
    risk: str
    permissions: tuple[str, ...]


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "list-commands",
        "List bounded command adapters.",
        "read_only",
        ("filesystem:read", "filesystem:write"),
    ),
    CommandSpec(
        "inspect",
        "Inspect target repository readiness.",
        "read_only",
        ("filesystem:read", "filesystem:write"),
    ),
    CommandSpec(
        "doctor",
        "Check dependency and trust readiness.",
        "read_only",
        ("filesystem:read", "filesystem:write"),
    ),
)


class UserError(Exception):
    """Expected CLI validation error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return cleaned or "target"


def stable_run_id(command: str, target_repository: str, target_root: Path | None) -> str:
    base = f"{utc_now()}|{command}|{target_repository}|{target_root or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def command_spec(name: str) -> CommandSpec:
    for spec in COMMANDS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def resolve_target_root(raw: str | None, *, required: bool) -> Path | None:
    configured = raw or os.environ.get(ENV_TARGET_ROOT)
    if not configured:
        if required:
            raise UserError(
                "target dependency not found: pass --target-root or set TARGET_CAPABILITIES_ROOT"
            )
        return None
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise UserError(f"target dependency not found: {root} is not a directory")
    return root


def repo_member_path(root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise UserError(f"{label} must be relative to the target repository root")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UserError(f"{label} must stay inside the target repository root") from exc
    return resolved


def relative_or_display(path: Path, root: Path | None) -> str:
    if root is not None:
        try:
            return str(path.relative_to(root))
        except ValueError:
            pass
    return str(path)


def safe_file_inventory(root: Path, *, limit: int = 60) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    skip_dirs = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if path.is_file():
            entries.append({"path": str(rel), "bytes": path.stat().st_size})
        if len(entries) >= limit:
            break
    return entries


def infer_capabilities(root: Path | None) -> list[dict[str, str]]:
    if root is None:
        return []
    hints = [
        ("pyproject.toml", "python-project"),
        ("package.json", "node-project"),
        ("README.md", "documentation"),
        ("Makefile", "make-targets"),
        ("Dockerfile", "container-build"),
        (".github/workflows", "github-actions"),
    ]
    found: list[dict[str, str]] = []
    for rel, capability in hints:
        if (root / rel).exists():
            found.append({"capability": capability, "source": rel})
    return found


def artifact_paths(command: str, run_id: str) -> tuple[Path, Path, dict[str, str]]:
    run_dir = ARTIFACT_ROOT / command / run_id
    handoff_dir = HANDOFF_ROOT / command
    run_dir.mkdir(parents=True, exist_ok=True)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: str(run_dir / name) for name in STANDARD_ARTIFACTS}
    paths["handoff"] = str(handoff_dir / f"{run_id}.json")
    return run_dir, handoff_dir / f"{run_id}.json", paths


def build_handoff(
    *,
    command: str,
    run_id: str,
    status: str,
    target_repository: str,
    artifacts: dict[str, str],
    next_actions: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "assimilated_repository": target_repository,
        "command": command,
        "run_id": run_id,
        "status": status,
        "artifacts": artifacts,
        "next_actions": next_actions,
    }


def write_artifacts(
    *,
    command: str,
    run_id: str,
    status: str,
    risk: str,
    target_repository: str,
    target_root: Path | None,
    body: dict[str, Any],
    stdout_text: str = "",
    stderr_text: str = "",
    report_extra: str = "",
) -> dict[str, Any]:
    run_dir, external_handoff_path, artifacts = artifact_paths(command, run_id)
    next_actions = [
        {
            "command": f"ooo target report --handoff {external_handoff_path}",
            "reason": "Summarize produced target-capabilities artifacts.",
        },
        {
            "command": f"ooo auto --handoff {external_handoff_path}",
            "reason": "Continue from the bounded AgentOS handoff.",
        },
    ]
    handoff = build_handoff(
        command=command,
        run_id=run_id,
        status=status,
        target_repository=target_repository,
        artifacts=artifacts,
        next_actions=next_actions,
    )
    provenance = {
        "generated_at": utc_now(),
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "assimilated_repository": target_repository,
        "target_root": str(target_root) if target_root else None,
        "command": command,
        "risk": risk,
        "redaction": ["no secrets", "bounded metadata and path inventory only"],
    }
    result = {
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "assimilated_repository": target_repository,
        "command": command,
        "status": status,
        "risk": risk,
        "artifacts": artifacts,
        "handoff": str(external_handoff_path),
        "next_actions": next_actions,
        **body,
    }
    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "handoff.json").write_text(
        json.dumps(handoff, indent=2) + "\n",
        encoding="utf-8",
    )
    external_handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stdout.txt").write_text(stdout_text, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr_text, encoding="utf-8")
    report = [
        f"# {PLUGIN_NAME} {command} report",
        "",
        f"- status: `{status}`",
        f"- risk: `{risk}`",
        f"- assimilated_repository: `{target_repository}`",
        f"- target_root: `{target_root}`" if target_root else "- target_root: not configured",
        f"- handoff: `{external_handoff_path}`",
        "",
        report_extra,
    ]
    (run_dir / "report.md").write_text(
        "\n".join(report).rstrip() + "\n",
        encoding="utf-8",
    )
    return result


def target_repository_value(raw: str | None, root: Path | None) -> str:
    if raw:
        return raw
    if root is None:
        return "<unconfigured-target-repository>"
    return f"local/{slug(root.name)}"


def run_list_commands(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_target_root(args.target_root, required=False)
    target_repository = target_repository_value(args.target_repository, root)
    specs = [
        {
            "name": spec.name,
            "summary": spec.summary,
            "risk": spec.risk,
            "permissions": list(spec.permissions),
        }
        for spec in COMMANDS
    ]
    return write_artifacts(
        command="list-commands",
        run_id=stable_run_id("list-commands", target_repository, root),
        status="completed",
        risk="read_only",
        target_repository=target_repository,
        target_root=root,
        body={"commands": specs},
        report_extra=(
            "Command adapters are bounded by the manifest and do not execute "
            "arbitrary command text."
        ),
    )


def run_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_target_root(args.target_root, required=True)
    target_repository = target_repository_value(args.target_repository, root)
    marker_paths = [
        repo_member_path(root, item, "--require-file")
        for item in args.require_file
    ]
    missing = [relative_or_display(path, root) for path in marker_paths if not path.exists()]
    inventory = safe_file_inventory(root, limit=args.inventory_limit)
    capabilities = infer_capabilities(root)
    status = "blocked" if missing else "completed"
    body = {
        "target_root": str(root),
        "missing_required_files": missing,
        "capability_hints": capabilities,
        "inventory": inventory,
    }
    if missing:
        body.update(
            {
                "reason": "target_required_files_missing",
                "message": "Required target files were not found; review missing_required_files.",
            }
        )
    return write_artifacts(
        command="inspect",
        run_id=stable_run_id("inspect", target_repository, root),
        status=status,
        risk="read_only",
        target_repository=target_repository,
        target_root=root,
        body=body,
        report_extra=(
            f"Captured {len(inventory)} file metadata entries and "
            f"{len(capabilities)} capability hints."
        ),
    )


def run_doctor(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_target_root(args.target_root, required=False)
    target_repository = target_repository_value(args.target_repository, root)
    checks = []
    if root is None:
        checks.append(
            {
                "name": "target-root",
                "status": "blocked",
                "message": f"Set {ENV_TARGET_ROOT} or pass --target-root.",
            }
        )
        status = "blocked"
    else:
        checks.append(
            {"name": "target-root", "status": "completed", "message": str(root)}
        )
        status = "completed"
    checks.append(
        {
            "name": "managed-install",
            "status": "blocked",
            "message": "Managed install is deferred until trust/update semantics are proven.",
        }
    )
    checks.append(
        {
            "name": "destructive-trust",
            "status": "blocked",
            "message": "Destructive commands require explicit trust and --confirm-destructive.",
        }
    )
    return write_artifacts(
        command="doctor",
        run_id=stable_run_id("doctor", target_repository, root),
        status=status,
        risk="read_only",
        target_repository=target_repository,
        target_root=root,
        body={
            "checks": checks,
            "reason": None if status == "completed" else "target_dependency_not_found",
        },
        report_extra=(
            "Doctor reports configuration and deferred trust gates without dumping "
            "the environment."
        ),
    )


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target-root",
        help="Pinned local checkout for the external target repository.",
    )
    parser.add_argument(
        "--target-repository",
        help="External target repository identity, e.g. owner/repo.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="target_capabilities")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("list-commands", "doctor"):
        p = sub.add_parser(name)
        add_common(p)
    inspect_p = sub.add_parser("inspect")
    add_common(inspect_p)
    inspect_p.add_argument(
        "--require-file",
        action="append",
        default=[],
        help="Target-root-relative file that must exist.",
    )
    inspect_p.add_argument("--inventory-limit", type=int, default=60)

    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "list-commands":
        return run_list_commands(args)
    if args.command == "inspect":
        return run_inspect(args)
    if args.command == "doctor":
        return run_doctor(args)
    raise UserError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
    except UserError as exc:
        target_repository = target_repository_value(
            getattr(args, "target_repository", None),
            None,
        )
        result = write_artifacts(
            command=getattr(args, "command", "unknown"),
            run_id=stable_run_id(getattr(args, "command", "unknown"), target_repository, None),
            status="blocked",
            risk=(
                command_spec(getattr(args, "command", "doctor")).risk
                if getattr(args, "command", None) in {c.name for c in COMMANDS}
                else "read_only"
            ),
            target_repository=target_repository,
            target_root=None,
            body={
                "reason": (
                    "target_dependency_not_found"
                    if "target dependency" in str(exc)
                    else "invalid_request"
                ),
                "message": str(exc),
            },
            stderr_text=str(exc) + "\n",
            report_extra=str(exc),
        )
        print(json.dumps(result, indent=2))
        return 1 if result.get("reason") != "target_dependency_not_found" else 0
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"completed", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
