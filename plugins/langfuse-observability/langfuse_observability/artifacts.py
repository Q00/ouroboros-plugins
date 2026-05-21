"""Artifact and redaction helpers for Langfuse handoffs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import PLUGIN_NAME, PLUGIN_VERSION

DEFAULT_OUTPUT_DIR = Path(".omx") / "handoffs" / "langfuse"
SECRET_KEY_RE = re.compile(r"(secret|api[_-]?key|token|password|authorization|credential)", re.I)
SECRET_VALUE_RE = re.compile(
    r"(sk-lf-[A-Za-z0-9_-]+|pk-lf-[A-Za-z0-9_-]+|bearer\s+[A-Za-z0-9._~+/=-]+)",
    re.I,
)
LARGE_TEXT_LIMIT = 500


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def parse_trace_reference(reference: str, default_host: str | None = None) -> tuple[str, str | None, str | None]:
    """Return (trace_id, host, trace_url) for a raw ID or Langfuse trace URL."""
    parsed = urlparse(reference)
    if parsed.scheme and parsed.netloc:
        parts = [part for part in parsed.path.split("/") if part]
        trace_id = None
        for marker in ("traces", "trace"):
            if marker in parts and parts.index(marker) + 1 < len(parts):
                trace_id = parts[parts.index(marker) + 1]
                break
        if not trace_id:
            raise ValueError("trace URL must contain /traces/<trace-id> or /trace/<trace-id>")
        host = f"{parsed.scheme}://{parsed.netloc}"
        return trace_id, host.rstrip("/"), reference
    if not reference.strip():
        raise ValueError("trace id cannot be empty")
    host = default_host.rstrip("/") if default_host else None
    trace_url = f"{host}/project/-/traces/{reference}" if host else None
    return reference, host, trace_url


def redact(value: Any, *, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item, key=key) for item in value]
    if isinstance(value, str):
        redacted = SECRET_VALUE_RE.sub("[REDACTED]", value)
        if len(redacted) > LARGE_TEXT_LIMIT:
            return redacted[:LARGE_TEXT_LIMIT].rstrip() + "… [TRUNCATED]"
        return redacted
    return value


def coerce_score_value(raw: str) -> str | int | float:
    lowered = raw.strip().lower()
    if lowered == "true":
        return 1
    if lowered == "false":
        return 0
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def item_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        value = value["data"]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_handoff(trace_payload: dict[str, Any], *, trace_id: str, host: str | None, trace_url: str | None) -> dict[str, Any]:
    redacted_trace = redact(trace_payload)
    observations = item_list(redacted_trace, "observations")
    scores = item_list(redacted_trace, "scores")
    raw_metrics = redacted_trace.get("metrics")
    metrics = raw_metrics if isinstance(raw_metrics, dict) else redacted_trace
    evidence: list[dict[str, Any]] = [
        {
            "kind": "trace",
            "id": str(redacted_trace.get("id") or trace_id),
            "name": redacted_trace.get("name"),
            "url": trace_url,
            "redacted": True,
        }
    ]
    for observation in observations:
        evidence.append(
            {
                "kind": "observation",
                "id": str(observation.get("id", "")),
                "name": observation.get("name") or observation.get("type"),
                "url": None,
                "redacted": True,
            }
        )
    for score in scores:
        evidence.append(
            {
                "kind": "score",
                "id": str(score.get("id", "")),
                "name": score.get("name"),
                "url": None,
                "redacted": True,
            }
        )
    errors = [obs for obs in observations if obs.get("level") == "ERROR" or obs.get("statusMessage")]
    now = utc_now()
    return {
        "schema_version": "0.1",
        "source": "langfuse",
        "status": "completed",
        "trace": {
            "id": str(redacted_trace.get("id") or trace_id),
            "url": trace_url,
            "name": redacted_trace.get("name"),
            "timestamp": redacted_trace.get("timestamp") or redacted_trace.get("createdAt"),
        },
        "summary": {
            "observations_count": len(observations),
            "scores_count": len(scores),
            "latency_ms": metrics.get("latency") or metrics.get("latencyMs"),
            "cost": metrics.get("totalCost") or metrics.get("calculatedTotalCost"),
            "error_count": len(errors),
        },
        "evidence": evidence,
        "provenance": {
            "fetched_at": now,
            "langfuse_host": host,
            "plugin": f"{PLUGIN_NAME}@{PLUGIN_VERSION}",
        },
        "audit": [
            {"event": "plugin.invoked", "at": now, "command": "inspect"},
            {"event": "plugin.permission_used", "at": now, "scope": "network:read" if host else "filesystem:read"},
            {"event": "plugin.completed", "at": now, "command": "inspect"},
        ],
        "next": {
            "handoff_recommendation": "attach_to_current_run" if observations or scores else "review_trace"
        },
        "raw_redacted": redacted_trace,
    }


def render_markdown(handoff: dict[str, Any]) -> str:
    trace = handoff["trace"]
    summary = handoff["summary"]
    lines = [
        "# Langfuse Trace Handoff",
        "",
        f"- Trace: `{trace['id']}`",
        f"- Name: {trace.get('name') or 'n/a'}",
        f"- URL: {trace.get('url') or 'n/a'}",
        f"- Observations: {summary['observations_count']}",
        f"- Scores: {summary['scores_count']}",
        f"- Errors: {summary['error_count']}",
        f"- Plugin: {handoff['provenance']['plugin']}",
        "",
        "## Evidence",
        "",
    ]
    for item in handoff["evidence"]:
        lines.append(f"- `{item['kind']}` `{item['id']}` {item.get('name') or ''}".rstrip())
    lines.extend(["", "## Next", "", handoff["next"]["handoff_recommendation"], ""])
    return "\n".join(lines)


def artifact_paths(output_dir: Path, trace_id: str) -> tuple[Path, Path]:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", trace_id)
    return output_dir / f"{safe}.json", output_dir / f"{safe}.md"
