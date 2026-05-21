"""Contract-aware adapter for the upstream Graphify CLI.

The adapter intentionally stays thin: it resolves and launches upstream
`graphify`, then adds AgentOS/Ouroboros permission classification, bounded
blocking for sensitive modes, artifact discovery, provenance, and handoff JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PLUGIN_NAME = "graphify"
PLUGIN_VERSION = "0.1.0"
PYPI_PACKAGE = "graphifyy"
HANDOFF_DIR = Path(".omx") / "handoffs" / "graphify"
STANDARD_ARTIFACTS = (
    "graphify-out/GRAPH_REPORT.md",
    "graphify-out/graph.json",
    "graphify-out/graph.html",
    "graphify-out/graph.svg",
    "graphify-out/graph.graphml",
    "graphify-out/graph.cypher",
)


@dataclass(frozen=True)
class Resolution:
    argv: list[str] | None
    label: str | None
    version: str | None
    blocked_reason: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "git", "ssh"} and bool(parsed.netloc)


def graphify_version() -> str | None:
    for package in (PYPI_PACKAGE, "graphify"):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return None


def resolve_graphify() -> Resolution:
    executable = shutil.which("graphify")
    version = graphify_version()
    if executable:
        return Resolution([executable], executable, version)

    try:
        probe = subprocess.run(
            [sys.executable, "-m", "graphify", "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        probe = None
    if probe is not None and probe.returncode == 0:
        return Resolution([sys.executable, "-m", "graphify"], "python -m graphify", version)

    return Resolution(
        None,
        None,
        version,
        "Graphify is not installed. Install it explicitly with `uv tool install graphifyy` or `pipx install graphifyy`; this adapter never auto-installs dependencies.",
    )


def command_family(args: list[str]) -> str:
    if args and args[0] in {"query", "path", "explain", "add"}:
        return args[0]
    if "--neo4j-push" in args:
        return "neo4j-push"
    if "--mcp" in args:
        return "mcp"
    if "--watch" in args or (args and args[0] == "watch"):
        return "watch"
    return "build"


def classify_permissions(args: list[str]) -> dict[str, Any]:
    family = command_family(args)
    permissions = ["shell:execute"]
    sensitive: list[str] = []
    risk = "write"
    requires_confirmation = False

    if family in {"query", "path", "explain"}:
        risk = "read_only"
        permissions.append("filesystem:read")
    else:
        permissions.extend(["filesystem:read", "filesystem:write"])

    url_targets = [a for a in args if is_url(a)]
    if family == "add" or url_targets:
        permissions.append("network:read")
        sensitive.append("network:read")
        requires_confirmation = True

    if "--mcp" in args or family == "mcp":
        permissions.append("mcp:execute")
        sensitive.append("mcp:execute")
        requires_confirmation = True

    if "--watch" in args or family == "watch":
        sensitive.append("long_running:watch")
        requires_confirmation = True

    if "--neo4j-push" in args:
        permissions.extend(["network:write", "database:write"])
        sensitive.extend(["network:write", "database:write"])
        requires_confirmation = True

    model_flags = {"--openai", "--gemini", "--bedrock", "--ollama", "--whisper-model"}
    if any(flag in args for flag in model_flags):
        permissions.append("network:write")
        sensitive.append("model_or_backend:write")
        requires_confirmation = True

    return {
        "family": family,
        "risk": risk,
        "permissions_used": sorted(set(permissions)),
        "sensitive_operations": sorted(set(sensitive)),
        "requires_confirmation": requires_confirmation,
    }


def discover_artifacts(root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    candidates = [root / p for p in STANDARD_ARTIFACTS]
    for extra_dir in (root / "graphify-out", root / "wiki"):
        if extra_dir.exists():
            for child in extra_dir.rglob("*"):
                if child.is_file():
                    candidates.append(child)
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        artifacts.append({"path": str(rel), "bytes": path.stat().st_size})
    return artifacts


def graph_stats(root: Path) -> dict[str, int] | None:
    graph_path = root / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        return None
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    def count_any(*keys: str) -> int:
        for key in keys:
            value = graph.get(key) if isinstance(graph, dict) else None
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):
                return len(value)
        return 0

    return {
        "nodes": count_any("nodes", "vertices"),
        "edges": count_any("edges", "links"),
        "communities": count_any("communities", "clusters"),
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def handoff_path(root: Path, family: str, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else root / p
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / HANDOFF_DIR / f"{stamp}-{family}.json"


def target_evidence(args: list[str], root: Path) -> dict[str, Any]:
    family = command_family(args)
    graph_path: str | None = None
    if "--graph" in args:
        idx = args.index("--graph")
        if idx + 1 < len(args):
            graph_path = args[idx + 1]

    target = "."
    if family == "build":
        for arg in args:
            if not arg.startswith("-"):
                target = arg
                break
    elif family == "add" and len(args) > 1:
        target = args[1]

    evidence: dict[str, Any] = {"target": target, "graph_path": graph_path}
    if family == "build" and not is_url(target):
        target_path = (root / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
        evidence["target_path"] = str(target_path)
        try:
            target_path.relative_to(root)
            evidence["repo_bounded"] = True
        except ValueError:
            evidence["repo_bounded"] = False
        if target_path.is_dir():
            skipped_names = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}
            files = 0
            skipped = 0
            for child in target_path.rglob("*"):
                if any(part in skipped_names for part in child.parts):
                    if child.is_file():
                        skipped += 1
                    continue
                if child.is_file():
                    files += 1
            evidence["local_file_count"] = files
            evidence["skipped_sensitive_or_cache_file_count"] = skipped
    return evidence


def build_payload(
    *,
    status: str,
    argv: list[str],
    classification: dict[str, Any],
    resolution: Resolution,
    returncode: int | None,
    stdout: str = "",
    stderr: str = "",
    message: str = "",
    root: Path,
    handoff: str | None = None,
) -> dict[str, Any]:
    artifacts = discover_artifacts(root)
    payload: dict[str, Any] = {
        "schema_version": "0.1",
        "kind": "graphify_handoff",
        "status": status,
        "message": message,
        "plugin": {"name": PLUGIN_NAME, "version": PLUGIN_VERSION},
        "upstream": {
            "package": PYPI_PACKAGE,
            "command": resolution.label,
            "version": resolution.version,
            "repository": "https://github.com/safishamsi/graphify",
        },
        "command": {
            "family": classification["family"],
            "argv": argv,
            "returncode": returncode,
        },
        "risk": classification["risk"],
        "permissions_used": classification["permissions_used"],
        "permission_sensitive_operations": classification["sensitive_operations"],
        "requires_confirmation": classification["requires_confirmation"],
        "target_evidence": target_evidence(argv, root),
        "artifacts": artifacts,
        "graph_stats": graph_stats(root),
        "backend_model_hints": [a for a in argv if a.startswith("--") and any(k in a for k in ("openai", "gemini", "bedrock", "ollama", "whisper"))],
        "stdout_excerpt": stdout[-4000:] if stdout else "",
        "stderr_excerpt": stderr[-4000:] if stderr else "",
        "generated_at": now_iso(),
        "next_suggested_commands": [
            "ooo graphify query \"what are the central components?\"",
            "ooo graphify path \"source\" \"target\"",
            "ooo auto <attach the graphify handoff as evidence>",
        ],
    }
    if handoff:
        payload["handoff_path"] = handoff
    return payload


def normalize_upstream_args(raw: list[str]) -> list[str]:
    return raw if raw else ["."]


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="graphify_plugin", add_help=True)
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to upstream graphify.")
    parser.add_argument("--handoff-out", help="Write handoff JSON to this path instead of .omx/handoffs/graphify/.")
    parser.add_argument("--no-handoff", action="store_true", help="Do not write handoff JSON; still print result JSON.")
    ns = parser.parse_args(argv)

    upstream_args = normalize_upstream_args(ns.args)
    root = Path.cwd().resolve()
    classification = classify_permissions(upstream_args)
    resolution = resolve_graphify()

    if resolution.argv is None:
        payload = build_payload(
            status="blocked",
            argv=upstream_args,
            classification=classification,
            resolution=resolution,
            returncode=None,
            message=resolution.blocked_reason or "Graphify executable could not be resolved.",
            root=root,
        )
        if not ns.no_handoff:
            out = handoff_path(root, classification["family"], ns.handoff_out)
            payload["handoff_path"] = str(out)
            write_json_atomic(out, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    proc = subprocess.run(
        [*resolution.argv, *upstream_args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    status = "completed" if proc.returncode == 0 else "failed"
    payload = build_payload(
        status=status,
        argv=upstream_args,
        classification=classification,
        resolution=resolution,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        message="Graphify command completed." if proc.returncode == 0 else "Graphify command failed.",
        root=root,
    )
    if not ns.no_handoff:
        out = handoff_path(root, classification["family"], ns.handoff_out)
        payload["handoff_path"] = str(out)
        write_json_atomic(out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(run())
