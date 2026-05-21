from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Any

from . import PLUGIN_NAME, PLUGIN_VERSION
from .artifacts import Artifact, sha256_file, summarize_markdown, write_json, write_text
from .audit import audit_event
from .normalize import SemgrepOutputError, load_semgrep_json, normalize_semgrep_output
from .paths import resolve_bounded_path
from .runner import ScanRequest, SemgrepBlocked, SemgrepExecutionError, prepare_scan, run_semgrep


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _artifact_map(artifacts: list[Artifact], *, root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        result[artifact.path.name] = {
            "path": artifact.path.relative_to(root).as_posix() if artifact.path.is_relative_to(root) else str(artifact.path),
            "sha256": artifact.sha256,
            "bytes": artifact.bytes,
        }
    return result


def _status_for_returncode(code: int) -> str:
    if code in {0, 1}:
        return "success"
    return "failed"


def _resolve_run_dir(root: Path, output_dir: str, run_id: str) -> Path:
    output_base = Path(output_dir)
    if not output_base.is_absolute():
        output_base = root / output_base
    requested = (output_base / run_id).resolve(strict=False)
    return resolve_bounded_path(
        str(requested), root=root, label="output_dir", must_exist=False
    ).absolute


def _write_blocked_response(
    *, root: Path, run_id: str, message: str, argv: list[str], trust_state: str
) -> int:
    fallback_run_dir = (root / ".omx" / "artifacts" / "semgrep" / run_id).resolve(strict=False)
    fallback_run_dir.mkdir(parents=True, exist_ok=True)
    event = audit_event(
        "plugin.failed",
        command_name="scan",
        argv=argv,
        status="blocked",
        message=message,
        permissions_used=[],
        provenance={"plugin_version": PLUGIN_VERSION, "audit_payload_mode": "plugin-prepared"},
        trust_state=trust_state,
    )
    audit_artifact = write_json(fallback_run_dir / "semgrep.audit.json", {"events": [event]})
    payload = {
        "status": "blocked",
        "message": message,
        "artifact_dir": str(fallback_run_dir),
        "audit_path": str(audit_artifact.path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 3


def scan(args: argparse.Namespace) -> int:
    root = Path(args.repository_root).resolve(strict=False)
    run_id = _run_id()
    try:
        run_dir = _resolve_run_dir(root, args.output_dir, run_id)
    except ValueError as exc:
        return _write_blocked_response(
            root=root,
            run_id=run_id,
            message=str(exc),
            argv=sys.argv[1:],
            trust_state=args.trust_state,
        )
    request = ScanRequest(
        root=root,
        target_path=args.target_path,
        config=args.config,
        output_dir=run_dir,
        semgrep_bin=args.semgrep_bin,
        allow_remote_config=args.allow_remote_config,
        sarif=args.sarif,
        error_on_findings=args.error,
        includes=tuple(args.include or ()),
        excludes=tuple(args.exclude or ()),
    )

    try:
        prepared = prepare_scan(request)
    except (SemgrepBlocked, ValueError) as exc:
        return _write_blocked_response(
            root=root,
            run_id=run_id,
            message=str(exc),
            argv=sys.argv[1:],
            trust_state=args.trust_state,
        )

    artifacts: list[Artifact] = []
    invoked = audit_event(
        "plugin.invoked",
        command_name="scan",
        argv=prepared.argv[1:],
        status="success",
        message="Semgrep scan invocation prepared.",
        permissions_used=prepared.permissions_used,
        provenance={
            "plugin_version": PLUGIN_VERSION,
            "audit_payload_mode": "plugin-prepared",
            "target_path": prepared.target.relative,
            "config": prepared.config_display,
            "config_kind": prepared.config_kind,
        },
        trust_state=args.trust_state,
    )
    permission_used = audit_event(
        "plugin.permission_used",
        command_name="scan",
        argv=prepared.argv[1:],
        status="success",
        message="Semgrep scan used declared read-only permissions.",
        permissions_used=prepared.permissions_used,
        provenance={"permissions": ",".join(prepared.permissions_used), "audit_payload_mode": "plugin-prepared"},
        trust_state=args.trust_state,
    )

    try:
        run = run_semgrep(prepared, cwd=root, timeout_seconds=args.timeout_seconds)
        artifacts.append(write_text(run_dir / "semgrep.raw.json", run.stdout))
        artifacts.append(write_text(run_dir / "semgrep.stderr.txt", run.stderr))
        semgrep_payload = load_semgrep_json(run.stdout)
        normalized = normalize_semgrep_output(
            semgrep_payload, tool_version=run.version, scan_root=prepared.target.relative
        )
        status = _status_for_returncode(run.returncode)
        artifacts.append(write_json(run_dir / "semgrep.findings.json", normalized))
        artifacts.append(
            write_text(
                run_dir / "semgrep.summary.md",
                summarize_markdown(
                    normalized,
                    status=status,
                    exit_code=run.returncode,
                    config=prepared.config_display,
                    target=prepared.target.relative,
                ),
            )
        )
        if prepared.sarif_path is not None and prepared.sarif_path.exists():
            artifacts.append(Artifact(path=prepared.sarif_path, sha256=sha256_file(prepared.sarif_path), bytes=prepared.sarif_path.stat().st_size))
        artifact_index = _artifact_map(artifacts, root=root)
        provenance = {
            "schema_version": "0.1",
            "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION},
            "tool": {"name": "semgrep", "version": run.version},
            "command": {
                "namespace": "semgrep",
                "name": "scan",
                "argv": prepared.argv[1:],
            },
            "target_path": prepared.target.relative,
            "config": prepared.config_display,
            "config_kind": prepared.config_kind,
            "metrics": "off",
            "version_check": "disabled",
            "network_mode": "enabled" if prepared.config_kind == "remote" else "disabled",
            "exit_code": run.returncode,
            "duration_seconds": run.duration_seconds,
            "result_counts": normalized["summary"],
            "artifacts": artifact_index,
            "artifact_index_note": "final artifact index is refreshed after audit and handoff artifacts are written; provenance intentionally does not self-hash",
        }
        artifacts.append(write_json(run_dir / "semgrep.provenance.json", provenance))
        final_event = audit_event(
            "plugin.completed" if status == "success" else "plugin.failed",
            command_name="scan",
            argv=prepared.argv[1:],
            status=status,
            message="Semgrep scan completed." if status == "success" else f"Semgrep scan failed with exit code {run.returncode}.",
            permissions_used=prepared.permissions_used,
            provenance={
                "semgrep_version": run.version,
                "audit_payload_mode": "plugin-prepared",
                "exit_code": str(run.returncode),
                "finding_count": str(normalized["summary"]["finding_count"]),
            },
            trust_state=args.trust_state,
        )
        audit_payload = {"events": [invoked, permission_used, final_event]}
        artifacts.append(write_json(run_dir / "semgrep.audit.json", audit_payload))
        artifact_index = _artifact_map(artifacts, root=root)
        handoff = {
            "schema_version": "0.1",
            "plugin": PLUGIN_NAME,
            "command": "semgrep scan",
            "status": status,
            "artifact_dir": str(run_dir.relative_to(root) if run_dir.is_relative_to(root) else run_dir),
            "raw_json": artifact_index.get("semgrep.raw.json", {}).get("path"),
            "findings": artifact_index.get("semgrep.findings.json", {}).get("path"),
            "summary": artifact_index.get("semgrep.summary.md", {}).get("path"),
            "provenance": str((run_dir / "semgrep.provenance.json").relative_to(root) if (run_dir / "semgrep.provenance.json").is_relative_to(root) else run_dir / "semgrep.provenance.json"),
            "audit": str((run_dir / "semgrep.audit.json").relative_to(root) if (run_dir / "semgrep.audit.json").is_relative_to(root) else run_dir / "semgrep.audit.json"),
            "downstream": {
                "can_triage": True,
                "can_generate_remediation_seed": True,
                "raw_semgrep_output_preserved": True,
            },
        }
        artifacts.append(write_json(run_dir / "semgrep.handoff.json", handoff))
        provenance["artifacts"] = _artifact_map(
            [artifact for artifact in artifacts if artifact.path.name != "semgrep.provenance.json"],
            root=root,
        )
        write_json(run_dir / "semgrep.provenance.json", provenance)
        response = {
            "status": status,
            "semgrep_exit_code": run.returncode,
            "artifact_dir": str(run_dir),
            "finding_count": normalized["summary"]["finding_count"],
            "handoff_path": str(run_dir / "semgrep.handoff.json"),
        }
        print(json.dumps(response, indent=2, sort_keys=True))
        return run.returncode
    except (SemgrepExecutionError, SemgrepOutputError) as exc:
        event = audit_event(
            "plugin.failed",
            command_name="scan",
            argv=prepared.argv[1:],
            status="failed",
            message=str(exc),
            permissions_used=prepared.permissions_used,
            provenance={"target_path": prepared.target.relative, "config": prepared.config_display, "audit_payload_mode": "plugin-prepared"},
            trust_state=args.trust_state,
        )
        write_json(run_dir / "semgrep.audit.json", {"events": [invoked, permission_used, event]})
        print(json.dumps({"status": "failed", "message": str(exc), "artifact_dir": str(run_dir)}, indent=2, sort_keys=True))
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="semgrep-static-analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="Run a bounded read-only Semgrep scan")
    scan_parser.add_argument("target_path")
    scan_parser.add_argument("--config", required=True)
    scan_parser.add_argument("--repository-root", default=".")
    scan_parser.add_argument("--output-dir", default=".omx/artifacts/semgrep")
    scan_parser.add_argument("--semgrep-bin", default="semgrep")
    scan_parser.add_argument("--allow-remote-config", action="store_true")
    scan_parser.add_argument("--sarif", action="store_true")
    scan_parser.add_argument("--error", action="store_true", help="Preserve Semgrep --error CI exit-code behavior")
    scan_parser.add_argument("--include", action="append")
    scan_parser.add_argument("--exclude", action="append")
    scan_parser.add_argument("--timeout-seconds", type=int, default=1800)
    scan_parser.add_argument(
        "--trust-state",
        choices=["discovered", "installed", "trusted", "disabled", "blocked", "first_party"],
        default="trusted",
        help="Trust state supplied by the Ouroboros dispatcher for prepared audit events.",
    )
    scan_parser.set_defaults(func=scan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
