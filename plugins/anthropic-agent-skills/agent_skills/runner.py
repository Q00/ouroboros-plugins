from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import command_entry
from .handoff import make_handoff
from .inspect import inspect_skill
from .license_policy import classify

REFERENCE_CONVERSION_SKILLS = {"webapp-testing", "mcp-builder", "skill-creator"}


def invoke(
    skill: str,
    command: str,
    args: list[str],
    *,
    repo: Path | None = None,
    dry_run: bool = False,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    command_meta = command_entry(skill, command)
    if command_meta is None:
        return make_handoff(
            skill,
            command,
            status="blocked",
            summary="Unknown skill command.",
            inputs=args,
            next_actions=["Choose a command from the catalog."],
        )

    license_state = classify(skill)
    evidence: list[Any] = [{"type": "catalog-command", "command": command_meta}]
    loaded_files: list[str] = []

    if license_state["assimilation_mode"] == "adapter-only" and not dry_run:
        return make_handoff(
            skill,
            command,
            status="blocked",
            summary="Restricted/source-available skill is adapter-only and cannot be vendored or executed without explicit maintainer approval.",
            inputs=args,
            evidence=evidence,
            loaded_files=loaded_files,
            next_actions=[
                "Use user-provided source only after legal/trust approval; keep restricted materials out of this repository."
            ],
        )

    skill_dir = _find_skill_dir(skill, repo)
    if skill_dir:
        inspected = inspect_skill(skill_dir)
        loaded_files.append(str((skill_dir / "SKILL.md").resolve()))
        evidence.append({"type": "inspection", "value": inspected})

    if not dry_run and not skill_dir and not _is_reference_conversion(skill, artifact_dir):
        return make_handoff(
            skill,
            command,
            status="blocked",
            summary="Invocation requires a user-provided upstream skill checkout via --repo.",
            inputs=args,
            evidence=evidence,
            loaded_files=loaded_files,
            next_actions=[
                "Provide --repo pointing at an anthropics/skills checkout, use --artifact-dir for reference conversions, or run with --dry-run for contract-only validation."
            ],
        )

    permissions = command_meta.get("permissions", [])
    if _is_reference_conversion(skill, artifact_dir):
        assert artifact_dir is not None  # narrowed by _is_reference_conversion
        outputs = _write_reference_conversion(skill, command, artifact_dir, args)
        evidence.append(
            {"type": "reference-conversion", "artifact_dir": str(artifact_dir), "bounded": True}
        )
        return make_handoff(
            skill,
            command,
            status="success",
            summary="Reference conversion artifacts generated through a bounded adapter; upstream scripts were not executed.",
            inputs=args,
            outputs=outputs,
            evidence=evidence,
            permissions_used=permissions,
            loaded_files=loaded_files,
            executed_scripts=[],
        )

    summary = "Bounded adapter contract prepared; untrusted helper scripts were not executed."
    return make_handoff(
        skill,
        command,
        status="success" if dry_run else "blocked",
        summary=(
            summary
            if dry_run
            else "Runtime script execution is blocked until a command-specific trust adapter is enabled."
        ),
        inputs=args,
        evidence=evidence,
        permissions_used=permissions,
        loaded_files=loaded_files,
        executed_scripts=[],
        next_actions=(
            []
            if dry_run
            else ["Enable a command-specific trusted adapter before executing upstream scripts."]
        ),
    )


def _find_skill_dir(skill: str, repo: Path | None) -> Path | None:
    if repo is None:
        return None
    for candidate in (repo / "skills" / skill, repo / skill):
        if candidate.exists():
            return candidate
    return None


def _is_reference_conversion(skill: str, artifact_dir: Path | None) -> bool:
    return artifact_dir is not None and skill in REFERENCE_CONVERSION_SKILLS


def _write_text_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json_new(path: Path, value: Any) -> None:
    _write_text_new(path, json.dumps(value, indent=2) + "\n")


def _write_reference_conversion(
    skill: str, command: str, artifact_dir: Path, args: list[str]
) -> list[Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if skill == "webapp-testing":
        plan = artifact_dir / "webapp-testing-plan.json"
        _write_json_new(
            plan,
            {
                "adapter": "webapp-testing",
                "command": command,
                "server_lifecycle": "user-provided --server command only; no implicit process spawn",
                "evidence": ["screenshots", "console", "network", "assertions"],
                "args": args,
            },
        )
        written.append(plan)
    elif skill == "mcp-builder":
        readme = artifact_dir / "README.md"
        _write_text_new(
            readme,
            "# MCP builder scaffold\n\n"
            "Bounded AgentOS conversion scaffold. Add service-specific tools before execution.\n",
        )
        pkg = artifact_dir / "package.json"
        _write_json_new(
            pkg,
            {
                "name": "agentos-mcp-server",
                "version": "0.1.0",
                "type": "module",
                "scripts": {"build": "tsc --noEmit"},
                "dependencies": {"@modelcontextprotocol/sdk": "latest", "zod": "latest"},
            },
        )
        src = artifact_dir / "src" / "index.ts"
        _write_text_new(
            src,
            "import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';\n\n"
            "export const server = new McpServer({ name: 'agentos-mcp-server', version: '0.1.0' });\n",
        )
        written.extend([readme, pkg, src])
    elif skill == "skill-creator":
        manifest = artifact_dir / "ouroboros.plugin.json"
        _write_json_new(
            manifest,
            {
                "schema_version": "0.1",
                "name": "converted-agent-skill",
                "version": "0.1.0",
                "source": {"type": "local_path", "path": "."},
                "commands": [
                    {
                        "namespace": "converted-skill",
                        "name": "run",
                        "summary": "Run converted Agent Skill workflow",
                        "usage": "ooo converted-skill run",
                        "risk": "write",
                    }
                ],
                "capabilities": [{"name": "handoff", "access": "attach"}],
                "permissions": [
                    {"scope": "filesystem:read", "risk": "read_only", "required": True}
                ],
                "entrypoint": {"type": "command", "command": "python -m converted_skill"},
            },
        )
        notes = artifact_dir / "CONVERSION.md"
        _write_text_new(
            notes,
            "# Agent Skill conversion notes\n\n"
            "Review command names, permissions, license state, and handoff schema before trusting.\n",
        )
        written.extend([manifest, notes])
    return [{"path": str(path), "bytes": path.stat().st_size} for path in written]
