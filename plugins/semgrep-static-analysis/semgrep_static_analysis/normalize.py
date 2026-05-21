from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any


class SemgrepOutputError(ValueError):
    """Raised when Semgrep JSON cannot be normalized."""


def load_semgrep_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise SemgrepOutputError(f"Semgrep JSON output is malformed: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SemgrepOutputError("Semgrep JSON output must be an object")
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise SemgrepOutputError("Semgrep JSON output field 'results' must be an array")
    return payload


def _position(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {"line": None, "col": None}
    return {"line": value.get("line"), "col": value.get("col")}


def _fingerprint(rule_id: str, path: str, start: dict[str, int | None], message: str) -> str:
    material = json.dumps(
        {
            "rule_id": rule_id,
            "path": path,
            "line": start.get("line"),
            "col": start.get("col"),
            "message": message,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def normalize_semgrep_output(
    payload: dict[str, Any], *, tool_version: str | None = None, scan_root: str | None = None
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for idx, result in enumerate(payload.get("results", [])):
        if not isinstance(result, dict):
            continue
        extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
        rule_id = str(result.get("check_id", "unknown"))
        path = str(result.get("path", ""))
        message = str(extra.get("message", ""))
        severity = str(extra.get("severity", "INFO"))
        start = _position(result.get("start"))
        end = _position(result.get("end"))
        metadata = extra.get("metadata") if isinstance(extra.get("metadata"), dict) else {}
        finding = {
            "schema_version": "0.1",
            "tool": "semgrep",
            "tool_version": tool_version or payload.get("version") or "unknown",
            "rule_id": rule_id,
            "severity": severity,
            "message": message,
            "path": path,
            "path_trust": "semgrep-reported",
            "scan_root": scan_root,
            "start": start,
            "end": end,
            "metadata": metadata,
            "fix_available": bool(extra.get("fix") or extra.get("fix_regex")),
            "fingerprint": result.get("fingerprint") or _fingerprint(rule_id, path, start, message),
            "raw_result_ref": f"semgrep.raw.json#/results/{idx}",
        }
        findings.append(finding)

    by_severity = Counter(f["severity"] for f in findings)
    by_rule = Counter(f["rule_id"] for f in findings)
    by_path = Counter(f["path"] for f in findings)
    return {
        "schema_version": "0.1",
        "tool": "semgrep",
        "tool_version": tool_version or payload.get("version") or "unknown",
        "summary": {
            "finding_count": len(findings),
            "by_severity": dict(sorted(by_severity.items())),
            "by_rule": dict(sorted(by_rule.items())),
            "by_path": dict(sorted(by_path.items())),
        },
        "findings": findings,
    }
