"""Plugin-owned paper contract: venue rules, claims, and evidence sufficiency."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_SCHEMA_VERSION = "ouroboros.paper-writer.contract.v0.1"
DEFAULT_VENUE = "iclr"
DEFAULT_PAPER_TYPE = "position"
DEFAULT_PAGE_LIMIT = 9
DEFAULT_WRITER_MODEL = "claude-opus-4-8"
DEFAULT_MAX_ADDITIONAL_RUNS = 3
PAPER_TYPES = ("position", "survey", "systems")

EVIDENCE_KINDS = (
    "doc",
    "spec",
    "rfd",
    "domain_pack",
    "adapter",
    "conformance",
    "test",
    "test_log",
    "experiment",
    "source",
)

REQUIRED_SECTIONS = (
    "Abstract",
    "Introduction",
    "Related Work",
    "Design",
    "Evaluation",
    "Discussion and Limitations",
    "Conclusion",
    "Reproducibility Statement",
)

# Every item must be re-checked against the current year's CFP before submission.
ICLR_READINESS_CHECKLIST = (
    "Use the official ICLR LaTeX template for the target year (iclr<year>.sty).",
    "Keep the main text within the page limit (9 pages historically; confirm on the current CFP); references and appendix are not counted.",
    "Fully anonymize the submission: authors, acknowledgments, repository URLs, and self-identifying citations.",
    "Provide an anonymized artifact link (for example anonymous.4open.science) instead of the public repository.",
    "Include a Reproducibility Statement after the main text.",
    "Include an Ethics Statement if the work warrants one (up to one page, not counted).",
    "Disclose LLM usage according to the current ICLR CFP policy.",
    "Confirm dual-submission policy compliance for any overlapping preprint or workshop version.",
    "Submit through OpenReview; the abstract deadline precedes the full-paper deadline.",
    "Position or survey framing alone is weak for the ICLR main track: anchor the paper on a formal model plus machine-checked evaluation, and identify a workshop fallback.",
)

ICLR_WORKSHOP_READINESS_CHECKLIST = (
    "Pick a concrete workshop whose scope matches the paper (agentic systems, "
    "agent evaluation/reliability, safe deployment) and verify its own CFP.",
    "Respect the workshop's page limit (often shorter than the main track; "
    "confirm per-workshop) and its template requirements.",
    "Check whether the workshop is archival or non-archival — non-archival "
    "keeps a later main-track submission possible under dual-submission rules.",
    "Anonymization per the workshop's review model (many are double-blind).",
    "Disclose LLM usage per the hosting conference's policy.",
    "State clearly what the workshop version claims versus the fuller system "
    "vision, so feedback targets the right scope.",
)

VENUE_RULES = {
    "iclr": {
        "name": "ICLR",
        "review_model": "double_blind_openreview",
        "page_limit_main_text": DEFAULT_PAGE_LIMIT,
        "references_counted": False,
        "appendix_counted": False,
        "required_sections": list(REQUIRED_SECTIONS),
        "readiness_checklist": list(ICLR_READINESS_CHECKLIST),
    },
    "iclr-workshop": {
        "name": "ICLR Workshop (agentic systems / agent evaluation track)",
        "review_model": "workshop_double_blind_openreview",
        "page_limit_main_text": DEFAULT_PAGE_LIMIT,
        "references_counted": False,
        "appendix_counted": False,
        "required_sections": list(REQUIRED_SECTIONS),
        "readiness_checklist": list(ICLR_WORKSHOP_READINESS_CHECKLIST),
    },
}


def default_research_queries(venue_name: str, thesis: str) -> list[str]:
    return [
        f"{venue_name} recent paper trends position papers agent systems",
        f"{venue_name} current call for papers formatting LLM policy",
        f"related work for: {thesis}",
        "agent protocol standardization survey (agent client protocol, MCP, A2A, LSP)",
    ]


def build_web_research_plan(
    *,
    venue_name: str,
    thesis: str,
    extra_queries: list[str] | None = None,
) -> dict[str, object]:
    queries = default_research_queries(venue_name, thesis)
    for query in extra_queries or []:
        if query not in queries:
            queries.append(query)
    return {
        "owner": "host_agent",
        "purpose": (
            "During the interview/auto stage the host agent must run these web "
            "searches and record verified findings; the plugin never accesses "
            "the network."
        ),
        "queries": queries,
        "outputs": {
            "references_path": str(Path(".ouroboros") / "paper-writer" / "references.json"),
            "trends_note_path": str(
                Path(".ouroboros") / "paper-writer" / "web_research" / "venue-trends.md"
            ),
        },
        "rules": [
            "Every [cite:key] in the draft must resolve to a verified entry in "
            "references.json before submission.",
            "Each reference entry must record the source URL it was verified from.",
            "No bibliographic detail may be invented; unverifiable keys stay "
            "explicit placeholders.",
            "Venue-trend findings inform framing only; they never override the "
            "claim-evidence rules in this contract.",
        ],
    }


DEFAULT_REVIEWER_MODEL = "claude-opus-4-8"

REVIEW_PERSONAS = (
    {
        "id": "R1",
        "focus": "technical rigor and evidence validity",
        "instruction": (
            "Attack every claim: does the cited evidence actually support it? "
            "Hunt for overclaims about implementation status and for numbers "
            "without evidence ids."
        ),
    },
    {
        "id": "R2",
        "focus": "novelty and positioning",
        "instruction": (
            "Judge the contribution against existing protocols and frameworks "
            "the paper cites. Is the delta real, or is this engineering "
            "packaging presented as research?"
        ),
    },
    {
        "id": "R3",
        "focus": "clarity, structure, and venue fit",
        "instruction": (
            "Review as a tired area chair: is the argument followable, is the "
            "framing consistent, does this fit the venue's main track, and "
            "what would make you desk-reject it?"
        ),
    },
)

REVIEW_RUBRIC = {
    "output_schema": {
        "reviewer_id": "R1|R2|R3",
        "summary": "3-5 sentence summary in the reviewer's own words",
        "strengths": ["list of concrete strengths"],
        "weaknesses": [{"severity": "major|minor", "text": "concrete weakness"}],
        "questions": ["questions for the authors"],
        "score": "integer 1-10 (venue-style overall rating)",
        "confidence": "integer 1-5",
    },
    "rules": [
        "Verify every evidence id you rely on against the research bundle.",
        "A weakness must be actionable; vague dissatisfaction is not a review.",
        "Do not reward prose quality when evidence discipline fails.",
        "Severity calibration: mark a weakness 'major' only if it would still "
        "block acceptance after a normal camera-ready revision; issues "
        "addressable in revision are 'minor'.",
    ],
}


def build_review_policy(reviewer_model: str) -> dict[str, object]:
    return {
        "delegated_to_host": True,
        "reviewer_model": reviewer_model,
        "independence_rule": (
            "Reviewer subagents must be fresh agents that did not write the "
            "draft; the writer's claim is not confirmation."
        ),
        "personas": [dict(persona) for persona in REVIEW_PERSONAS],
        "rubric": REVIEW_RUBRIC,
        "gate": {
            "min_average_score": 6,
            "block_on_major_weaknesses": True,
            "note": (
                "Failing the gate produces revision actions, not submission; "
                "re-run the writer subagent, then review again."
            ),
        },
    }


DEFAULT_MAX_REVIEW_ROUNDS = 3


def build_revision_loop_policy(max_review_rounds: int) -> dict[str, object]:
    return {
        "owner": "host_agent",
        "purpose": (
            "Iterate write -> compose -> fresh review until the review gate "
            "passes; the plugin tracks rounds and routes non-writable "
            "weaknesses out of the writing loop."
        ),
        "max_review_rounds": max_review_rounds,
        "round_shape": [
            "paper revise (archive round, emit revision brief)",
            "writer subagent applies the revision brief",
            "paper compose (mechanical verification)",
            "paper review + FRESH reviewer subagents + paper review --ingest",
        ],
        "stop_conditions": {
            "gate_passed": "review gate passes; proceed to latex and human review",
            "max_rounds": "round budget exhausted; escalate to a human decision",
            "stagnation": (
                "average score did not improve versus the previous round; "
                "another rewrite is unlikely to converge — escalate"
            ),
            "evidence_bound": (
                "remaining major weaknesses need new evidence, not new prose; "
                "route them to additional_experiment_policy instead of rewriting"
            ),
        },
        "rules": [
            "Reviewers must be fresh agents every round; the writer may persist.",
            "A major weakness that requires missing evidence must never be "
            "papered over with prose; it is acknowledged in Discussion and "
            "Limitations and routed to the experiment loop.",
            "Every round is recorded in loop_ledger.json with scores and "
            "outstanding majors so convergence is auditable.",
        ],
    }


def default_figure_plan() -> dict[str, object]:
    return {
        "rule": (
            "Every figure must be derived from the spec, the research bundle, "
            "or repository facts; invented data plots are forbidden. Charts are "
            "generated by code from the recorded artifacts, never drawn by hand "
            "from remembered numbers."
        ),
        "visualization_emphasis": (
            "A systems paper argues its architecture visually: the system "
            "architecture figure is mandatory, every headline quantitative "
            "result should have a chart, and the draft references each figure "
            "by id (e.g. F1) with a markdown image so the LaTeX build embeds it."
        ),
        "figures": [
            {
                "id": "F1",
                "title": (
                    "System architecture: contract plane above transports "
                    "(ACP/MCP/A2A) and runtimes, with adapters, kernel, "
                    "verifier, and authority gate"
                ),
                "required": True,
                "acceptable_forms": ["image", "tikz"],
            },
            {
                "id": "F2",
                "title": (
                    "Governed run pipeline: Plan, Unit, Claim, Evidence, "
                    "Verdict, Transition"
                ),
                "required": True,
                "acceptable_forms": ["image", "tikz", "verbatim block"],
            },
            {
                "id": "F3",
                "title": "Headline results visualization (studies/comparisons)",
                "required": True,
                "acceptable_forms": ["image"],
            },
        ],
    }


def default_claims(thesis: str) -> list[dict[str, object]]:
    """Generic claim skeleton; callers should override with --claims-file."""
    return [
        {
            "id": "C1",
            "statement": thesis,
            "strength": "position",
            "evidence_required": [{"kind": "spec", "min_count": 1}],
        },
        {
            "id": "C2",
            "statement": (
                "The proposed abstraction generalizes beyond a single domain, "
                "demonstrated by multiple concrete domain packs."
            ),
            "strength": "empirical",
            "evidence_required": [{"kind": "domain_pack", "min_count": 2}],
        },
        {
            "id": "C3",
            "statement": (
                "The proposed contract surface is machine-checkable via an "
                "executable conformance suite."
            ),
            "strength": "empirical",
            "evidence_required": [
                {"kind": "conformance", "min_count": 1},
                {"kind": "test_log", "min_count": 1},
            ],
        },
        {
            "id": "C4",
            "statement": (
                "The design decisions are documented and traceable to recorded "
                "rationale rather than ad-hoc implementation choices."
            ),
            "strength": "empirical",
            "evidence_required": [{"kind": "rfd", "min_count": 1}],
        },
    ]


def load_claims_file(path: Path) -> list[dict[str, object]]:
    claims = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims file must be a non-empty JSON array")
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be a JSON object")
        for field in ("id", "statement", "evidence_required"):
            if field not in claim:
                raise ValueError(f"claim missing required field {field!r}")
        claim_id = str(claim["id"])
        if claim_id in seen:
            raise ValueError(f"duplicate claim id {claim_id!r}")
        seen.add(claim_id)
        for requirement in claim["evidence_required"]:
            kind = requirement.get("kind")
            if kind not in EVIDENCE_KINDS:
                raise ValueError(
                    f"claim {claim_id!r} requires unknown evidence kind {kind!r}; "
                    f"expected one of {sorted(EVIDENCE_KINDS)}"
                )
    return claims


def build_paper_contract(
    *,
    repository: Path,
    thesis: str,
    venue: str = DEFAULT_VENUE,
    paper_type: str = DEFAULT_PAPER_TYPE,
    page_limit: int | None = None,
    writer_model: str = DEFAULT_WRITER_MODEL,
    claims: list[dict[str, object]] | None = None,
    max_additional_runs: int = DEFAULT_MAX_ADDITIONAL_RUNS,
    research_queries: list[str] | None = None,
    reviewer_model: str = DEFAULT_REVIEWER_MODEL,
    max_review_rounds: int = DEFAULT_MAX_REVIEW_ROUNDS,
) -> dict[str, object]:
    if venue not in VENUE_RULES:
        raise ValueError(f"unknown venue {venue!r}; expected one of {sorted(VENUE_RULES)}")
    if paper_type not in PAPER_TYPES:
        raise ValueError(f"unknown paper type {paper_type!r}; expected one of {PAPER_TYPES}")
    rules = dict(VENUE_RULES[venue])
    if page_limit is not None:
        rules["page_limit_main_text"] = page_limit
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(repository),
        "thesis": thesis,
        "paper_type": paper_type,
        "venue": rules,
        "claims": claims if claims is not None else default_claims(thesis),
        "writing_rules": {
            "language": "english",
            "no_fabricated_numbers": (
                "Every quantitative statement must cite a research-bundle evidence "
                "id in the form [E-...]. Numbers without an evidence id are forbidden."
            ),
            "external_citations": (
                "Cite external work with [cite:key] placeholders; never invent "
                "bibliographic details, venues, or years."
            ),
            "unsupported_claims": (
                "Claims the gap report marks unsupported may only appear as "
                "positions or future work inside Discussion and Limitations."
            ),
            "anonymization": (
                "Do not name authors, organizations, or public repository URLs "
                "in the draft body."
            ),
        },
        "writer_policy": {
            "delegated_to_host": True,
            "writer_model": writer_model,
            "note": (
                "The plugin never generates prose. The host agent must spawn a "
                "subagent on writer_model with the generated writing brief."
            ),
        },
        "review_policy": build_review_policy(reviewer_model),
        "revision_loop_policy": build_revision_loop_policy(max_review_rounds),
        "figure_plan": default_figure_plan(),
        "web_research_plan": build_web_research_plan(
            venue_name=rules["name"],
            thesis=thesis,
            extra_queries=research_queries,
        ),
        "additional_experiment_policy": {
            "max_additional_runs": max_additional_runs,
            "entrypoint": "ouroboros_start_auto",
            "note": (
                "When the gap report marks a claim unsupported, run the suggested "
                "bounded ooo auto goal, re-harvest, and re-run gap before writing."
            ),
        },
    }
