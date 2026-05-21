from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

PLUGIN = "vercel-agent-skills"
VERSION = "0.1.0"
UPSTREAM_REPOSITORY = "https://github.com/vercel-labs/agent-skills"
UPSTREAM_COMMIT = "7defe2d03c5fa8e39b63b12648c1fa10131b422a"
DEFAULT_RUN_ROOT = Path(".ouroboros/plugins/vercel-agent-skills/runs")
TEXT_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css", ".scss", ".md", ".mdx", ".json"}
SECRET_RE = re.compile(r"(?i)(vercel[_-]?token|token|authorization|bearer|secret|password|api[_-]?key)([\s:=]+)([^\s'\"`]+)")
LONG_SECRET_RE = re.compile(r"\b([A-Za-z0-9_\-]{24,})\b")

@dataclass
class RunContext:
    command: str
    upstream_skill: str
    risk: str = "read_only"
    permissions_used: list[str] = field(default_factory=lambda: ["filesystem:read"])
    out: Path | None = None
    argv: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.out is None:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            digest = hashlib.sha1((self.command + "\0" + "\0".join(self.argv) + ts).encode()).hexdigest()[:8]
            self.run_dir = DEFAULT_RUN_ROOT / f"{ts}-{self.command}-{digest}"
        else:
            self.run_dir = self.out
        self.run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def upstream_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "upstream" / "agent-skills" / "skills" / self.upstream_skill


def redact(value: str) -> str:
    value = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", value)
    return LONG_SECRET_RE.sub(lambda m: "[REDACTED]" if _looks_secret(m.group(1)) else m.group(1), value)


def _looks_secret(value: str) -> bool:
    has_alpha = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_alpha and (has_digit or "_" in value or "-" in value) and len(value) >= 32


def repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def bounded_paths(target: str, root: Path | None = None) -> list[Path]:
    root = (root or repo_root()).resolve()
    raw = Path(target)
    matches: list[Path] = []
    if any(ch in target for ch in "*?["):
        matches = [p for p in root.glob(target) if p.is_file()]
    else:
        path = (raw if raw.is_absolute() else root / raw).resolve()
        if path.is_dir():
            matches = [p for p in path.rglob("*") if p.is_file() and p.suffix in TEXT_EXTENSIONS]
        elif path.is_file():
            matches = [path]
        else:
            raise FileNotFoundError(f"target not found: {target}")
    bounded: list[Path] = []
    for p in matches:
        rp = p.resolve()
        try:
            rp.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path escapes repository boundary: {p}") from exc
        if rp.suffix in TEXT_EXTENSIONS and not any(part in {".git", "node_modules", ".next", "dist", "build"} for part in rp.parts):
            bounded.append(rp)
    return sorted(dict.fromkeys(bounded))


def read_text(path: Path, limit: int = 250_000) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")


def load_upstream_skill(ctx: RunContext) -> str:
    skill = ctx.upstream_dir / "SKILL.md"
    return read_text(skill) if skill.exists() else ""


def load_rule_names(ctx: RunContext) -> list[str]:
    rules = ctx.upstream_dir / "rules"
    if not rules.exists():
        refs = ctx.upstream_dir / "references"
        if refs.exists():
            return [p.stem for p in refs.glob("*.md") if not p.name.startswith("_")]
        return []
    return [p.stem for p in rules.glob("*.md") if not p.name.startswith("_")]


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_handoff(ctx: RunContext, status: str, artifacts: list[dict[str, str]], *, findings: list[dict[str, Any]] | None = None, limitations: list[str] | None = None, next_actions: list[dict[str, str]] | None = None, provenance_extra: dict[str, str] | None = None) -> dict[str, Any]:
    handoff = {
        "schema_version": "0.1",
        "plugin": PLUGIN,
        "upstream": {"repository": UPSTREAM_REPOSITORY, "commit": UPSTREAM_COMMIT, "skill": ctx.upstream_skill},
        "command": {"namespace": "vercel", "name": ctx.command, "argv": [redact(a) for a in ctx.argv]},
        "status": status,
        "risk": ctx.risk,
        "permissions_used": ctx.permissions_used,
        "artifacts": artifacts,
        "findings": findings or [],
        "limitations": limitations or [],
        "next_actions": next_actions or [],
        "provenance": {"run_dir": str(ctx.run_dir), **(provenance_extra or {})},
    }
    write_json(ctx.run_dir / "handoff.json", handoff)
    event_type = "plugin.completed" if status in {"success", "blocked"} else "plugin.failed"
    audit = {
        "schema_version": "0.1",
        "event_type": event_type,
        "occurred_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "plugin": {"name": PLUGIN, "version": VERSION, "source_type": "local_path"},
        "command": {"namespace": "vercel", "name": ctx.command, "argv": [redact(a) for a in ctx.argv]},
        "trust_state": "blocked" if status == "blocked" else "trusted",
        "capabilities_used": ["ledger", "provenance", "handoff", "progress"],
        "permissions_used": ctx.permissions_used,
        "provenance": {k: str(v) for k, v in handoff["provenance"].items()},
        "result": {"status": status, "message": (limitations or ["completed"])[0] if status != "success" else "completed"},
    }
    write_json(ctx.run_dir / "audit-event.json", audit)
    return handoff


def relative(path: Path, root: Path | None = None) -> str:
    root = (root or repo_root()).resolve()
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)
