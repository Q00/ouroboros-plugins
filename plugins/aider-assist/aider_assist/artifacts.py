from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)=([^\s]+)"),
    re.compile(r"(?i)(bearer)\s+[a-z0-9._~+/-]+"),
]


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        value = pattern.sub(lambda m: f"{m.group(1)}=<redacted>" if len(m.groups()) >= 2 else "<redacted>", value)
    return value


def run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def root(repo_root: Path, rid: str) -> Path:
    return repo_root / ".omx" / "artifacts" / "plugins" / "aider-assist" / rid


def write_json(path: Path, payload: Any) -> None:
    def default(obj: Any) -> Any:
        if is_dataclass(obj):
            return asdict(obj)
        raise TypeError(type(obj).__name__)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=default) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(redact(content), encoding="utf-8")


def write_handoff(path: Path, *, command: str, message: str, selected_context: list[str], status: str, aider_version: str, summary: str) -> None:
    body = f"""# Aider Assist Handoff

## Command
{command}

## User Goal
{redact(message)}

## Selected Read-only Context
{chr(10).join(f'- {p}' for p in selected_context) or '- (none)'}

## Aider Version
{redact(aider_version)}

## Permissions Used
- filesystem:read
- shell:execute
- network:write

## Result Status
{status}

## Summary of Result
{redact(summary)}

## Known Gaps
- Write-capable edit/fix and architect polish are implemented in later stacked PRs.
- Full interactive Aider session passthrough is deferred by issue #44.

## Recommended Next Step
Review `answer.md`, then decide whether to run a bounded `aider edit` PR2+ workflow.
"""
    path.write_text(body, encoding="utf-8")
