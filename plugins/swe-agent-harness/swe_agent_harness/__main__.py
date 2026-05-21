from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .artifacts import (
    build_run_spec,
    collect_bundle,
    discover_artifacts,
    make_run_id,
    resolve_output_dir,
    verify_bundle,
    write_handoff,
)

WRITE_PERMISSIONS = ["filesystem:read", "filesystem:write"]


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return int(payload.get("exit_code", 0))


def collect(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="swe_agent_harness collect-artifacts")
    parser.add_argument("source_output_dir")
    parser.add_argument("--agentos-artifact-dir")
    parser.add_argument("--agentos-run-id")
    parser.add_argument("--status", choices=["blocked", "failed", "completed", "submitted", "partial", "cancelled"])
    ns = parser.parse_args(argv)
    run_id = ns.agentos_run_id or make_run_id("swe-agent-collected")
    bundle_dir = resolve_output_dir(ns.agentos_artifact_dir, run_id)
    source = Path(ns.source_output_dir).expanduser().resolve()
    run_spec = build_run_spec(
        command="collect-artifacts",
        upstream_command=[],
        run_id=run_id,
        artifact_dir=bundle_dir,
        upstream_output_dir=source,
        agentos_flags=vars(ns),
        status=ns.status or "partial",
    )
    run_spec["permissions_exercised"] = WRITE_PERMISSIONS
    result = collect_bundle(source_output_dir=source, bundle_dir=bundle_dir, run_spec=run_spec, status=ns.status)
    return emit({"status": result["status"], "artifact_dir": bundle_dir.as_posix(), "artifacts": result["artifacts"]})


def handoff(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="swe_agent_harness handoff")
    parser.add_argument("artifact_dir")
    ns = parser.parse_args(argv)
    bundle = Path(ns.artifact_dir).expanduser().resolve()
    spec_path = bundle / "run-spec.json"
    if not spec_path.exists():
        return emit({"status": "failed", "error": f"missing {spec_path}", "exit_code": 1})
    run_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = Path(run_spec.get("upstream_output_dir", bundle / "swe-agent-output"))
    hits = discover_artifacts(source) if source.exists() else discover_artifacts(bundle)
    payload = write_handoff(bundle, run_spec=run_spec, hits=hits, status=run_spec.get("status", "partial"))
    return emit({"status": "completed", "handoff_path": (bundle / "handoff.json").as_posix(), "handoff": payload})


def verify(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="swe_agent_harness verify-artifacts")
    parser.add_argument("artifact_dir")
    ns = parser.parse_args(argv)
    payload = verify_bundle(Path(ns.artifact_dir).expanduser().resolve())
    payload["exit_code"] = 0 if payload["status"] == "valid" else 1
    return emit(payload)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: python -m swe_agent_harness {collect-artifacts,handoff,verify-artifacts} ...")
        return 0
    command, rest = argv[0], argv[1:]
    if command == "collect-artifacts":
        return collect(rest)
    if command == "handoff":
        return handoff(rest)
    if command == "verify-artifacts":
        return verify(rest)
    print(f"command not implemented in this PR: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
