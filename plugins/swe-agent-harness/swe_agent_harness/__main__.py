from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifacts import (
    build_run_spec,
    collect_bundle,
    discover_artifacts,
    ensure_dir,
    make_run_id,
    resolve_output_dir,
    verify_bundle,
    write_audit,
    write_handoff,
    write_json,
)

EXECUTE_PERMISSIONS = ["filesystem:read", "filesystem:write", "shell:execute", "runtime:execute"]
WRITE_PERMISSIONS = ["filesystem:read", "filesystem:write"]
NETWORK_HINTS = ("github_url", "http://", "https://")
OPEN_PR_HINTS = ("openpr", "openprhook", "pullrequest", "pushgh", "github:pullrequest")
APPLY_PATCH_HINTS = ("applypatch", "applytorepo", "saveapplypatchhook")


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return int(payload.get("exit_code", 0))


def has_option(args: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(name + "=") for arg in args)


def option_value(args: list[str], name: str) -> str | None:
    prefix = name + "="
    for index, arg in enumerate(args):
        if arg.startswith(prefix):
            return arg[len(prefix) :]
        if arg == name and index + 1 < len(args):
            return args[index + 1]
    return None


def normalized_policy_text(args: list[str]) -> str:
    return " ".join(args).lower().replace("-", "").replace("_", "").replace(".", "")


def sensitive_argv_values(args: list[str]) -> list[str]:
    values: list[str] = []
    capture_next = False
    for item in args:
        if capture_next:
            if item:
                values.append(item)
            capture_next = False
            continue
        if item.startswith("--"):
            flag, sep, value = item.partition("=")
            normalized_flag = flag.lower().replace("-", "").replace("_", "").replace(".", "")
            if any(part in normalized_flag for part in ("key", "token", "secret", "password", "credential")):
                if sep:
                    values.append(value)
                else:
                    capture_next = True
    return [value for value in values if value]


def redact_text(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "<redacted>")
    return text


def required_permissions(upstream_args: list[str], execute: bool) -> list[str]:
    perms = list(EXECUTE_PERMISSIONS if execute else WRITE_PERMISSIONS)
    joined = " ".join(upstream_args)
    if any(hint in joined for hint in NETWORK_HINTS):
        perms.extend(["network:read", "network:write", "github:read"])
    return list(dict.fromkeys(perms))


def blocked(bundle_dir: Path, *, run_spec: dict[str, Any], reason: str, permissions: list[str]) -> int:
    ensure_dir(bundle_dir)
    run_spec = dict(run_spec)
    run_spec["status"] = "blocked"
    run_spec["permissions_exercised"] = []
    run_spec["required_permissions"] = permissions
    run_spec["blocked_reason"] = reason
    write_json(bundle_dir / "run-spec.json", run_spec)
    (bundle_dir / "upstream-command.txt").write_text(" ".join(run_spec.get("upstream_command", [])) + "\n", encoding="utf-8")
    (bundle_dir / "stdout.log").write_text("", encoding="utf-8")
    (bundle_dir / "stderr.log").write_text(reason + "\n", encoding="utf-8")
    write_audit(bundle_dir, status="blocked", permissions=[], command=run_spec.get("upstream_command", []), message=reason)
    write_handoff(bundle_dir, run_spec=run_spec, hits=[], status="blocked")
    write_json(bundle_dir / "provenance.json", {"schema_version": "agentos.swe-agent.provenance.v0.1", "status": "blocked", "reason": reason})
    return emit({"status": "blocked", "reason": reason, "artifact_dir": bundle_dir.as_posix(), "exit_code": 1})


def add_common_agentos_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agentos-artifact-dir")
    parser.add_argument("--agentos-run-id")
    parser.add_argument("--agentos-sweagent-bin", default=os.environ.get("SWE_AGENT_BIN", "sweagent"))
    parser.add_argument("--agentos-allow-execute", action="store_true", help="Acknowledge shell/runtime authority for run commands.")
    parser.add_argument("--agentos-allow-open-pr", action="store_true", help="Allow upstream args that may open a GitHub PR.")
    parser.add_argument("--agentos-allow-host-patch", action="store_true", help="Allow upstream args that may apply a patch to a host repo.")
    parser.add_argument("--agentos-no-open-pr", action="store_true", default=True)
    parser.add_argument("--agentos-dry-run", action="store_true", help="Create AgentOS metadata without invoking sweagent.")


def run_like(command: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"swe_agent_harness {command}", allow_abbrev=False)
    add_common_agentos_flags(parser)
    ns, upstream_args = parser.parse_known_args(argv)
    run_id = ns.agentos_run_id or make_run_id(f"swe-agent-{command}")
    bundle_dir = resolve_output_dir(ns.agentos_artifact_dir, run_id)
    upstream_output_arg = option_value(upstream_args, "--output_dir")
    upstream_output = (
        Path(upstream_output_arg).expanduser().resolve()
        if upstream_output_arg
        else bundle_dir / "swe-agent-output"
    )
    upstream_command = [ns.agentos_sweagent_bin, command, *upstream_args]
    if command in {"run", "run-replay"} and not has_option(upstream_args, "--output_dir"):
        upstream_command.extend(["--output_dir", upstream_output.as_posix()])
    permissions = required_permissions(upstream_args, execute=True)
    run_spec = build_run_spec(
        command=command,
        upstream_command=upstream_command,
        run_id=run_id,
        artifact_dir=bundle_dir,
        upstream_output_dir=upstream_output,
        agentos_flags={k: v for k, v in vars(ns).items() if k.startswith("agentos")},
    )
    policy_text = normalized_policy_text(upstream_args)
    if any(hint in policy_text for hint in OPEN_PR_HINTS):
        return blocked(bundle_dir, run_spec=run_spec, reason="upstream args appear to request PR/GitHub mutation; this MVP defers PR creation to a dedicated destructive command", permissions=permissions)
    if any(hint in policy_text for hint in APPLY_PATCH_HINTS):
        return blocked(bundle_dir, run_spec=run_spec, reason="upstream args appear to request host patch application; this MVP defers host patch application to a dedicated trusted command", permissions=permissions)
    if not ns.agentos_allow_execute and not ns.agentos_dry_run:
        return blocked(bundle_dir, run_spec=run_spec, reason="missing shell/runtime trust; rerun with --agentos-allow-execute after plugin trust grants shell:execute/runtime:execute", permissions=permissions)
    ensure_dir(bundle_dir)
    ensure_dir(upstream_output)
    run_spec["permissions_exercised"] = [] if ns.agentos_dry_run else permissions
    if ns.agentos_dry_run:
        (bundle_dir / "stdout.log").write_text("dry-run: sweagent not invoked\n", encoding="utf-8")
        (bundle_dir / "stderr.log").write_text("", encoding="utf-8")
        result = collect_bundle(source_output_dir=upstream_output, bundle_dir=bundle_dir, run_spec=run_spec, status="partial")
        return emit({"status": result["status"], "dry_run": True, "artifact_dir": bundle_dir.as_posix()})
    if shutil.which(ns.agentos_sweagent_bin) is None and not Path(ns.agentos_sweagent_bin).exists():
        return blocked(bundle_dir, run_spec=run_spec, reason=f"sweagent executable not found: {ns.agentos_sweagent_bin}", permissions=permissions)
    proc = subprocess.run(upstream_command, cwd=Path.cwd(), capture_output=True, text=True, check=False)
    secrets = sensitive_argv_values(upstream_args)
    (bundle_dir / "stdout.log").write_text(redact_text(proc.stdout, secrets), encoding="utf-8")
    (bundle_dir / "stderr.log").write_text(redact_text(proc.stderr, secrets), encoding="utf-8")
    result = collect_bundle(source_output_dir=upstream_output, bundle_dir=bundle_dir, run_spec=run_spec, returncode=proc.returncode)
    payload = {"status": result["status"], "returncode": proc.returncode, "artifact_dir": bundle_dir.as_posix(), "exit_code": 0 if proc.returncode == 0 else 1}
    return emit(payload)


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
    run_spec = build_run_spec(command="collect-artifacts", upstream_command=[], run_id=run_id, artifact_dir=bundle_dir, upstream_output_dir=source, agentos_flags=vars(ns), status=ns.status or "partial")
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
        print("usage: python -m swe_agent_harness {run,run-replay,collect-artifacts,handoff,verify-artifacts} ...")
        return 0
    command, rest = argv[0], argv[1:]
    if command in {"run", "run-replay"}:
        return run_like(command, rest)
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
