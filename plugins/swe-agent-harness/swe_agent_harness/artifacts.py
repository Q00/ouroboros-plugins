from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARTIFACT_PATTERNS = {
    "trajectory": ["*.traj", "*.traj.json", "*.trajectory.json"],
    "prediction": ["*.pred", "*.pred.json", "predictions*.json"],
    "patch": ["*.patch", "*.diff"],
    "log": ["*.log", "*.trace.log", "*.debug.log", "*.info.log"],
    "config": ["config.yaml", "config.yml", "*.config.yaml", "*.config.yml"],
}
NORMALIZED_NAMES = {
    "trajectory": "trajectory.traj",
    "prediction": "prediction.pred",
    "patch": "patch.diff",
}

SECRET_KEYS = ("key", "token", "secret", "password", "credential")
STATUS_VALUES = {"blocked", "failed", "completed", "submitted", "partial", "cancelled"}


@dataclass(frozen=True)
class ArtifactHit:
    kind: str
    path: Path
    relpath: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id(prefix: str = "swe-agent") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_output_dir(value: str | None, run_id: str | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return (Path.cwd() / ".agentos" / "swe-agent" / (run_id or make_run_id())).resolve()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if any(part in key.lower() for part in SECRET_KEYS):
                out[key] = "<redacted>"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def discover_artifacts(root: Path) -> list[ArtifactHit]:
    root = root.resolve()
    hits: list[ArtifactHit] = []
    seen: set[Path] = set()
    for kind, patterns in ARTIFACT_PATTERNS.items():
        for pattern in patterns:
            for path in sorted(root.rglob(pattern)):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                hits.append(ArtifactHit(kind=kind, path=path, relpath=path.relative_to(root).as_posix()))
    return hits


def copy_first_kind(bundle_dir: Path, hits: list[ArtifactHit], kind: str) -> str | None:
    for hit in hits:
        if hit.kind == kind:
            target = bundle_dir / NORMALIZED_NAMES[kind]
            shutil.copyfile(hit.path, target)
            return target.name
    return None


def infer_status(returncode: int | None, hits: list[ArtifactHit], explicit: str | None = None) -> str:
    if explicit:
        if explicit not in STATUS_VALUES:
            raise ValueError(f"unknown status {explicit!r}; expected one of {sorted(STATUS_VALUES)}")
        return explicit
    if any(hit.kind == "patch" for hit in hits):
        return "submitted"
    if returncode is None:
        return "partial" if hits else "failed"
    if returncode == 0:
        return "completed"
    return "failed"


def edited_files_from_patch(patch_path: Path | None) -> list[str]:
    if not patch_path or not patch_path.is_file():
        return []
    files: set[str] = set()
    for line in patch_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                candidate = parts[3]
                files.add(candidate[2:] if candidate.startswith("b/") else candidate)
        elif line.startswith("+++ b/"):
            files.add(line[6:])
    return sorted(files)


def summarize_hits(hits: list[ArtifactHit]) -> dict[str, Any]:
    by_kind: dict[str, list[str]] = {}
    for hit in hits:
        by_kind.setdefault(hit.kind, []).append(hit.relpath)
    return {"counts": {kind: len(paths) for kind, paths in sorted(by_kind.items())}, "paths": by_kind}


def build_run_spec(
    *,
    command: str,
    upstream_command: list[str],
    run_id: str,
    artifact_dir: Path,
    upstream_output_dir: Path,
    agentos_flags: dict[str, Any],
    status: str = "partial",
) -> dict[str, Any]:
    return {
        "schema_version": "agentos.swe-agent.run-spec.v0.1",
        "run_id": run_id,
        "command": command,
        "status": status,
        "created_at": utc_now(),
        "artifact_dir": artifact_dir.as_posix(),
        "upstream_output_dir": upstream_output_dir.as_posix(),
        "upstream_command": upstream_command,
        "agentos_flags": redact(agentos_flags),
        "safety": {
            "host_patch_application_default": "disabled",
            "open_pr_default": "disabled",
            "secrets_policy": "redact key/token/secret/password/credential fields from AgentOS metadata",
        },
    }


def write_audit(bundle_dir: Path, *, status: str, permissions: list[str], command: list[str], message: str | None = None) -> dict[str, Any]:
    events = [
        {"type": "plugin.invoked", "timestamp": utc_now(), "command": command},
    ]
    for permission in permissions:
        events.append({"type": "plugin.permission_used", "timestamp": utc_now(), "permission": permission})
    terminal = "plugin.failed" if status in {"blocked", "failed"} else "plugin.completed"
    events.append({"type": terminal, "timestamp": utc_now(), "status": status, "message": message or ""})
    payload = {"schema_version": "agentos.swe-agent.audit-summary.v0.1", "status": status, "events": events}
    write_json(bundle_dir / "audit-summary.json", payload)
    return payload


def write_provenance(
    bundle_dir: Path,
    *,
    run_spec: dict[str, Any],
    hits: list[ArtifactHit],
    source_output_dir: Path,
    status: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": "agentos.swe-agent.provenance.v0.1",
        "created_at": utc_now(),
        "status": status,
        "swe_agent_repo": "https://github.com/SWE-agent/SWE-agent",
        "swe_agent_version": "external executable resolved at runtime",
        "source_output_dir": source_output_dir.as_posix(),
        "artifact_paths": summarize_hits(hits)["paths"],
        "run_spec": {
            "run_id": run_spec.get("run_id"),
            "command": run_spec.get("command"),
            "upstream_command": run_spec.get("upstream_command"),
            "upstream_output_dir": run_spec.get("upstream_output_dir"),
        },
    }
    write_json(bundle_dir / "provenance.json", payload)
    return payload


def write_handoff(bundle_dir: Path, *, run_spec: dict[str, Any], hits: list[ArtifactHit], status: str) -> dict[str, Any]:
    normalized_patch = bundle_dir / "patch.diff"
    edited_files = edited_files_from_patch(normalized_patch if normalized_patch.exists() else None)
    summary = summarize_hits(hits)
    next_steps = ["inspect patch and trajectory", "run target repository tests", "handoff to ooo auto or reviewers"]
    if normalized_patch.exists():
        next_steps.insert(1, "apply patch only through an explicit trusted action")
    next_steps.append("open PR only through a separately trusted GitHub write path")
    payload = {
        "schema_version": "agentos.swe-agent.handoff.v0.1",
        "run_id": run_spec.get("run_id"),
        "status": status,
        "artifact_dir": bundle_dir.as_posix(),
        "upstream_command": run_spec.get("upstream_command", []),
        "permissions_exercised": run_spec.get("permissions_exercised", []),
        "artifacts": summary,
        "edited_files": edited_files,
        "next_steps": next_steps,
    }
    write_json(bundle_dir / "handoff.json", payload)
    lines = [
        "# SWE-agent AgentOS Handoff",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Status: `{status}`",
        f"- Artifact directory: `{bundle_dir.as_posix()}`",
        f"- Upstream command: `{' '.join(run_spec.get('upstream_command', []))}`",
        "",
        "## Artifacts",
    ]
    for kind, paths in sorted(summary["paths"].items()):
        lines.append(f"- {kind}: {len(paths)} file(s)")
        for path in paths[:10]:
            lines.append(f"  - `{path}`")
    lines += ["", "## Edited files"]
    lines += [f"- `{path}`" for path in edited_files] or ["- None detected"]
    lines += ["", "## Next steps"]
    lines += [f"- {step}" for step in next_steps]
    lines += ["", "Host patch application and PR creation are intentionally not automatic.", ""]
    (bundle_dir / "handoff.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def collect_bundle(
    *,
    source_output_dir: Path,
    bundle_dir: Path,
    run_spec: dict[str, Any],
    status: str | None = None,
    returncode: int | None = None,
) -> dict[str, Any]:
    ensure_dir(bundle_dir)
    source_output_dir = source_output_dir.resolve()
    hits = discover_artifacts(source_output_dir) if source_output_dir.exists() else []
    final_status = infer_status(returncode, hits, status)
    run_spec = dict(run_spec)
    run_spec["status"] = final_status
    run_spec.setdefault("permissions_exercised", [])
    write_json(bundle_dir / "run-spec.json", run_spec)
    (bundle_dir / "upstream-command.txt").write_text(" ".join(run_spec.get("upstream_command", [])) + "\n", encoding="utf-8")
    if source_output_dir.exists() and source_output_dir != (bundle_dir / "swe-agent-output").resolve():
        target = bundle_dir / "swe-agent-output"
        if not target.exists():
            shutil.copytree(source_output_dir, target)
    for kind in ("patch", "prediction", "trajectory"):
        copy_first_kind(bundle_dir, hits, kind)
    provenance = write_provenance(bundle_dir, run_spec=run_spec, hits=hits, source_output_dir=source_output_dir, status=final_status)
    handoff = write_handoff(bundle_dir, run_spec=run_spec, hits=hits, status=final_status)
    audit = write_audit(bundle_dir, status=final_status, permissions=run_spec.get("permissions_exercised", []), command=run_spec.get("upstream_command", []))
    return {"status": final_status, "run_spec": run_spec, "artifacts": summarize_hits(hits), "provenance": provenance, "handoff": handoff, "audit": audit}


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    required = ["run-spec.json", "provenance.json", "audit-summary.json", "handoff.json", "handoff.md"]
    missing = [name for name in required if not (bundle_dir / name).exists()]
    status = "valid" if not missing else "invalid"
    return {"status": status, "missing": missing, "artifact_dir": bundle_dir.resolve().as_posix()}
