from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str
    bytes: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: Path, text: str) -> Artifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return Artifact(path=path, sha256=sha256_file(path), bytes=path.stat().st_size)


def write_json(path: Path, payload: Any) -> Artifact:
    return write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def summarize_markdown(normalized: dict[str, Any], *, status: str, exit_code: int, config: str, target: str) -> str:
    summary = normalized.get("summary", {})
    finding_count = summary.get("finding_count", 0)
    lines = [
        "# Semgrep scan summary",
        "",
        f"- Status: `{status}`",
        f"- Semgrep exit code: `{exit_code}`",
        f"- Target: `{target}`",
        f"- Config: `{config}`",
        f"- Findings: `{finding_count}`",
        "",
        "## Findings by severity",
        "",
    ]
    by_severity = summary.get("by_severity", {}) if isinstance(summary, dict) else {}
    if by_severity:
        for severity, count in sorted(by_severity.items()):
            lines.append(f"- `{severity}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Top findings", ""])
    findings = normalized.get("findings", [])
    if findings:
        for finding in findings[:20]:
            start = finding.get("start", {})
            loc = f"{finding.get('path')}:{start.get('line')}:{start.get('col')}"
            lines.append(f"- `{finding.get('severity')}` `{finding.get('rule_id')}` at `{loc}` — {finding.get('message')}")
    else:
        lines.append("No findings reported by Semgrep.")
    return "\n".join(lines) + "\n"
