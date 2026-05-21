"""Command entrypoint for the Langfuse observability Ouroboros plugin."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import PLUGIN_NAME, PLUGIN_VERSION
from .artifacts import (
    DEFAULT_OUTPUT_DIR,
    artifact_paths,
    build_handoff,
    coerce_score_value,
    parse_trace_reference,
    redact,
    render_markdown,
    timestamp_slug,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from .client import LangfuseClient, LangfuseConfig


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def command_inspect(args: argparse.Namespace) -> int:
    env_host = args.host or os.environ.get("LANGFUSE_BASE_URL")
    trace_id, host_from_ref, trace_url = parse_trace_reference(args.trace_url_or_id, env_host)
    host = (args.host or host_from_ref or env_host or "").rstrip("/") or None
    if args.offline_fixture:
        trace_payload = load_json(Path(args.offline_fixture))
        if not host:
            host = trace_payload.get("host") if isinstance(trace_payload.get("host"), str) else None
        trace_url = trace_url or (f"{host}/project/-/traces/{trace_id}" if host else None)
    else:
        config = LangfuseConfig.from_env(host)
        client = LangfuseClient(config)
        host = config.host
        trace_url = trace_url or f"{host}/project/-/traces/{trace_id}"
        trace_payload = client.get_trace(trace_id)

    handoff = build_handoff(trace_payload, trace_id=trace_id, host=host, trace_url=trace_url)
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    json_path, md_path = artifact_paths(output_dir, handoff["trace"]["id"])
    write_json_atomic(json_path, handoff)
    write_text_atomic(md_path, render_markdown(handoff))
    result = {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "command": "inspect",
        "status": "completed",
        "trace_id": handoff["trace"]["id"],
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "summary": handoff["summary"],
    }
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def trace_context(artifact: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    trace = artifact.get("trace") if isinstance(artifact.get("trace"), dict) else {}
    trace_id = trace.get("id") or artifact.get("traceId") or artifact.get("trace_id")
    observation_id = artifact.get("observationId") or artifact.get("observation_id")
    provenance = artifact.get("provenance") if isinstance(artifact.get("provenance"), dict) else {}
    host = provenance.get("langfuse_host") if isinstance(provenance.get("langfuse_host"), str) else None
    return str(trace_id) if trace_id else None, str(observation_id) if observation_id else None, host


def build_score_payload(args: argparse.Namespace, artifact: dict[str, Any]) -> dict[str, Any]:
    trace_id, observation_id, _ = trace_context(artifact)
    trace_id = args.trace_id or trace_id
    observation_id = args.observation_id or observation_id
    if not trace_id:
        raise ValueError("trace id missing; provide --trace-id or an artifact with trace.id")
    payload: dict[str, Any] = {
        "traceId": trace_id,
        "name": args.name,
        "value": coerce_score_value(args.value),
        "comment": args.comment or "Published from Ouroboros Langfuse observability plugin.",
    }
    if observation_id:
        payload["observationId"] = observation_id
    return payload


def write_score_result(args: argparse.Namespace, *, payload: dict[str, Any], response: dict[str, Any] | None, status: str, error: str | None = None) -> Path:
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    path = output_dir / f"score-{timestamp_slug()}.json"
    result = {
        "schema_version": "0.1",
        "source": "langfuse",
        "status": status,
        "score": redact(payload),
        "response": redact(response or {}),
        "error": error,
        "provenance": {"recorded_at": now, "plugin": f"{PLUGIN_NAME}@{PLUGIN_VERSION}"},
        "audit": [
            {"event": "plugin.invoked", "at": now, "command": "score"},
            {"event": "plugin.permission_used", "at": now, "scope": "filesystem:read"},
            {
                "event": "plugin.permission_used",
                "at": now,
                "scope": "network:write" if status == "completed" else "filesystem:write",
            },
            {
                "event": "plugin.completed" if status in {"completed", "dry_run"} else "plugin.failed",
                "at": now,
                "command": "score",
            },
        ],
    }
    write_json_atomic(path, result)
    return path


def command_score(args: argparse.Namespace) -> int:
    artifact = load_json(Path(args.artifact_path))
    payload = build_score_payload(args, artifact)
    if args.dry_run:
        result_path = write_score_result(args, payload=payload, response=None, status="dry_run")
        sys.stdout.write(
            json.dumps(
                {"status": "dry_run", "payload": redact(payload), "result_path": str(result_path)},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 0
    if not args.confirm:
        raise ValueError("real Langfuse score publication requires --confirm; use --dry-run to inspect the payload")
    _, _, artifact_host = trace_context(artifact)
    config = LangfuseConfig.from_env(args.host or artifact_host)
    try:
        response = LangfuseClient(config).create_score(payload)
    except Exception as exc:
        result_path = write_score_result(args, payload=payload, response=None, status="failed", error=str(exc))
        sys.stderr.write(f"score publication failed; structured artifact: {result_path}\n")
        raise
    result_path = write_score_result(args, payload=payload, response=response, status="completed")
    sys.stdout.write(
        json.dumps(
            {"status": "completed", "response": redact(response), "result_path": str(result_path)},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="langfuse-observability")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect", help="Fetch a Langfuse trace into Ouroboros artifacts.")
    inspect_parser.add_argument("trace_url_or_id")
    inspect_parser.add_argument("--host", help="Langfuse base URL. Defaults to LANGFUSE_BASE_URL or URL origin.")
    inspect_parser.add_argument("--offline-fixture", help="Read trace-like JSON from a local fixture instead of Langfuse.")
    inspect_parser.add_argument("--output-dir", help="Artifact directory. Defaults to .omx/handoffs/langfuse.")
    inspect_parser.set_defaults(func=command_inspect)

    score_parser = sub.add_parser("score", help="Publish or dry-run a Langfuse score from an Ouroboros artifact.")
    score_parser.add_argument("artifact_path")
    score_parser.add_argument("--name", required=True)
    score_parser.add_argument("--value", required=True)
    score_parser.add_argument("--trace-id")
    score_parser.add_argument("--observation-id")
    score_parser.add_argument("--comment")
    score_parser.add_argument("--host", help="Langfuse base URL. Defaults to artifact provenance or LANGFUSE_BASE_URL.")
    score_parser.add_argument("--dry-run", action="store_true", help="Write local provenance without network write.")
    score_parser.add_argument("--confirm", action="store_true", help="Required for real network write.")
    score_parser.add_argument("--output-dir", help="Artifact directory. Defaults to .omx/handoffs/langfuse.")
    score_parser.set_defaults(func=command_score)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
