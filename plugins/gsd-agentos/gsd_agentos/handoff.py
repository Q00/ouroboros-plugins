"""Handoff bundle generation for GSD planning artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provenance import build_record, utc_now

PLANNING_PROJECTIONS = {
    ".planning/PROJECT.md": "project_context",
    ".planning/REQUIREMENTS.md": "requirements_acceptance_criteria",
    ".planning/ROADMAP.md": "staged_plan_phase_graph",
    ".planning/STATE.md": "resumability_progress_state",
}


def _excerpt(path: Path, limit: int = 8000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n\n[truncated]"


def collect_planning_artifacts(root: Path) -> list[dict[str, Any]]:
    artifacts = []
    for relative, projection in PLANNING_PROJECTIONS.items():
        path = root / relative
        artifacts.append({
            "path": relative,
            "projection": projection,
            "exists": path.is_file(),
            "excerpt": _excerpt(path),
        })
    phase_root = root / ".planning" / "phases"
    if phase_root.is_dir():
        for path in sorted(phase_root.rglob("*.md"))[:200]:
            artifacts.append({
                "path": str(path.relative_to(root)),
                "projection": "phase_evidence_or_execution_handoff",
                "exists": True,
                "excerpt": _excerpt(path, 3000),
            })
    return artifacts


def write_handoff(
    root: Path,
    command: dict,
    argv: list[str],
    *,
    status: str = "completed",
    runner_result: dict[str, Any] | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    out_dir = root / ".ouroboros" / "handoffs" / "gsd"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now()
    base = f"{stamp}-{command['canonical_name']}"
    markdown_path = out_dir / f"{base}.md"
    json_path = out_dir / f"{base}.json"
    artifacts = collect_planning_artifacts(root)
    record = build_record(
        command,
        argv=argv,
        target_repo=root,
        status=status,
        output_paths=[markdown_path, json_path],
        exit_code=(runner_result or {}).get("exit_code"),
        next_action=f"ooo gsd progress --next after reviewing {json_path}",
    )
    payload = {
        **record,
        "handoff": {
            "kind": command.get("handoff_kinds", []),
            "planning_projection": artifacts,
            "runner": runner_result,
        },
    }
    lines = [
        f"# GSD AgentOS Handoff: {command['canonical_name']}",
        "",
        f"- status: {status}",
        f"- risk: {command['risk']}",
        f"- upstream: {command.get('upstream_file')}",
        f"- argv: `{' '.join(argv)}`",
        "",
        "## AgentOS Projection",
        "",
    ]
    for item in artifacts:
        marker = "present" if item["exists"] else "missing"
        lines.append(f"- `{item['path']}` → {item['projection']} ({marker})")
    if runner_result:
        lines.extend(
            [
                "",
                "## Runner Result",
                "",
                f"- exit_code: {runner_result.get('exit_code')}",
                f"- stdout_excerpt: {runner_result.get('stdout_excerpt', '')}",
                f"- stderr_excerpt: {runner_result.get('stderr_excerpt', '')}",
            ]
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return markdown_path, json_path, payload
