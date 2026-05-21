"""Bounded command entrypoint for the OPA policy gate reference plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import PLUGIN_NAME, PLUGIN_VERSION

DEFAULT_ARTIFACT_ROOT = Path(".omx") / "artifacts" / "opa"
SAFE_TIMEOUT_DEFAULT = "30s"
MAX_SUBPROCESS_TIMEOUT_SECONDS = 300.0
VERSION_TIMEOUT_SECONDS = 10.0
SUPPORTED_COMMANDS = {"eval", "test", "check", "build-handoff"}


class UserError(Exception):
    """Expected validation or environment blocker."""


@dataclass(frozen=True)
class Invocation:
    command: str
    repo_root: Path
    config_path: Path
    config: dict[str, Any]
    opa_bin: str
    artifact_root: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_run_id(command: str, config_path: Path, config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, default=str)
    base = f"{utc_now()}|{command}|{config_path}|{payload}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def resolve_repo_root(raw: str | None) -> Path:
    root = Path(raw or os.getcwd()).expanduser().resolve()
    if not root.is_dir():
        raise UserError(f"repo root is not a directory: {root}")
    return root


def ensure_relative_member(root: Path, raw: str, label: str, *, must_exist: bool = True) -> Path:
    if not isinstance(raw, str) or not raw:
        raise UserError(f"{label} must be a non-empty repo-relative path")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise UserError(f"{label} must be repo-relative, not absolute")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UserError(f"{label} must stay inside the repository root") from exc
    if must_exist and not resolved.exists():
        raise UserError(f"{label} does not exist: {raw}")
    return resolved


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def require_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise UserError(f"{label} must be a string or list of strings")


def load_config(repo_root: Path, raw_config: str) -> tuple[Path, dict[str, Any]]:
    path = ensure_relative_member(repo_root, raw_config, "--config")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UserError(f"--config is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UserError("--config JSON must be an object")
    return path, data


def resolve_artifact_root(repo_root: Path, raw: str | None) -> Path:
    root = DEFAULT_ARTIFACT_ROOT if raw is None else Path(raw)
    if root.is_absolute():
        raise UserError("--artifact-root must be repo-relative")
    resolved = (repo_root / root).resolve()
    default_resolved = (repo_root / DEFAULT_ARTIFACT_ROOT).resolve()
    try:
        resolved.relative_to(default_resolved)
    except ValueError as exc:
        raise UserError("--artifact-root must stay under .omx/artifacts/opa") from exc
    return resolved


def find_opa() -> str:
    path = shutil.which("opa")
    if not path:
        raise UserError("opa binary not found; install OPA and ensure it is on PATH")
    if not os.access(path, os.X_OK):
        raise UserError("opa binary is not executable; fix permissions for the opa executable on PATH")
    return path


def opa_subprocess_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("PATH", "HOME", "TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def safe_run(command: list[str], *, timeout_seconds: float, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, env=opa_subprocess_env(), timeout=timeout_seconds, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise UserError(f"opa subprocess timed out after {timeout_seconds:g} seconds") from exc
    except OSError as exc:
        raise UserError(f"opa binary could not execute: {exc}") from exc


def run_opa_version(opa_bin: str) -> tuple[str | None, dict[str, Any] | str]:
    proc = safe_run([opa_bin, "version", "--format", "json"], timeout_seconds=VERSION_TIMEOUT_SECONDS, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout or "{}")
            version = payload.get("Version") or payload.get("version")
            return str(version) if version else None, payload
        except json.JSONDecodeError:
            pass
    proc = safe_run([opa_bin, "version"], timeout_seconds=VERSION_TIMEOUT_SECONDS, capture_output=True, text=True, check=False)
    text = (proc.stdout or proc.stderr).strip()
    version = None
    for line in text.splitlines():
        if line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break
    return version, text


def config_paths(inv: Invocation) -> dict[str, list[Path] | Path | None]:
    cfg = inv.config
    data = [ensure_relative_member(inv.repo_root, item, "data") for item in require_list(cfg.get("data"), "data")]
    bundles = [ensure_relative_member(inv.repo_root, item, "bundle") for item in require_list(cfg.get("bundle") or cfg.get("bundles"), "bundle")]
    schemas = [ensure_relative_member(inv.repo_root, item, "schema") for item in require_list(cfg.get("schema") or cfg.get("schemas"), "schema")]
    capabilities = ensure_relative_member(inv.repo_root, cfg["capabilities"], "capabilities") if cfg.get("capabilities") else None
    input_path = ensure_relative_member(inv.repo_root, cfg["input"], "input") if cfg.get("input") else None
    files = [ensure_relative_member(inv.repo_root, item, "path") for item in require_list(cfg.get("paths") or cfg.get("files"), "paths")]
    return {"data": data, "bundles": bundles, "schemas": schemas, "capabilities": capabilities, "input": input_path, "files": files}


def parse_duration_seconds(value: str) -> float:
    if not re.fullmatch(r"(?:\d+(?:\.\d+)?(?:ms|us|µs|h|m|s))+", value):
        raise UserError("timeout must be a duration using h, m, s, ms, us, or µs units")
    total = 0.0
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|us|µs|h|m|s)", value):
        amount = float(number)
        if unit == "h":
            total += amount * 3600
        elif unit == "m":
            total += amount * 60
        elif unit == "s":
            total += amount
        elif unit == "ms":
            total += amount / 1000
        else:
            total += amount / 1_000_000
    return total


def validate_timeout(value: Any) -> str:
    timeout = SAFE_TIMEOUT_DEFAULT if value is None else value
    if not isinstance(timeout, str) or not timeout:
        raise UserError("timeout must be a string duration such as '10s'")
    seconds = parse_duration_seconds(timeout)
    if seconds <= 0 or seconds > MAX_SUBPROCESS_TIMEOUT_SECONDS:
        raise UserError(f"timeout must be >0 and <= {int(MAX_SUBPROCESS_TIMEOUT_SECONDS)} seconds")
    return timeout


def subprocess_timeout(value: Any) -> float:
    return min(parse_duration_seconds(validate_timeout(value)) + 1.0, MAX_SUBPROCESS_TIMEOUT_SECONDS + 1.0)


def build_opa_command(inv: Invocation, paths: dict[str, Any], run_dir: Path) -> list[str]:
    cfg = inv.config
    cmd = [inv.opa_bin]
    if inv.command == "eval":
        query = cfg.get("query")
        if not isinstance(query, str) or not query.strip():
            raise UserError("eval config requires non-empty query")
        cmd += ["eval", "--format", "json", "--timeout", validate_timeout(cfg.get("timeout"))]
        for item in paths["data"]:
            cmd += ["--data", str(item)]
        for item in paths["bundles"]:
            cmd += ["--bundle", str(item)]
        if paths["input"]:
            cmd += ["--input", str(paths["input"])]
        if cfg.get("fail"):
            cmd.append("--fail")
        if cfg.get("fail_defined") or cfg.get("fail-defined"):
            cmd.append("--fail-defined")
        cmd.append(query)
        return cmd
    if inv.command == "test":
        sources = list(paths["data"] or paths["files"])
        if not sources:
            raise UserError("test config requires data/files paths")
        cmd += ["test", "--format", "json", "--timeout", validate_timeout(cfg.get("timeout"))]
        if cfg.get("fail_fast") or cfg.get("fail-fast"):
            cmd.append("--fail-fast")
        cmd += [str(item) for item in sources]
        return cmd
    if inv.command == "check":
        sources = list(paths["data"] or paths["files"])
        if not sources:
            raise UserError("check config requires data/files paths")
        cmd += ["check", "--format", "json"]
        for item in paths["schemas"]:
            cmd += ["--schema", str(item)]
        if paths["capabilities"]:
            cmd += ["--capabilities", str(paths["capabilities"])]
        cmd += [str(item) for item in sources]
        return cmd
    if inv.command == "build-handoff":
        sources = list(paths["data"] or paths["files"] or paths["bundles"])
        if not sources:
            raise UserError("build-handoff config requires data/files/bundle paths")
        output_name = cfg.get("output_name", "bundle.tar.gz")
        if not isinstance(output_name, str) or Path(output_name).name != output_name or "/" in output_name or ".." in output_name:
            raise UserError("output_name must be a simple filename")
        output_path = run_dir / output_name
        cmd += ["build", "--format", "json", "-o", str(output_path)]
        cmd += [str(item) for item in sources]
        return cmd
    raise UserError(f"unsupported command: {inv.command}")


def parse_json_or_wrap(text: str) -> Any:
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def extract_eval_decision(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return None
    result = raw.get("result")
    if not isinstance(result, list) or not result:
        return None
    expressions = result[0].get("expressions") if isinstance(result[0], dict) else None
    if not isinstance(expressions, list) or not expressions:
        return None
    expr = expressions[0]
    return expr.get("value") if isinstance(expr, dict) else None


def normalize(inv: Invocation, proc: subprocess.CompletedProcess[str], raw_stdout: Any, artifacts: dict[str, str], opa_version: str | None, repro: str) -> dict[str, Any]:
    status = "completed" if proc.returncode == 0 else "failed"
    next_action = "continue" if status == "completed" else "fix_policy"
    decision = None
    reason = None
    if inv.command == "eval":
        decision = extract_eval_decision(raw_stdout)
        if proc.returncode == 0 and decision is None:
            status = "failed"
            reason = "undefined_decision"
            next_action = "review_decision"
        elif proc.returncode == 0 and decision is False:
            next_action = "review_decision"
    elif inv.command == "test" and proc.returncode != 0:
        next_action = "fix_policy_tests"
    elif inv.command == "check" and proc.returncode != 0:
        next_action = "fix_policy_source"
    elif inv.command == "build-handoff" and proc.returncode != 0:
        next_action = "fix_bundle_inputs"
    return {
        "schema_version": "0.1",
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "tool": "opa",
        "tool_version": opa_version,
        "command": inv.command,
        "status": status,
        "normalized_status": "success" if status == "completed" else "failed",
        "reason": reason,
        "exit_code": proc.returncode,
        "query": inv.config.get("query"),
        "decision": decision,
        "artifacts": artifacts,
        "repro_command": repro,
        "human_summary": human_summary(inv.command, status, decision, reason),
        "next_action": next_action,
    }


def human_summary(command: str, status: str, decision: Any, reason: str | None) -> str:
    if reason == "undefined_decision":
        return "OPA eval completed without a defined decision for the configured query."
    if command == "eval" and status == "completed":
        return f"OPA eval completed with decision {decision!r}."
    if status == "completed":
        return f"OPA {command} completed successfully."
    return f"OPA {command} failed; inspect raw stderr/stdout artifacts."


def write_handoff(run_dir: Path, normalized: dict[str, Any]) -> None:
    lines = [
        f"# OPA policy gate handoff: {normalized['command']}",
        "",
        f"- status: `{normalized['status']}`",
        f"- OPA version: `{normalized.get('tool_version')}`",
        f"- query: `{normalized.get('query')}`",
        f"- decision: `{normalized.get('decision')}`",
        f"- next action: `{normalized.get('next_action')}`",
        "",
        "## Evidence",
    ]
    for name, path in normalized["artifacts"].items():
        lines.append(f"- {name}: `{path}`")
    lines += ["", "## Reproduce", "", "```bash", normalized["repro_command"], "```", ""]
    (run_dir / "handoff.md").write_text("\n".join(lines), encoding="utf-8")


def write_repro(run_dir: Path, command: list[str]) -> str:
    repro = " ".join(shlex.quote(part) for part in command)
    path = run_dir / "repro.sh"
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + repro + "\n", encoding="utf-8")
    path.chmod(0o755)
    return repro


def artifact_paths(repo_root: Path, run_dir: Path) -> dict[str, str]:
    names = ["raw-stdout.json", "raw-stderr.txt", "normalized-result.json", "provenance.json", "handoff.md", "repro.sh"]
    existing = {name: rel(repo_root, run_dir / name) for name in names}
    for candidate in run_dir.iterdir() if run_dir.exists() else []:
        if candidate.name.endswith(".tar.gz"):
            existing[candidate.name] = rel(repo_root, candidate)
    return existing


def collect_hashes(root: Path, paths: dict[str, Any]) -> dict[str, Any]:
    hashed: dict[str, Any] = {}
    for label in ("data", "bundles", "schemas", "files"):
        hashed[label] = [{"path": rel(root, item), "sha256": sha256_file(item)} for item in paths[label]]
    if paths["input"]:
        hashed["input"] = {"path": rel(root, paths["input"]), "sha256": sha256_file(paths["input"])}
    if paths["capabilities"]:
        hashed["capabilities"] = {"path": rel(root, paths["capabilities"]), "sha256": sha256_file(paths["capabilities"])}
    return hashed


def execute(inv: Invocation) -> dict[str, Any]:
    run_id = stable_run_id(inv.command, inv.config_path, inv.config)
    run_dir = inv.artifact_root / inv.command / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = config_paths(inv)
    opa_version, version_payload = run_opa_version(inv.opa_bin)
    opa_cmd = build_opa_command(inv, paths, run_dir)
    repro = write_repro(run_dir, opa_cmd)
    proc = safe_run(opa_cmd, timeout_seconds=subprocess_timeout(inv.config.get("timeout")), cwd=inv.repo_root, capture_output=True, text=True, check=False)
    raw_stdout = parse_json_or_wrap(proc.stdout)
    artifacts = artifact_paths(inv.repo_root, run_dir)
    provenance = {
        "generated_at": utc_now(),
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "opa": {"version": opa_version, "version_payload": version_payload, "command": inv.command},
        "config_path": rel(inv.repo_root, inv.config_path),
        "repo_root": str(inv.repo_root),
        "permissions_used": ["filesystem:read", "filesystem:write", "shell:execute"],
        "path_hashes": collect_hashes(inv.repo_root, paths),
        "repro_command": repro,
        "redaction": ["no environment dump", "path metadata and SHA-256 hashes only"],
    }
    (run_dir / "raw-stdout.json").write_text(json_dump(raw_stdout), encoding="utf-8")
    (run_dir / "raw-stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (run_dir / "provenance.json").write_text(json_dump(provenance), encoding="utf-8")
    normalized = normalize(inv, proc, raw_stdout, artifact_paths(inv.repo_root, run_dir), opa_version, repro)
    (run_dir / "normalized-result.json").write_text(json_dump(normalized), encoding="utf-8")
    write_handoff(run_dir, normalized)
    # Refresh artifact list after handoff/normalized files and optional bundle exist.
    normalized["artifacts"] = artifact_paths(inv.repo_root, run_dir)
    (run_dir / "normalized-result.json").write_text(json_dump(normalized), encoding="utf-8")
    return normalized


def blocked_result(command: str, reason: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plugin": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "tool": "opa",
        "command": command,
        "status": "blocked",
        "normalized_status": "blocked",
        "reason": reason,
        "message": message,
        "next_action": "install_opa" if "opa binary" in message else "fix_request",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opa_policy_gate")
    parser.add_argument("command", help="OPA policy gate command: eval, test, check, or build-handoff.")
    parser.add_argument("--config", required=True, help="Repo-relative JSON config file.")
    parser.add_argument("--repo-root", help="Repository root for path bounding; defaults to cwd.")
    parser.add_argument("--artifact-root", help="Repo-relative artifact root under .omx/artifacts/opa; defaults to .omx/artifacts/opa.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command not in SUPPORTED_COMMANDS:
            raise UserError(f"unsupported command: {args.command}")
        repo_root = resolve_repo_root(args.repo_root)
        config_path, config = load_config(repo_root, args.config)
        inv = Invocation(
            command=args.command,
            repo_root=repo_root,
            config_path=config_path,
            config=config,
            opa_bin=find_opa(),
            artifact_root=resolve_artifact_root(repo_root, args.artifact_root),
        )
        result = execute(inv)
    except UserError as exc:
        reason = "opa_binary_missing" if "opa binary" in str(exc) else "invalid_request"
        result = blocked_result(getattr(args, "command", "unknown"), reason, str(exc))
        print(json_dump(result), end="")
        return 0
    print(json_dump(result), end="")
    return 0 if result["status"] in {"completed", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
