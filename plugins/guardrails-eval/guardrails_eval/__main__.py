"""Command entrypoint for the Guardrails Ouroboros plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

PLUGIN_NAME = "guardrails-eval"
PLUGIN_VERSION = __version__
TOOL_NAME = "guardrails-ai"
TOOL_PACKAGE = "guardrails-ai"
TOOL_REPOSITORY = "https://github.com/guardrails-ai/guardrails"
SUPPORTED_SPEC_SUFFIXES = {".rail", ".json"}
DEFAULT_AUDIT_EVENTS = [
    "plugin.invoked",
    "plugin.permission_used",
    "plugin.completed",
    "plugin.failed",
]


class UserError(Exception):
    """A recoverable command error that should be shown without a traceback."""

    exit_code = 2


class ValidationRuntimeError(UserError):
    exit_code = 1


@dataclass(frozen=True)
class BoundedPath:
    path: Path
    display: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_path(root: Path, raw_path: str, label: str, *, must_exist: bool = True) -> BoundedPath:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise UserError(f"{label} must be a path relative to the repository root")
    resolved = (root / candidate).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise UserError(f"{label} must stay inside the repository root") from exc
    if must_exist and not resolved.is_file():
        raise UserError(f"{label} not found: {rel}")
    return BoundedPath(path=resolved, display=str(rel))


def ensure_parent_for_write(path: BoundedPath) -> None:
    path.path.parent.mkdir(parents=True, exist_ok=True)


def load_json_file(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise UserError(f"{label} must be valid JSON: {exc.msg}") from exc


def load_metadata(path: BoundedPath | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = load_json_file(path.path, "--metadata")
    if not isinstance(payload, dict):
        raise UserError("--metadata must contain a JSON object")
    return payload


def write_json_atomic(path: BoundedPath, payload: dict[str, Any]) -> None:
    ensure_parent_for_write(path)
    tmp = path.path.with_name(f".{path.path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path.path)


def import_guardrails_guard():
    try:
        from guardrails import Guard  # type: ignore
    except ImportError as exc:
        raise ValidationRuntimeError(
            "guardrails-ai is required for validation. Install it in the plugin "
            "environment, for example: pip install guardrails-ai"
        ) from exc
    return Guard


def load_guard(spec: BoundedPath):
    suffix = spec.path.suffix.lower()
    if suffix not in SUPPORTED_SPEC_SUFFIXES:
        raise UserError(
            f"unsupported --spec type {suffix or '(none)'}; MVP supports .rail and .json specs only"
        )

    Guard = import_guardrails_guard()
    if suffix == ".rail":
        if not hasattr(Guard, "for_rail"):
            raise ValidationRuntimeError("installed guardrails-ai does not expose Guard.for_rail")
        return Guard.for_rail(str(spec.path))

    guard_dict = load_json_file(spec.path, "--spec")
    if not isinstance(guard_dict, dict):
        raise UserError("JSON --spec must contain a guard object")
    if hasattr(Guard, "from_dict"):
        return Guard.from_dict(guard_dict)
    raise ValidationRuntimeError("installed guardrails-ai does not expose Guard.from_dict")


def outcome_value(outcome: Any, name: str, default: Any = None) -> Any:
    if isinstance(outcome, dict):
        return outcome.get(name, default)
    return getattr(outcome, name, default)


def jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, "model_dump"):
            return jsonable(value.model_dump())
        if hasattr(value, "dict"):
            return jsonable(value.dict())
        return repr(value)


def normalize_outcome(outcome: Any, target_text: str) -> dict[str, Any]:
    validation_passed = bool(outcome_value(outcome, "validation_passed", False))
    return {
        "validation_passed": validation_passed,
        "validated_output": jsonable(outcome_value(outcome, "validated_output")),
        "raw_llm_output": {
            "redacted": True,
            "sha256": sha256_text(str(outcome_value(outcome, "raw_llm_output", target_text))),
            "length": len(str(outcome_value(outcome, "raw_llm_output", target_text))),
        },
        "validation_summaries": jsonable(outcome_value(outcome, "validation_summaries", [])),
        "reask": jsonable(outcome_value(outcome, "reask")),
        "error": jsonable(outcome_value(outcome, "error")),
    }


def run_guard_validation(spec: BoundedPath, target_text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    guard = load_guard(spec)
    try:
        if hasattr(guard, "parse"):
            outcome = guard.parse(llm_output=target_text, metadata=metadata, num_reasks=0)
        elif hasattr(guard, "validate"):
            outcome = guard.validate(target_text, metadata=metadata)
        else:
            raise ValidationRuntimeError("loaded Guardrails guard has neither parse nor validate")
    except Exception as exc:  # Guardrails validators may raise on configured failures.
        if isinstance(exc, ValidationRuntimeError):
            raise
        return {
            "validation_passed": False,
            "validated_output": None,
            "raw_llm_output": {"redacted": True, "sha256": sha256_text(target_text), "length": len(target_text)},
            "validation_summaries": [],
            "reask": None,
            "error": str(exc),
        }
    return normalize_outcome(outcome, target_text)


def target_reference(
    *,
    target_path: BoundedPath | None,
    inline_text: str | None,
    target_kind: str,
) -> tuple[str, dict[str, Any]]:
    if target_path is not None:
        text = target_path.path.read_text(encoding="utf-8", errors="replace")
        ref = {
            "kind": target_kind,
            "path": target_path.display,
            "sha256": sha256_file(target_path.path),
            "length": len(text),
        }
        return text, ref
    assert inline_text is not None
    return inline_text, {
        "kind": "inline_text",
        "path": None,
        "sha256": sha256_text(inline_text),
        "length": len(inline_text),
    }


def build_report(
    *,
    command_name: str,
    spec: BoundedPath,
    target_ref: dict[str, Any],
    metadata_path: BoundedPath | None,
    report_path: BoundedPath | None,
    handoff_path: BoundedPath | None,
    outcome: dict[str, Any],
) -> dict[str, Any]:
    passed = bool(outcome.get("validation_passed"))
    status = "success" if passed else "failed"
    permissions_used = ["filesystem:read"]
    if report_path or handoff_path:
        permissions_used.append("filesystem:write")
    capabilities_used = ["ledger:write", "provenance:write", "state:write"]
    if handoff_path:
        capabilities_used.append("handoff:attach")

    return {
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": {
            "name": TOOL_NAME,
            "source_repository": TOOL_REPOSITORY,
            "package": TOOL_PACKAGE,
        },
        "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION},
        "command": {"namespace": "guardrails", "name": command_name},
        "input": {
            "spec_path": spec.display,
            "spec_sha256": sha256_file(spec.path),
            "target": target_ref,
            "metadata_path": metadata_path.display if metadata_path else None,
            "metadata_sha256": sha256_file(metadata_path.path) if metadata_path else None,
        },
        "guardrails_outcome": outcome,
        "ouroboros_result": {
            "status": status,
            "risk": "write",
            "permissions_used": permissions_used,
            "capabilities_used": capabilities_used,
            "audit_events": DEFAULT_AUDIT_EVENTS,
        },
        "provenance": {
            "bounded_inputs": [
                {"path": spec.display, "role": "guardrails_spec", "sha256": sha256_file(spec.path)},
                {"path": target_ref.get("path"), "role": target_ref["kind"], "sha256": target_ref["sha256"]},
            ],
            "redaction": "Raw target text is represented by path/hash/length references; raw LLM output is redacted in reports by default.",
        },
        "ledger_event": {
            "event_type": "plugin.completed" if passed else "plugin.failed",
            "plugin": PLUGIN_NAME,
            "command": command_name,
            "status": status,
            "evidence": "Guardrails validation passed" if passed else "Guardrails validation failed",
        },
        "state_update": {
            "validation_status": status,
            "report_path": report_path.display if report_path else None,
            "handoff_path": handoff_path.display if handoff_path else None,
        },
        "handoff": {
            "consumer_hint": "Use this report as validation evidence for the associated artifact.",
            "artifact_status": "accepted" if passed else "rejected",
            "report_path": report_path.display if report_path else None,
        },
    }


def build_handoff(report: dict[str, Any], handoff_path: BoundedPath) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plugin": report["plugin"],
        "tool": report["tool"],
        "created_at": report["generated_at"],
        "status": report["ouroboros_result"]["status"],
        "artifact_status": report["handoff"]["artifact_status"],
        "report_path": report["state_update"]["report_path"],
        "handoff_path": handoff_path.display,
        "consumer_hint": report["handoff"]["consumer_hint"],
        "evidence": {
            "validation_passed": report["guardrails_outcome"]["validation_passed"],
            "error": report["guardrails_outcome"].get("error"),
            "target": report["input"]["target"],
            "spec_path": report["input"]["spec_path"],
        },
    }


def summary_for_report(report: dict[str, Any]) -> str:
    outcome = report.get("guardrails_outcome", {})
    result = report.get("ouroboros_result", {})
    target = report.get("input", {}).get("target", {})
    status = result.get("status", "unknown")
    passed = outcome.get("validation_passed")
    error = outcome.get("error")
    target_label = target.get("path") or target.get("kind", "target")
    line = f"guardrails {status}: validation_passed={passed} target={target_label}"
    if error:
        line += f" error={error}"
    return line


def validate_command(args: argparse.Namespace, *, command_name: str) -> int:
    root = Path.cwd().resolve()
    spec = bounded_path(root, args.spec, "--spec")
    metadata_path = bounded_path(root, args.metadata, "--metadata") if args.metadata else None
    report_path = bounded_path(root, args.report, "--report", must_exist=False) if args.report else None
    handoff_path = bounded_path(root, args.handoff, "--handoff", must_exist=False) if args.handoff else None

    output_path = None
    inline_text = None
    target_kind = "llm_output"
    if command_name == "validate-artifact":
        output_path = bounded_path(root, args.artifact, "--artifact")
        target_kind = "artifact"
    else:
        if bool(args.output) == bool(args.text is not None):
            raise UserError("validate-output requires exactly one of --output or --text")
        if args.output:
            output_path = bounded_path(root, args.output, "--output")
        else:
            inline_text = args.text

    target_text, target_ref = target_reference(
        target_path=output_path,
        inline_text=inline_text,
        target_kind=target_kind,
    )
    metadata = load_metadata(metadata_path)
    outcome = run_guard_validation(spec, target_text, metadata)
    report = build_report(
        command_name=command_name,
        spec=spec,
        target_ref=target_ref,
        metadata_path=metadata_path,
        report_path=report_path,
        handoff_path=handoff_path,
        outcome=outcome,
    )

    if report_path:
        write_json_atomic(report_path, report)
    if handoff_path:
        write_json_atomic(handoff_path, build_handoff(report, handoff_path))

    sys.stdout.write(summary_for_report(report) + "\n")
    if not report_path:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")

    if outcome.get("validation_passed"):
        return 0
    return 0 if args.no_fail_on_validation_fail else 1


def summarize_command(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    report_path = bounded_path(root, args.report, "--report")
    report = load_json_file(report_path.path, "--report")
    if not isinstance(report, dict):
        raise UserError("--report must contain a JSON object")
    sys.stdout.write(summary_for_report(report) + "\n")
    return 0


def add_common_validation_args(parser: argparse.ArgumentParser, *, target: str) -> None:
    parser.add_argument("--spec", required=True)
    if target == "output":
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--output")
        group.add_argument("--text")
    else:
        parser.add_argument("--artifact", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--report")
    parser.add_argument("--handoff")
    parser.add_argument("--no-fail-on-validation-fail", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardrails")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_output = sub.add_parser("validate-output")
    add_common_validation_args(validate_output, target="output")

    validate_artifact = sub.add_parser("validate-artifact")
    add_common_validation_args(validate_artifact, target="artifact")

    summarize = sub.add_parser("summarize-report")
    summarize.add_argument("--report", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-output":
            return validate_command(args, command_name="validate-output")
        if args.command == "validate-artifact":
            return validate_command(args, command_name="validate-artifact")
        if args.command == "summarize-report":
            return summarize_command(args)
        parser.error(f"unknown command: {args.command}")
    except UserError as exc:
        sys.stderr.write(f"guardrails-eval: {exc}\n")
        return getattr(exc, "exit_code", 2)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
