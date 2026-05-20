"""Command entrypoint for the autoresearch Ouroboros plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PLUGIN_NAME = "autoresearch"
PLUGIN_VERSION = "0.1.0"
UPSTREAM_REPOSITORY = "https://github.com/karpathy/autoresearch"
DEFAULT_PROGRAM_FILE = "program.md"
DEFAULT_TARGET_FILE = "train.py"
DEFAULT_SUPPORT_FILE = "prepare.py"
DEFAULT_METRIC = "val_bpb"
DEFAULT_EXPERIMENT_SECONDS = 300
DEFAULT_MAX_EXPERIMENTS = 8
DEFAULT_TRAIN_COMMAND = "uv run train.py"
ARTIFACT_DIR = Path(".ouroboros") / PLUGIN_NAME


@dataclass(frozen=True)
class RepoInspection:
    root: Path
    program_file: Path
    target_file: Path
    support_file: Path
    program_exists: bool
    target_exists: bool
    support_exists: bool

    @property
    def ready(self) -> bool:
        return self.program_exists and self.target_exists and self.support_exists

    @property
    def missing(self) -> list[str]:
        missing: list[str] = []
        if not self.program_exists:
            missing.append(display_path(self.program_file, self.root))
        if not self.target_exists:
            missing.append(display_path(self.target_file, self.root))
        if not self.support_exists:
            missing.append(display_path(self.support_file, self.root))
        return missing


def display_path(path: Path, root: Path) -> str:
    """Return a stable repo-relative path when possible."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def repo_member_path(root: Path, raw_path: str, label: str) -> Path:
    """Resolve a user-supplied repo member path without allowing escape."""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"{label} must be a path relative to the repository root")

    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"{label} must stay inside the repository root"
        ) from exc
    return resolved


def inspect_repo(
    repository_path: str,
    *,
    program_file: str = DEFAULT_PROGRAM_FILE,
    target_file: str = DEFAULT_TARGET_FILE,
    support_file: str = DEFAULT_SUPPORT_FILE,
) -> RepoInspection:
    root = Path(repository_path).expanduser().resolve()
    program = repo_member_path(root, program_file, "--program-file")
    target = repo_member_path(root, target_file, "--target-file")
    support = repo_member_path(root, support_file, "--support-file")
    return RepoInspection(
        root=root,
        program_file=program,
        target_file=target,
        support_file=support,
        program_exists=program.is_file(),
        target_exists=target.is_file(),
        support_exists=support.is_file(),
    )


def read_excerpt(path: Path, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[excerpt truncated]"


def write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def sha256_file(path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": size}


def run_git(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def git_metadata(root: Path) -> dict:
    inside = run_git(root, "rev-parse", "--is-inside-work-tree") == "true"
    if not inside:
        return {"is_git_repository": False}

    status = run_git(root, "status", "--porcelain")
    return {
        "is_git_repository": True,
        "remote_origin": run_git(root, "remote", "get-url", "origin"),
        "commit": run_git(root, "rev-parse", "HEAD"),
        "branch": run_git(root, "branch", "--show-current"),
        "dirty": bool(status),
        "status_porcelain": status or "",
    }


def provenance_payload(inspection: RepoInspection) -> dict:
    files = {}
    for label, path in (
        ("program", inspection.program_file),
        ("target", inspection.target_file),
        ("support", inspection.support_file),
    ):
        rel = display_path(path, inspection.root)
        files[label] = {"path": rel, **sha256_file(path)}

    return {
        "upstream": UPSTREAM_REPOSITORY,
        "repository": str(inspection.root),
        "git": git_metadata(inspection.root),
        "files": files,
    }


def fenced_code_block(language: str, content: str) -> list[str]:
    """Return a Markdown code fence that cannot be closed by its content."""
    longest_run = 0
    current_run = 0
    for char in content:
        if char == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * max(3, longest_run + 1)
    return [f"{fence}{language}", content.rstrip(), fence]


def build_seed_markdown(
    inspection: RepoInspection,
    *,
    goal: str,
    metric: str,
    max_experiments: int,
    experiment_seconds: int,
    train_command: str,
) -> str:
    program_excerpt = read_excerpt(inspection.program_file)
    target_rel = display_path(inspection.target_file, inspection.root)
    program_rel = display_path(inspection.program_file, inspection.root)
    support_rel = display_path(inspection.support_file, inspection.root)
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Autoresearch Ouroboros Seed",
        "",
        f"generated_at: {generated_at}",
        f"repository: {inspection.root}",
        f"upstream: {UPSTREAM_REPOSITORY}",
        "",
        "## Goal",
        "",
        goal,
        "",
        "## Execution Boundary",
        "",
        f"- Edit only `{target_rel}` unless the user explicitly widens scope.",
        f"- Treat `{program_rel}` as the research program and product requirements.",
        f"- Treat `{support_rel}` as fixed data prep and runtime utility code.",
        f"- Run at most {max_experiments} experiments.",
        f"- Keep each experiment bounded to {experiment_seconds} seconds.",
        f"- Use `{metric}` as the primary comparison metric.",
        f"- Prefer changes that improve `{metric}` and preserve a reproducible command trail.",
        "",
        "## Verification Command",
        "",
        *fenced_code_block("bash", train_command),
        "",
        "## Acceptance Criteria",
        "",
        f"- The final result reports the best observed `{metric}` and the baseline value if available.",
        f"- Every experiment records command, changed files, observed `{metric}`, and conclusion.",
        f"- The final patch is limited to `{target_rel}` unless scope was widened in the ledger.",
        "- The run stops when the experiment budget is exhausted or no promising next edit remains.",
        "",
        "## Program Excerpt",
        "",
        *fenced_code_block("markdown", program_excerpt),
        "",
    ]
    return "\n".join(lines)


def build_auto_goal(
    inspection: RepoInspection,
    *,
    goal: str,
    metric: str,
    max_experiments: int,
    experiment_seconds: int,
    train_command: str,
    seed_path: Path,
) -> str:
    target_rel = display_path(inspection.target_file, inspection.root)
    program_rel = display_path(inspection.program_file, inspection.root)
    support_rel = display_path(inspection.support_file, inspection.root)
    return "\n".join(
        [
            goal,
            "",
            "Use the prepared autoresearch handoff brief at:",
            str(seed_path),
            "",
            "Concrete constraints for the generated Ouroboros Seed:",
            f"- Work in repository: {inspection.root}",
            f"- Treat `{program_rel}` as the research program/instructions.",
            f"- Edit only `{target_rel}` unless explicitly widening scope in the ledger.",
            f"- Treat `{support_rel}` as fixed data prep/runtime utility code.",
            f"- Run at most {max_experiments} experiments.",
            f"- Keep each experiment bounded to {experiment_seconds} seconds.",
            f"- Use `{metric}` as the primary metric; lower is better.",
            f"- Verification command: `{train_command}`.",
            "- Do not run training during Seed creation; only prepare the bounded plan unless execution is explicitly requested.",
            "",
        ]
    )


def write_handoff(
    inspection: RepoInspection,
    *,
    goal: str,
    metric: str,
    max_experiments: int,
    experiment_seconds: int,
    train_command: str,
) -> dict:
    if not inspection.ready:
        raise ValueError("repository is missing required autoresearch files")

    out_dir = inspection.root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_path = out_dir / "seed.md"
    auto_goal_path = out_dir / "auto_goal.txt"
    handoff_path = out_dir / "handoff.json"

    seed = build_seed_markdown(
        inspection,
        goal=goal,
        metric=metric,
        max_experiments=max_experiments,
        experiment_seconds=experiment_seconds,
        train_command=train_command,
    )
    write_text_atomic(seed_path, seed)
    auto_goal = build_auto_goal(
        inspection,
        goal=goal,
        metric=metric,
        max_experiments=max_experiments,
        experiment_seconds=experiment_seconds,
        train_command=train_command,
        seed_path=seed_path,
    )
    write_text_atomic(auto_goal_path, auto_goal)

    handoff = {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "status": "prepared",
        "repository": str(inspection.root),
        "seed_path": str(seed_path),
        "auto_goal_path": str(auto_goal_path),
        "handoff_path": str(handoff_path),
        "upstream": UPSTREAM_REPOSITORY,
        "provenance": provenance_payload(inspection),
        "ooo_auto": {
            "recommended_command": (
                f"ouroboros auto \"$(cat {shlex.quote(str(auto_goal_path))})\""
            ),
            "goal": goal,
            "metric": metric,
            "max_experiments": max_experiments,
            "experiment_seconds": experiment_seconds,
            "train_command": train_command,
            "editable_files": [display_path(inspection.target_file, inspection.root)],
        },
    }
    write_text_atomic(handoff_path, json.dumps(handoff, indent=2) + "\n")
    return handoff


def inspection_payload(inspection: RepoInspection) -> dict:
    return {
        "plugin": PLUGIN_NAME,
        "status": "ready" if inspection.ready else "missing_prerequisites",
        "repository": str(inspection.root),
        "required_files": {
            display_path(inspection.program_file, inspection.root): inspection.program_exists,
            display_path(inspection.target_file, inspection.root): inspection.target_exists,
            display_path(inspection.support_file, inspection.root): inspection.support_exists,
        },
        "missing": inspection.missing,
        "ooo_auto_ready": inspection.ready,
    }


def positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoresearch")
    parser.add_argument("command", choices=["inspect", "prepare"])
    parser.add_argument("repository_path")
    parser.add_argument("--program-file", default=DEFAULT_PROGRAM_FILE)
    parser.add_argument("--target-file", default=DEFAULT_TARGET_FILE)
    parser.add_argument("--support-file", default=DEFAULT_SUPPORT_FILE)
    parser.add_argument("--goal", default="")
    parser.add_argument("--metric", default=DEFAULT_METRIC)
    parser.add_argument("--max-experiments", type=positive_int, default=DEFAULT_MAX_EXPERIMENTS)
    parser.add_argument("--experiment-seconds", type=positive_int, default=DEFAULT_EXPERIMENT_SECONDS)
    parser.add_argument("--train-command", default=DEFAULT_TRAIN_COMMAND)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        inspection = inspect_repo(
            args.repository_path,
            program_file=args.program_file,
            target_file=args.target_file,
            support_file=args.support_file,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.command == "inspect":
        sys.stdout.write(json.dumps(inspection_payload(inspection), indent=2) + "\n")
        return 0 if inspection.ready else 1

    if not args.goal.strip():
        parser.error("prepare requires --goal")
    if not inspection.ready:
        missing = ", ".join(inspection.missing)
        sys.stderr.write(f"autoresearch: missing required file(s): {missing}\n")
        return 1

    handoff = write_handoff(
        inspection,
        goal=args.goal.strip(),
        metric=args.metric,
        max_experiments=args.max_experiments,
        experiment_seconds=args.experiment_seconds,
        train_command=args.train_command,
    )
    sys.stdout.write(json.dumps(handoff, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
