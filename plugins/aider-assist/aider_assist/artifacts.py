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
    re.compile(r"(?i)(sk-[a-z0-9_-]{12,})"),
]


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        def repl(match: re.Match[str]) -> str:
            if len(match.groups()) >= 2:
                return f"{match.group(1)}=<redacted>"
            if match.group(1).lower() == "bearer":
                return "bearer <redacted>"
            return "<redacted>"
        value = pattern.sub(repl, value)
    return value


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
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
    safe_payload = redact_value(payload)
    path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True, default=default) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(redact(content), encoding="utf-8")


def write_handoff(path: Path, *, command: str, message: str, selected_context: list[str], status: str, aider_version: str, summary: str) -> None:
    next_step = "Review the generated artifact and continue with the next bounded Ouroboros command."
    if command == "architect":
        next_step = "Review `plan.md`; if implementation is approved, promote the plan into an explicit `aider edit` invocation with editable file bounds."
    body = f"""# Aider Assist Handoff

## Command
{command}

## User Goal
{redact(message)}

## Selected Context
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
- Full interactive Aider session passthrough is deferred until transcript capture, pre/post diff, trust-boundary, and post-session handoff semantics are designed.

## Recommended Next Step
{next_step}
"""
    path.write_text(body, encoding="utf-8")
