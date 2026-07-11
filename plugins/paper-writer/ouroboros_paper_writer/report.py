"""Gap analysis, writing brief, and compose verification for the paper contract."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

GAP_SCHEMA_VERSION = "ouroboros.paper-writer.gap-report.v0.1"
COMPOSE_SCHEMA_VERSION = "ouroboros.paper-writer.compose-report.v0.1"
HANDOFF_SCHEMA_VERSION = "ouroboros.paper-writer.handoff.v0.1"
REVIEW_SCHEMA_VERSION = "ouroboros.paper-writer.review-report.v0.1"

EVIDENCE_REF = re.compile(r"\[E-[A-Z]+-\d{3}\]")
WORDS_PER_PAGE = 550


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_substantive(item: dict) -> bool:
    """An empty directory is a reserved boundary, not evidence."""
    return item.get("detail", {}).get("file_count") != 0


def evidence_by_kind(bundle: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in bundle.get("evidence", []):
        if not is_substantive(item):
            continue
        grouped.setdefault(str(item["kind"]), []).append(item)
    return grouped


def suggested_auto_goal(repository: str, claim: dict, missing: list[dict]) -> str:
    needs = ", ".join(
        f"{requirement['min_count']}x {requirement['kind']}" for requirement in missing
    )
    return (
        f"Run a bounded evidence-gathering experiment in repository {repository} "
        f"to support paper claim {claim['id']}: {claim['statement']} "
        f"Produce machine-checkable evidence of kind(s): {needs}. "
        "Record every run in a reproducible ledger, keep the repository layout "
        "unchanged, and stop when the evidence exists or the budget is exhausted."
    )


def build_gap_report(contract: dict, bundle: dict) -> dict:
    grouped = evidence_by_kind(bundle)
    claims: list[dict] = []
    unsupported = 0
    for claim in contract["claims"]:
        missing: list[dict] = []
        matched: list[str] = []
        for requirement in claim["evidence_required"]:
            kind = str(requirement["kind"])
            min_count = int(requirement.get("min_count", 1))
            available = grouped.get(kind, [])
            if len(available) < min_count:
                missing.append({"kind": kind, "min_count": min_count, "available": len(available)})
            else:
                matched.extend(str(item["id"]) for item in available[:min_count])
        entry: dict = {
            "id": claim["id"],
            "statement": claim["statement"],
            "status": "supported" if not missing else "unsupported",
            "matched_evidence": matched,
            "missing": missing,
        }
        if missing:
            unsupported += 1
            entry["suggested_actions"] = [
                {
                    "action": "run_additional_experiment",
                    "entrypoint": contract["additional_experiment_policy"]["entrypoint"],
                    "auto_goal": suggested_auto_goal(contract["repository"], claim, missing),
                },
                {
                    "action": "downgrade_claim",
                    "note": (
                        "Restate the claim as a position or future-work item inside "
                        "Discussion and Limitations."
                    ),
                },
            ]
        claims.append(entry)
    return {
        "schema_version": GAP_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repository": contract["repository"],
        "claims": claims,
        "summary": {
            "total_claims": len(claims),
            "supported": len(claims) - unsupported,
            "unsupported": unsupported,
            "writing_ready": unsupported == 0,
        },
    }


def fenced_json(payload: object) -> list[str]:
    return ["```json", json.dumps(payload, indent=2, ensure_ascii=False), "```"]


def build_writing_brief(contract: dict, bundle: dict, gap: dict) -> str:
    venue = contract["venue"]
    writer = contract["writer_policy"]
    rules = contract["writing_rules"]
    lines = [
        "# Paper Writing Brief",
        "",
        f"generated_at: {utc_now()}",
        f"repository: {contract['repository']}",
        "",
        "## Writer Policy",
        "",
        f"- This brief must be executed by a dedicated writer subagent on model `{writer['writer_model']}`.",
        "- The plugin only prepared this brief; all prose is the writer's responsibility.",
        "- Return exactly one Markdown document as the draft.",
        "",
        "## Thesis",
        "",
        contract["thesis"],
        "",
        f"- Paper type: {contract['paper_type']}",
        f"- Venue: {venue['name']} ({venue['review_model']})",
        f"- Main-text budget: {venue['page_limit_main_text']} pages "
        f"(~{venue['page_limit_main_text'] * WORDS_PER_PAGE} words; references/appendix excluded).",
        "",
        "## Required Sections",
        "",
        "The draft must contain every heading below as a `## <name>` heading, in order:",
        "",
    ]
    lines += [f"1. {name}" for name in venue["required_sections"]]
    lines += [
        "",
        "## Claims",
        "",
        "Each claim id must appear verbatim (e.g. `C1`) where the paper argues it.",
        "Unsupported claims may only appear inside Discussion and Limitations,",
        "explicitly framed as positions or future work.",
        "",
    ]
    for claim in gap["claims"]:
        lines.append(f"- **{claim['id']}** [{claim['status']}]: {claim['statement']}")
        if claim["matched_evidence"]:
            lines.append(f"  - evidence: {', '.join(claim['matched_evidence'])}")
        for missing in claim.get("missing", []):
            lines.append(
                f"  - missing: {missing['min_count']}x {missing['kind']} "
                f"(available: {missing['available']})"
            )
    lines += [
        "",
        "## Hard Writing Rules",
        "",
        f"- {rules['no_fabricated_numbers']}",
        f"- {rules['external_citations']}",
        f"- {rules['unsupported_claims']}",
        f"- {rules['anonymization']}",
        "- Do not cite evidence ids that are absent from the evidence appendix below.",
        "",
        "## Web Research Contract",
        "",
        "The host agent (not the writer) owns these searches; findings arrive as",
        "references.json and a venue-trends note. Writer obligations:",
        "- Use [cite:key] placeholders only; the bibliography is resolved from",
        "  verified web research, never from memory.",
        "- If a venue-trends note exists in the artifact directory, align framing",
        "  with it without weakening any claim-evidence rule.",
        "",
    ] + [
        f"- host query: {query}"
        for query in contract.get("web_research_plan", {}).get("queries", [])
    ] + [
        "",
        "## Venue Readiness Checklist (context for Reproducibility/Ethics sections)",
        "",
    ]
    lines += [f"- {item}" for item in venue["readiness_checklist"]]
    lines += [
        "",
        "## Evidence Appendix",
        "",
        "Quantitative statements must cite these ids in the form `[E-...]`.",
        "",
        *fenced_json(
            {
                "summary": bundle["summary"],
                "evidence": bundle["evidence"],
            }
        ),
        "",
    ]
    return "\n".join(lines)


def build_reviewer_brief(
    contract: dict,
    persona: dict,
    *,
    paper_path: str,
    bundle_path: str,
    gap_path: str,
    output_path: str,
) -> str:
    policy = contract["review_policy"]
    rubric = policy["rubric"]
    lines = [
        f"# Reviewer Brief {persona['id']}",
        "",
        f"- Model: `{policy['reviewer_model']}`",
        f"- Independence: {policy['independence_rule']}",
        f"- Venue: {contract['venue']['name']} ({contract['paper_type']} paper)",
        "",
        "## Your lens",
        "",
        f"Focus: {persona['focus']}.",
        "",
        persona["instruction"],
        "",
        "## Inputs (read all three)",
        "",
        f"- Draft: `{paper_path}`",
        f"- Research bundle (source of truth for every [E-...] id): `{bundle_path}`",
        f"- Gap report (claim support status): `{gap_path}`",
        "",
        "## Rules",
        "",
    ]
    lines += [f"- {rule}" for rule in rubric["rules"]]
    lines += [
        "",
        "## Output",
        "",
        f"Write EXACTLY one JSON object to `{output_path}` matching:",
        "",
        *fenced_json(rubric["output_schema"]),
        "",
    ]
    return "\n".join(lines)


def validate_review(review: dict) -> list[str]:
    problems = []
    for field in ("reviewer_id", "summary", "strengths", "weaknesses", "score", "confidence"):
        if field not in review:
            problems.append(f"missing field {field!r}")
    score = review.get("score")
    if not isinstance(score, int) or not 1 <= score <= 10:
        problems.append("score must be an integer 1-10")
    for weakness in review.get("weaknesses", []):
        if not isinstance(weakness, dict) or weakness.get("severity") not in ("major", "minor"):
            problems.append("each weakness needs severity major|minor")
            break
    return problems


def build_review_report(contract: dict, reviews: list[dict]) -> dict:
    gate = contract["review_policy"]["gate"]
    scores = [review["score"] for review in reviews]
    average = round(sum(scores) / len(scores), 2) if scores else 0.0
    majors = [
        {"reviewer": review["reviewer_id"], "text": weakness["text"]}
        for review in reviews
        for weakness in review.get("weaknesses", [])
        if weakness.get("severity") == "major"
    ]
    failures = []
    if average < gate["min_average_score"]:
        failures.append(
            f"average score {average} below gate {gate['min_average_score']}"
        )
    if gate.get("block_on_major_weaknesses") and majors:
        failures.append(f"{len(majors)} major weakness(es) unaddressed")
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "review_passed" if not failures else "revision_required",
        "reviews": reviews,
        "summary": {
            "reviewer_count": len(reviews),
            "average_score": average,
            "scores": scores,
            "major_weaknesses": majors,
            "gate_failures": failures,
        },
        "revision_actions": (
            [
                "Address every major weakness in a writer-subagent revision pass.",
                "Re-run compose, then re-run the review gate with fresh reviewers.",
            ]
            if failures
            else []
        ),
    }


LOOP_SCHEMA_VERSION = "ouroboros.paper-writer.loop-ledger.v0.1"


def build_revision_brief(contract: dict, review_report: dict, gap: dict, round_number: int) -> str:
    unsupported = [
        f"{claim['id']}: {claim['statement']}"
        for claim in gap["claims"]
        if claim["status"] == "unsupported"
    ]
    majors = review_report["summary"]["major_weaknesses"]
    lines = [
        f"# Revision Brief — round {round_number}",
        "",
        f"- Writer model: `{contract['writer_policy']['writer_model']}`",
        f"- Review gate: average >= {contract['review_policy']['gate']['min_average_score']}, zero major weaknesses",
        f"- Previous round average: {review_report['summary']['average_score']}",
        "",
        "## Routing rule (contractual)",
        "",
        "For each major weakness below, decide which kind it is:",
        "- **Writable**: fully addressable with prose plus evidence already in the "
        "research bundle. Address it completely.",
        "- **Evidence-bound**: needs evidence that does not exist yet. Do NOT paper "
        "over it. State it plainly in Discussion and Limitations as an open gap; "
        "it is routed to the experiment loop, not to another rewrite.",
        "",
        "Known evidence-bound anchors (unsupported claims from the gap report):",
        "",
    ]
    lines += [f"- {item}" for item in unsupported] or ["- none"]
    lines += ["", "## Major weaknesses to address", ""]
    for index, major in enumerate(majors, start=1):
        lines.append(f"{index}. ({major['reviewer']}) {major['text']}")
    lines += [
        "",
        "## Constraints (unchanged)",
        "",
        "- Keep every hard rule from the original writing brief: required "
        "sections, verbatim claim ids, [E-...] evidence ids only from the "
        "bundle, [cite:key] placeholders, anonymization, page budget.",
        "- Do not weaken the specified-versus-implemented honesty to chase a "
        "higher score.",
        "",
    ]
    return "\n".join(lines)


def check_figures(contract: dict, draft_text: str) -> tuple[list[str], list[str]]:
    """Return (failures, warnings) for the contract's figure plan."""
    plan = contract.get("figure_plan")
    if not plan:
        return [], []
    failures, warnings = [], []
    for figure in plan.get("figures", []):
        if figure["id"] in draft_text:
            continue
        message = f"figure {figure['id']} ({figure['title']}) not referenced in draft"
        if figure.get("required"):
            failures.append(message)
        else:
            warnings.append(message)
    return failures, warnings


def draft_sections(draft_text: str) -> list[str]:
    return [
        line.strip().lstrip("#").strip()
        for line in draft_text.splitlines()
        if line.strip().startswith("## ")
    ]


def verify_draft(contract: dict, bundle: dict, gap: dict, draft_text: str) -> dict:
    venue = contract["venue"]
    known_ids = {str(item["id"]) for item in bundle.get("evidence", [])}
    present = {section.lower() for section in draft_sections(draft_text)}
    missing_sections = [
        name for name in venue["required_sections"] if name.lower() not in present
    ]
    cited = {match.strip("[]") for match in EVIDENCE_REF.findall(draft_text)}
    unknown_refs = sorted(cited - known_ids)
    missing_claims = [
        claim["id"] for claim in gap["claims"] if str(claim["id"]) not in draft_text
    ]
    word_count = len(draft_text.split())
    estimated_pages = round(word_count / WORDS_PER_PAGE, 1)
    over_budget = estimated_pages > venue["page_limit_main_text"]
    failures = []
    if missing_sections:
        failures.append(f"missing required sections: {', '.join(missing_sections)}")
    if unknown_refs:
        failures.append(f"cites unknown evidence ids: {', '.join(unknown_refs)}")
    if missing_claims:
        failures.append(f"never references claims: {', '.join(missing_claims)}")
    figure_failures, figure_warnings = check_figures(contract, draft_text)
    failures += figure_failures
    return {
        "schema_version": COMPOSE_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": "verified" if not failures else "rejected",
        "failures": failures,
        "warnings": (
            [f"draft is ~{estimated_pages} pages; budget is {venue['page_limit_main_text']}"]
            if over_budget
            else []
        )
        + figure_warnings,
        "metrics": {
            "word_count": word_count,
            "estimated_pages": estimated_pages,
            "evidence_ids_cited": sorted(cited),
            "sections_found": draft_sections(draft_text),
        },
    }


def build_handoff(
    contract: dict,
    gap: dict,
    compose_report: dict,
    *,
    artifact_dir: Path,
    paper_path: Path,
) -> dict:
    unsupported = [
        claim["id"] for claim in gap["claims"] if claim["status"] == "unsupported"
    ]
    next_steps = [
        "convert the verified markdown draft to the official venue LaTeX template",
        "resolve every [cite:key] placeholder into a real, verified bibliography entry",
    ]
    if unsupported:
        next_steps.insert(
            0,
            "run the suggested ooo auto goals for unsupported claims, re-harvest, "
            f"and re-verify: {', '.join(unsupported)}",
        )
    next_steps += [
        "pass the `paper review` gate: fresh reviewer subagents on the contract's "
        "reviewer_model score the draft; revision is required on gate failure",
        "walk the venue readiness checklist item by item against the current CFP",
        "human review: claims, tone, and anonymization before any submission",
    ]
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "plugin": "paper-writer",
        "status": compose_report["status"],
        "repository": contract["repository"],
        "artifact_dir": str(artifact_dir),
        "paper_path": str(paper_path),
        "venue": contract["venue"]["name"],
        "paper_type": contract["paper_type"],
        "writer_model": contract["writer_policy"]["writer_model"],
        "claims": {
            "supported": gap["summary"]["supported"],
            "unsupported": gap["summary"]["unsupported"],
        },
        "verification": {
            "failures": compose_report["failures"],
            "warnings": compose_report["warnings"],
            "metrics": compose_report["metrics"],
        },
        "next_steps": next_steps,
    }


def handoff_markdown(handoff: dict) -> str:
    lines = [
        "# Paper Writer Handoff",
        "",
        f"- Status: `{handoff['status']}`",
        f"- Venue: {handoff['venue']} ({handoff['paper_type']})",
        f"- Draft: `{handoff['paper_path']}`",
        f"- Writer model: `{handoff['writer_model']}`",
        f"- Claims: {handoff['claims']['supported']} supported / "
        f"{handoff['claims']['unsupported']} unsupported",
        "",
        "## Verification",
        "",
    ]
    failures = handoff["verification"]["failures"]
    warnings = handoff["verification"]["warnings"]
    lines += [f"- FAIL: {item}" for item in failures] or ["- all checks passed"]
    lines += [f"- WARN: {item}" for item in warnings]
    lines += ["", "## Next steps", ""]
    lines += [f"- {step}" for step in handoff["next_steps"]]
    lines += ["", "Submission is intentionally never automatic.", ""]
    return "\n".join(lines)
