from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .runtime import RunContext, bounded_paths, read_text, relative, repo_root, write_handoff, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ooo vercel optimize")
    parser.add_argument("project_path")
    parser.add_argument("--project")
    parser.add_argument("--limited", action="store_true")
    parser.add_argument("--out", type=Path)
    return parser


def run(argv: list[str]) -> int:
    ns = build_parser().parse_args(argv)
    ctx = RunContext(command="optimize", upstream_skill="vercel-optimize", out=ns.out, argv=argv, permissions_used=["filesystem:read", "vercel:metrics:read", "vercel:usage:read"])
    root = repo_root(Path(ns.project_path))
    project_path = (Path(ns.project_path) if Path(ns.project_path).is_absolute() else Path.cwd() / ns.project_path).resolve()
    limitations: list[str] = []
    status = "success"
    signals = _collect_safe_signals(project_path, ns.project)
    signals["project"]["path"] = relative(project_path, root)
    gate = _gate(signals)

    if not os.environ.get("VERCEL_TOKEN"):
        status = "blocked" if not ns.limited else "success"
        limitations.append("Missing VERCEL_TOKEN; Vercel metrics and usage collection blocked.")
    if not signals["project"].get("linked") and not ns.project:
        status = "blocked" if not ns.limited else "success"
        limitations.append("No Vercel project linkage detected; pass --project or run from a linked project.")
    if not signals["framework"].get("supported", False):
        limitations.append("Framework support is limited or unknown; recommendations are local-signal only.")

    write_json(ctx.run_dir / "signals.json", signals)
    write_json(ctx.run_dir / "gate.json", gate)
    report = _report(signals, gate, limitations, status)
    (ctx.run_dir / "report.md").write_text(report)
    handoff = write_handoff(
        ctx,
        status,
        [{"kind": "signals", "path": str(ctx.run_dir / "signals.json")}, {"kind": "gate", "path": str(ctx.run_dir / "gate.json")}, {"kind": "report", "path": str(ctx.run_dir / "report.md")}],
        findings=gate["candidates"],
        limitations=limitations,
        next_actions=[{"kind": "handoff_to_agentos_automation", "summary": "Implement the highest-confidence metric-backed or local-signal recommendation after resolving blockers."}],
        provenance_extra={"project_path": relative(project_path, root)},
    )
    print(json.dumps(handoff, indent=2) if status == "blocked" else report)
    return 2 if status == "blocked" else 0


def _collect_safe_signals(project_path: Path, project: str | None) -> dict[str, Any]:
    package_json = project_path / "package.json"
    vercel_json = project_path / "vercel.json"
    next_config = next((p for p in [project_path / "next.config.js", project_path / "next.config.mjs", project_path / "next.config.ts"] if p.exists()), None)
    pkg: dict[str, Any] = {}
    if package_json.exists():
        try:
            pkg = json.loads(read_text(package_json, 100_000))
        except json.JSONDecodeError:
            pkg = {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    framework = _framework(deps, next_config)
    linked = (project_path / ".vercel" / "project.json").exists()
    return {
        "project": {"path": str(project_path), "id_or_name": project, "linked": linked, "has_vercel_json": vercel_json.exists()},
        "framework": framework,
        "local_files_considered": [p.name for p in [package_json, vercel_json, next_config] if p and p.exists()],
        "metrics": {"collected": False, "reason": "adapter records blocked/limited semantics unless trusted Vercel auth is available"},
    }


def _framework(deps: dict[str, str], next_config: Path | None) -> dict[str, Any]:
    if "next" in deps or next_config:
        return {"name": "nextjs", "supported": True}
    for name in ["svelte", "@sveltejs/kit", "astro", "nuxt", "react"]:
        if name in deps:
            return {"name": name, "supported": name in {"@sveltejs/kit", "astro", "react"}}
    return {"name": "unknown", "supported": False}


def _gate(signals: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if signals["project"].get("has_vercel_json"):
        candidates.append({"rule": "project-config-review", "severity": "info", "summary": "Review vercel.json for region, function, cache, and routing settings."})
    if signals["framework"].get("name") == "nextjs":
        candidates.append({"rule": "nextjs-performance-gate", "severity": "info", "summary": "Next.js project detected; collect Vercel metrics before broad source investigation."})
    if not candidates:
        candidates.append({"rule": "metrics-required", "severity": "blocked", "summary": "No deterministic local optimization candidate; Vercel metrics are required before source deep-dive."})
    return {"gate": "metrics-first", "source_scan_allowed": any(c["severity"] != "blocked" for c in candidates), "candidates": candidates}


def _report(signals: dict[str, Any], gate: dict[str, Any], limitations: list[str], status: str) -> str:
    lines = ["# Vercel optimize report", "", f"Status: {status}", f"Framework: {signals['framework']['name']}", f"Metrics collected: {signals['metrics']['collected']}", "", "## Gate candidates"]
    for c in gate["candidates"]:
        lines.append(f"- [{c['severity']}] {c['rule']}: {c['summary']}")
    if limitations:
        lines += ["", "## Limitations", *[f"- {item}" for item in limitations]]
    lines += ["", "The adapter preserves the upstream metrics-first gate: broad source inspection is not performed unless signals justify it."]
    return "\n".join(lines) + "\n"
