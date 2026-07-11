"""Deterministic evidence harvest: repository facts in, research bundle out."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BUNDLE_SCHEMA_VERSION = "ouroboros.paper-writer.research-bundle.v0.1"

DOC_FILES = ("README.md", "WHITEPAPER.md", "STATUS.md", "GOVERNANCE.md")
EVIDENCE_DIRS = {
    "spec": "spec",
    "rfd": "rfds",
    "domain_pack": "domain-packs",
    "adapter": "adapters",
    "conformance": "conformance",
}
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt", ".py", ".rs", ".ts"}
PYTEST_SUMMARY = re.compile(r"(\d+) (passed|failed|skipped|errors|error|xfailed|xpassed)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_safe_regular_file(path: Path, root: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
    except OSError:
        pass
    return path.stem


def iter_evidence_files(root: Path, directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.suffix.lower() in TEXT_SUFFIXES and is_safe_regular_file(path, root)
    )


def evidence_id(kind: str, index: int) -> str:
    short = {
        "doc": "DOC",
        "spec": "SPEC",
        "rfd": "RFD",
        "domain_pack": "PACK",
        "adapter": "ADPT",
        "conformance": "CONF",
        "test": "TEST",
        "test_log": "XLOG",
        "experiment": "EXPT",
        "source": "SRC",
    }[kind]
    return f"E-{short}-{index:03d}"


def collect_dir_evidence(root: Path, kind: str, dirname: str) -> list[dict[str, object]]:
    directory = root / dirname
    items: list[dict[str, object]] = []
    if kind in ("domain_pack", "adapter"):
        if not directory.is_dir():
            return items
        members = sorted(p for p in directory.iterdir() if p.is_dir() and not p.name.startswith("."))
        for index, member in enumerate(members, start=1):
            file_count = sum(1 for p in member.rglob("*") if is_safe_regular_file(p, root))
            items.append(
                {
                    "id": evidence_id(kind, index),
                    "kind": kind,
                    "path": member.relative_to(root).as_posix(),
                    "title": member.name,
                    "detail": {"file_count": file_count},
                }
            )
        return items
    for index, path in enumerate(iter_evidence_files(root, directory), start=1):
        items.append(
            {
                "id": evidence_id(kind, index),
                "kind": kind,
                "path": path.relative_to(root).as_posix(),
                "title": first_heading(path) if path.suffix.lower() == ".md" else path.name,
                "detail": {"bytes": path.stat().st_size},
            }
        )
    return items


def collect_doc_evidence(root: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    index = 0
    for name in DOC_FILES:
        path = root / name
        if not is_safe_regular_file(path, root):
            continue
        index += 1
        items.append(
            {
                "id": evidence_id("doc", index),
                "kind": "doc",
                "path": name,
                "title": first_heading(path),
                "detail": {"bytes": path.stat().st_size},
            }
        )
    return items


def collect_test_evidence(root: Path) -> tuple[list[dict[str, object]], int]:
    tests_dir = root / "tests"
    items: list[dict[str, object]] = []
    total_functions = 0
    if not tests_dir.is_dir():
        return items, total_functions
    files = sorted(
        path
        for path in tests_dir.rglob("test_*.py")
        if is_safe_regular_file(path, root)
    )
    for index, path in enumerate(files, start=1):
        text = path.read_text(encoding="utf-8", errors="replace")
        function_count = len(re.findall(r"^\s*def test_", text, flags=re.MULTILINE))
        total_functions += function_count
        items.append(
            {
                "id": evidence_id("test", index),
                "kind": "test",
                "path": path.relative_to(root).as_posix(),
                "title": path.name,
                "detail": {"test_functions": function_count},
            }
        )
    return items, total_functions


def parse_pytest_log(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for value, label in PYTEST_SUMMARY.findall(line):
            key = "error" if label in ("error", "errors") else label
            counts[key] = int(value)
    return counts


def collect_test_log_evidence(root: Path, test_log: Path | None) -> list[dict[str, object]]:
    if test_log is None or not test_log.is_file():
        return []
    counts = parse_pytest_log(test_log)
    if not counts:
        return []
    return [
        {
            "id": evidence_id("test_log", 1),
            "kind": "test_log",
            "path": str(test_log),
            "title": "pytest summary",
            "detail": counts,
        }
    ]


def collect_experiment_evidence(root: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    index = 0
    experiments = root / "artifacts" / "experiments.jsonl"
    if is_safe_regular_file(experiments, root):
        rows: list[dict[str, object]] = []
        for line in experiments.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        if rows:
            index += 1
            items.append(
                {
                    "id": evidence_id("experiment", index),
                    "kind": "experiment",
                    "path": experiments.relative_to(root).as_posix(),
                    "title": "experiment ledger (jsonl)",
                    "detail": {"rows": len(rows), "last_row": rows[-1]},
                }
            )
    for path in sorted((root / "artifacts").glob("*.json")):
        if not is_safe_regular_file(path, root):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        index += 1
        detail: dict[str, object] = {"top_level_keys": sorted(payload)[:12]}
        if isinstance(payload.get("aggregate"), dict):
            detail["aggregate"] = payload["aggregate"].get("counts", payload["aggregate"])
        items.append(
            {
                "id": evidence_id("experiment", index),
                "kind": "experiment",
                "path": path.relative_to(root).as_posix(),
                "title": f"experiment artifact ({path.stem})",
                "detail": detail,
            }
        )
    autoresearch_handoff = root / ".ouroboros" / "autoresearch" / "handoff.json"
    if is_safe_regular_file(autoresearch_handoff, root):
        try:
            handoff = json.loads(autoresearch_handoff.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            handoff = {}
        index += 1
        items.append(
            {
                "id": evidence_id("experiment", index),
                "kind": "experiment",
                "path": autoresearch_handoff.relative_to(root).as_posix(),
                "title": "autoresearch handoff",
                "detail": {
                    "status": handoff.get("status"),
                    "metric": handoff.get("ooo_auto", {}).get("metric"),
                },
            }
        )
    return items


def collect_source_evidence(root: Path) -> list[dict[str, object]]:
    src_dir = root / "src"
    if not src_dir.is_dir():
        return []
    files = [
        path
        for path in src_dir.rglob("*")
        if path.suffix.lower() in (".py", ".rs", ".ts", ".go") and is_safe_regular_file(path, root)
    ]
    loc = 0
    for path in files:
        loc += sum(
            1
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        )
    if not files:
        return []
    return [
        {
            "id": evidence_id("source", 1),
            "kind": "source",
            "path": "src",
            "title": "implementation",
            "detail": {"file_count": len(files), "loc_nonblank": loc},
        }
    ]


def harvest_bundle(root: Path, *, test_log: Path | None = None) -> dict[str, object]:
    evidence: list[dict[str, object]] = []
    evidence += collect_doc_evidence(root)
    for kind, dirname in EVIDENCE_DIRS.items():
        evidence += collect_dir_evidence(root, kind, dirname)
    test_items, test_functions = collect_test_evidence(root)
    evidence += test_items
    evidence += collect_test_log_evidence(root, test_log)
    evidence += collect_experiment_evidence(root)
    evidence += collect_source_evidence(root)

    counts: dict[str, int] = {}
    for item in evidence:
        counts[str(item["kind"])] = counts.get(str(item["kind"]), 0) + 1
    pytest_counts = next(
        (item["detail"] for item in evidence if item["kind"] == "test_log"),
        None,
    )
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repository": str(root),
        "evidence": evidence,
        "summary": {
            "counts": counts,
            "test_functions": test_functions,
            "pytest": pytest_counts,
        },
    }
