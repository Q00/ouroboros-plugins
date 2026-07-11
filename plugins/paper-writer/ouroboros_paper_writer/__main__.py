"""Command entrypoint for the paper-writer Ouroboros plugin."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import PLUGIN_NAME
from .bundle import harvest_bundle
from .contract import (
    DEFAULT_MAX_ADDITIONAL_RUNS,
    DEFAULT_MAX_REVIEW_ROUNDS,
    DEFAULT_PAPER_TYPE,
    DEFAULT_REVIEWER_MODEL,
    DEFAULT_VENUE,
    DEFAULT_WRITER_MODEL,
    PAPER_TYPES,
    build_paper_contract,
    load_claims_file,
)
from .latex import render_latex
from .report import (
    LOOP_SCHEMA_VERSION,
    build_gap_report,
    build_handoff,
    build_review_report,
    build_reviewer_brief,
    build_revision_brief,
    build_writing_brief,
    handoff_markdown,
    validate_review,
    verify_draft,
)

ARTIFACT_DIR = Path(".ouroboros") / PLUGIN_NAME
CONTRACT_FILE = "paper_contract.json"
BUNDLE_FILE = "research_bundle.json"
GAP_FILE = "gap_report.json"
BRIEF_FILE = "writing_brief.md"
PAPER_FILE = "paper.md"
COMPOSE_FILE = "compose_report.json"
HANDOFF_JSON = "handoff.json"
HANDOFF_MD = "handoff.md"

EVIDENCE_SOURCES = (
    "README.md",
    "WHITEPAPER.md",
    "spec",
    "rfds",
    "domain-packs",
    "adapters",
    "conformance",
    "tests",
    "src",
)


def resolve_root(repository_path: str) -> Path:
    root = Path(repository_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    return root


def artifact_dir(root: Path) -> Path:
    return root / ARTIFACT_DIR


def write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def write_json_artifact(path: Path, payload: dict) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_json_artifact(root: Path, name: str, produced_by: str) -> dict:
    path = artifact_dir(root) / name
    if not path.is_file():
        raise FileNotFoundError(
            f"missing {path}; run `paper {produced_by}` first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def cmd_inspect(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    sources = {name: (root / name).exists() for name in EVIDENCE_SOURCES}
    ready = any(sources.values())
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "ready" if ready else "missing_prerequisites",
            "repository": str(root),
            "evidence_sources": sources,
            "artifact_dir": str(artifact_dir(root)),
        }
    )
    return 0 if ready else 1


def cmd_prepare(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    claims = None
    if args.claims_file:
        claims = load_claims_file(Path(args.claims_file).expanduser().resolve())
    contract = build_paper_contract(
        repository=root,
        thesis=args.thesis.strip(),
        venue=args.venue,
        paper_type=args.paper_type,
        page_limit=args.page_limit,
        writer_model=args.writer_model,
        claims=claims,
        max_additional_runs=args.max_additional_runs,
        research_queries=args.research_query,
        reviewer_model=args.reviewer_model,
        max_review_rounds=args.max_review_rounds,
    )
    out_dir = artifact_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(out_dir / CONTRACT_FILE, contract)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "prepared",
            "contract_path": str(out_dir / CONTRACT_FILE),
            "claims": [claim["id"] for claim in contract["claims"]],
            "writer_model": contract["writer_policy"]["writer_model"],
        }
    )
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    test_log = Path(args.test_log).expanduser().resolve() if args.test_log else None
    bundle = harvest_bundle(root, test_log=test_log)
    out_dir = artifact_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(out_dir / BUNDLE_FILE, bundle)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "harvested",
            "bundle_path": str(out_dir / BUNDLE_FILE),
            "summary": bundle["summary"],
        }
    )
    return 0


def cmd_gap(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    bundle = load_json_artifact(root, BUNDLE_FILE, "harvest")
    gap = build_gap_report(contract, bundle)
    write_json_artifact(artifact_dir(root) / GAP_FILE, gap)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "writing_ready" if gap["summary"]["writing_ready"] else "evidence_gaps",
            "gap_path": str(artifact_dir(root) / GAP_FILE),
            "summary": gap["summary"],
        }
    )
    return 0 if gap["summary"]["writing_ready"] else 1


def cmd_brief(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    bundle = load_json_artifact(root, BUNDLE_FILE, "harvest")
    gap = load_json_artifact(root, GAP_FILE, "gap")
    brief = build_writing_brief(contract, bundle, gap)
    brief_path = artifact_dir(root) / BRIEF_FILE
    write_text_atomic(brief_path, brief)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "brief_ready",
            "brief_path": str(brief_path),
            "writer_model": contract["writer_policy"]["writer_model"],
            "note": (
                "Spawn a writer subagent on writer_model with the brief file as "
                "its task; the plugin never writes prose."
            ),
        }
    )
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    bundle = load_json_artifact(root, BUNDLE_FILE, "harvest")
    gap = load_json_artifact(root, GAP_FILE, "gap")
    draft_path = Path(args.draft).expanduser().resolve()
    if not draft_path.is_file():
        raise FileNotFoundError(f"draft not found: {draft_path}")
    draft_text = draft_path.read_text(encoding="utf-8")
    compose_report = verify_draft(contract, bundle, gap, draft_text)
    out_dir = artifact_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_path = out_dir / PAPER_FILE
    write_text_atomic(paper_path, draft_text)
    write_json_artifact(out_dir / COMPOSE_FILE, compose_report)
    handoff = build_handoff(
        contract,
        gap,
        compose_report,
        artifact_dir=out_dir,
        paper_path=paper_path,
    )
    write_json_artifact(out_dir / HANDOFF_JSON, handoff)
    write_text_atomic(out_dir / HANDOFF_MD, handoff_markdown(handoff))
    emit(handoff)
    return 0 if compose_report["status"] == "verified" else 1


def cmd_review(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    out_dir = artifact_dir(root)
    reviews_dir = out_dir / "reviews"
    policy = contract["review_policy"]

    if not args.ingest:
        if not (out_dir / PAPER_FILE).is_file():
            raise FileNotFoundError(
                f"missing {out_dir / PAPER_FILE}; run `paper compose` first"
            )
        reviews_dir.mkdir(parents=True, exist_ok=True)
        briefs = []
        for persona in policy["personas"]:
            brief = build_reviewer_brief(
                contract,
                persona,
                paper_path=str(out_dir / PAPER_FILE),
                bundle_path=str(out_dir / BUNDLE_FILE),
                gap_path=str(out_dir / GAP_FILE),
                output_path=str(reviews_dir / f"{persona['id']}.json"),
            )
            brief_path = reviews_dir / f"brief-{persona['id']}.md"
            write_text_atomic(brief_path, brief)
            briefs.append(str(brief_path))
        emit(
            {
                "plugin": PLUGIN_NAME,
                "status": "review_briefs_ready",
                "reviewer_model": policy["reviewer_model"],
                "briefs": briefs,
                "note": (
                    "Spawn one FRESH subagent per brief on reviewer_model (never "
                    "the writer agent), then run `paper review --ingest`."
                ),
            }
        )
        return 0

    reviews = []
    problems = []
    for persona in policy["personas"]:
        review_path = reviews_dir / f"{persona['id']}.json"
        if not review_path.is_file():
            problems.append(f"missing review {review_path}")
            continue
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review_problems = validate_review(review)
        if review_problems:
            problems.append(f"{persona['id']}: {'; '.join(review_problems)}")
            continue
        reviews.append(review)
    if problems:
        sys.stderr.write(f"{PLUGIN_NAME}: invalid reviews: {problems}\n")
        return 1
    report = build_review_report(contract, reviews)
    write_json_artifact(out_dir / "review_report.json", report)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": report["status"],
            "report_path": str(out_dir / "review_report.json"),
            "summary": report["summary"],
            "revision_actions": report["revision_actions"],
        }
    )
    return 0 if report["status"].startswith("review_passed") else 1


def cmd_revise(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    gap = load_json_artifact(root, GAP_FILE, "gap")
    review_report = load_json_artifact(root, "review_report.json", "review --ingest")
    out_dir = artifact_dir(root)
    policy = contract["revision_loop_policy"]

    if review_report["status"].startswith("review_passed"):
        emit(
            {
                "plugin": PLUGIN_NAME,
                "status": "no_revision_needed",
                "note": "review gate already passed; proceed to latex and human review",
            }
        )
        return 0

    ledger_path = out_dir / "loop_ledger.json"
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.is_file()
        else {"schema_version": LOOP_SCHEMA_VERSION, "rounds": []}
    )
    summary = review_report["summary"]
    rounds = ledger["rounds"]
    already_recorded = bool(rounds) and rounds[-1].get("report_generated_at") == review_report["generated_at"]
    if already_recorded:
        round_number = rounds[-1]["round"]
    else:
        round_number = len(rounds) + 1
        rounds.append(
            {
                "round": round_number,
                "report_generated_at": review_report["generated_at"],
                "average_score": summary["average_score"],
                "scores": summary["scores"],
                "major_count": len(summary["major_weaknesses"]),
                "status": review_report["status"],
            }
        )
        write_json_artifact(ledger_path, ledger)

    warnings = []
    if round_number >= 2:
        previous = ledger["rounds"][round_number - 2]["average_score"]
        if summary["average_score"] <= previous:
            warnings.append(
                f"stagnation: average {summary['average_score']} did not improve "
                f"over previous round ({previous}); per stop_conditions consider "
                "escalating instead of rewriting"
            )
    if round_number >= policy["max_review_rounds"]:
        emit(
            {
                "plugin": PLUGIN_NAME,
                "status": "loop_budget_exhausted",
                "rounds_used": round_number,
                "max_review_rounds": policy["max_review_rounds"],
                "warnings": warnings,
                "note": (
                    "Round budget exhausted without passing the gate; escalate "
                    "to a human decision or to additional_experiment_policy."
                ),
            }
        )
        return 1

    archive_dir = out_dir / "rounds" / f"round-{round_number}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir = out_dir / "reviews"
    for persona in contract["review_policy"]["personas"]:
        review_file = reviews_dir / f"{persona['id']}.json"
        if review_file.is_file():
            review_file.replace(archive_dir / review_file.name)
    (out_dir / "review_report.json").replace(archive_dir / "review_report.json")

    brief = build_revision_brief(contract, review_report, gap, round_number)
    brief_path = out_dir / "revision_brief.md"
    write_text_atomic(brief_path, brief)
    emit(
        {
            "plugin": PLUGIN_NAME,
            "status": "revision_brief_ready",
            "round": round_number,
            "brief_path": str(brief_path),
            "archived_round": str(archive_dir),
            "writer_model": contract["writer_policy"]["writer_model"],
            "warnings": warnings,
            "note": (
                "Writer subagent applies the brief, then compose, then FRESH "
                "reviewers, then review --ingest."
            ),
        }
    )
    return 0


def cmd_latex(args: argparse.Namespace) -> int:
    root = resolve_root(args.repository_path)
    contract = load_json_artifact(root, CONTRACT_FILE, "prepare")
    out_dir = artifact_dir(root)
    paper_path = out_dir / PAPER_FILE
    if not paper_path.is_file():
        raise FileNotFoundError(f"missing {paper_path}; run `paper compose` first")
    references_json = out_dir / "references.json"
    result = render_latex(
        paper_path,
        references_json=references_json if references_json.is_file() else None,
        out_dir=out_dir,
        venue_name=contract["venue"]["name"],
    )
    payload = {"plugin": PLUGIN_NAME, "status": "latex_ready", **result}
    if result["unresolved_citations"]:
        payload["status"] = "latex_ready_with_unresolved_citations"
        payload["note"] = (
            "Resolve the placeholder citations via the contract's "
            "web_research_plan before submission."
        )
    emit(payload)
    return 0


def positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-writer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("repository_path")
    inspect.set_defaults(handler=cmd_inspect)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("repository_path")
    prepare.add_argument("--thesis", required=True)
    prepare.add_argument("--venue", default=DEFAULT_VENUE)
    prepare.add_argument("--paper-type", choices=PAPER_TYPES, default=DEFAULT_PAPER_TYPE)
    prepare.add_argument("--page-limit", type=positive_int, default=None)
    prepare.add_argument("--writer-model", default=DEFAULT_WRITER_MODEL)
    prepare.add_argument("--claims-file", default=None)
    prepare.add_argument(
        "--max-additional-runs", type=positive_int, default=DEFAULT_MAX_ADDITIONAL_RUNS
    )
    prepare.add_argument("--research-query", action="append", default=None)
    prepare.add_argument("--reviewer-model", default=DEFAULT_REVIEWER_MODEL)
    prepare.add_argument(
        "--max-review-rounds", type=positive_int, default=DEFAULT_MAX_REVIEW_ROUNDS
    )
    prepare.set_defaults(handler=cmd_prepare)

    harvest = subparsers.add_parser("harvest")
    harvest.add_argument("repository_path")
    harvest.add_argument("--test-log", default=None)
    harvest.set_defaults(handler=cmd_harvest)

    gap = subparsers.add_parser("gap")
    gap.add_argument("repository_path")
    gap.set_defaults(handler=cmd_gap)

    brief = subparsers.add_parser("brief")
    brief.add_argument("repository_path")
    brief.set_defaults(handler=cmd_brief)

    compose = subparsers.add_parser("compose")
    compose.add_argument("repository_path")
    compose.add_argument("--draft", required=True)
    compose.set_defaults(handler=cmd_compose)

    revise = subparsers.add_parser("revise")
    revise.add_argument("repository_path")
    revise.set_defaults(handler=cmd_revise)

    review = subparsers.add_parser("review")
    review.add_argument("repository_path")
    review.add_argument("--ingest", action="store_true")
    review.set_defaults(handler=cmd_review)

    latex = subparsers.add_parser("latex")
    latex.add_argument("repository_path")
    latex.set_defaults(handler=cmd_latex)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ValueError, FileNotFoundError) as exc:
        sys.stderr.write(f"{PLUGIN_NAME}: {exc}\n")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
