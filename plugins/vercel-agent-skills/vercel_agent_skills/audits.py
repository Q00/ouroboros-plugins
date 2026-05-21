from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

from .runtime import RunContext, bounded_paths, load_rule_names, load_upstream_skill, read_text, relative, write_handoff, write_json

SKILL_MAP = {
    "react-best-practices": "react-best-practices",
    "composition-patterns": "composition-patterns",
    "react-native-skills": "react-native-skills",
    "react-view-transitions": "react-view-transitions",
    "web-design-guidelines": "web-design-guidelines",
}

HEURISTICS = {
    "react-best-practices": [("possible-waterfall", "await "), ("bundle-barrel-import", "from './index"), ("memoization-review", "useMemo"), ("image-optimization", "<img")],
    "composition-patterns": [("boolean-prop-surface", "={true}"), ("provider-boundary", "Provider"), ("render-prop", "children(")],
    "react-native-skills": [("flatlist-performance", "FlatList"), ("inline-style", "style={{"), ("expo-image", "Image")],
    "react-view-transitions": [("view-transition-opportunity", "viewTransition"), ("shared-element-identity", "key={"), ("suspense-reveal", "Suspense")],
    "web-design-guidelines": [("focus-state", ":focus"), ("aria", "aria-"), ("image-alt", "<img")],
}


def build_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"ooo vercel {command}")
    parser.add_argument("target")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--out", type=Path)
    if command == "react-view-transitions":
        parser.add_argument("--mode", choices=["audit", "plan", "implement"], default="audit")
    if command == "web-design-guidelines":
        parser.add_argument("--guidelines-url", default="https://vercel.com/design/guidelines")
    return parser


def run(command: str, argv: list[str]) -> int:
    ns = build_parser(command).parse_args(argv)
    ctx = RunContext(command=command, upstream_skill=SKILL_MAP[command], out=ns.out, argv=argv)
    if command == "web-design-guidelines":
        ctx.permissions_used.append("network:read")
    if command == "react-view-transitions" and ns.mode == "implement":
        return _blocked_implement(ctx)
    upstream = load_upstream_skill(ctx)
    rules = load_rule_names(ctx)
    files = bounded_paths(ns.target)
    findings = _findings(command, files)
    if command == "web-design-guidelines":
        guideline = _fetch_guideline(ns.guidelines_url)
        (ctx.run_dir / "guidelines-source.txt").write_text(guideline[:4000] + "\n")
        provenance_extra = {"guidelines_url": ns.guidelines_url}
    else:
        provenance_extra = {}
    report = _render_report(command, files, findings, rules, upstream, getattr(ns, "mode", "audit"))
    report_path = ctx.run_dir / ("report.json" if ns.format == "json" else "report.md")
    if ns.format == "json":
        write_json(report_path, {"command": command, "files": [relative(p) for p in files], "rules": rules, "findings": findings})
    else:
        report_path.write_text(report)
    handoff = write_handoff(ctx, "success", [{"kind": "report", "path": str(report_path)}, {"kind": "upstream_skill", "path": str(ctx.upstream_dir / "SKILL.md")}], findings=findings, limitations=["Static adapter findings are heuristic; upstream SKILL.md remains the behavioral source for agent review."], next_actions=[{"kind": "handoff_to_agentos_automation", "summary": "Use findings and upstream rules to plan targeted code changes."}], provenance_extra=provenance_extra)
    print(json.dumps(handoff, indent=2) if ns.format == "json" else report)
    return 0


def _blocked_implement(ctx: RunContext) -> int:
    handoff = write_handoff(ctx, "blocked", [], limitations=["react-view-transitions implement mode is intentionally blocked in v0 because write semantics and patch ownership are not locked."], next_actions=[{"kind": "rerun", "summary": "Use --mode audit or --mode plan for a read-only handoff."}])
    print(json.dumps(handoff, indent=2))
    return 2


def _findings(command: str, files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in files:
        text = read_text(path)
        lines = text.splitlines()
        for rule, needle in HEURISTICS.get(command, []):
            for idx, line in enumerate(lines, start=1):
                if needle in line:
                    findings.append({"rule": rule, "path": relative(path), "line": idx, "severity": "info", "summary": f"Review `{needle.strip()}` against upstream {command} guidance."})
                    break
    return findings


def _render_report(command: str, files: list[Path], findings: list[dict[str, Any]], rules: list[str], upstream: str, mode: str) -> str:
    out = [f"# Vercel {command} {mode} report", "", f"Reviewed files: {len(files)}", f"Upstream rules/references available: {len(rules)}", ""]
    if findings:
        out.append("## Findings")
        for f in findings:
            out.append(f"- `{f['path']}:{f['line']}` [{f['rule']}] {f['summary']}")
    else:
        out.extend(["## Findings", "- No heuristic findings; use upstream skill guidance for deeper agent review."])
    out.extend(["", "## Progressive disclosure", "The adapter loaded the selected upstream `SKILL.md` for this command only.", f"Upstream instruction bytes loaded: {len(upstream.encode('utf-8'))}"])
    return "\n".join(out) + "\n"


def _fetch_guideline(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - URL is explicit user/plugin input and recorded in provenance.
            return response.read(64_000).decode("utf-8", errors="replace")
    except Exception as exc:  # network trust may be unavailable
        return f"FETCH_BLOCKED_OR_FAILED: {type(exc).__name__}: {exc}"
