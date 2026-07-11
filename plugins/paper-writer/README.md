# paper-writer

Turn Ouroboros run evidence into a venue-ready paper draft. The plugin owns the
paper domain contract (thesis, venue rules, claims, evidence sufficiency); the
host agent owns prose (via a dedicated writer subagent) and any additional
experiment runs (via `ooo auto`). Ouroboros core stays domain-agnostic.

## Pipeline

```text
paper inspect   -> which evidence sources exist in the target repository
paper prepare   -> plugin-owned paper_contract.json (thesis, venue, claims,
                   review/figure/web-research/revision-loop policies)
paper harvest   -> research_bundle.json (spec/RFD/domain-pack/adapter/
                   conformance/test/experiment evidence with stable E-* ids)
paper gap       -> gap_report.json (claim vs evidence; unsupported claims get
                   bounded ooo auto goals or a downgrade-to-position action)
paper brief     -> writing_brief.md (task for the writer subagent)
[host agent]    -> spawn writer subagent on contract writer_model, get draft
paper compose   -> verify draft (sections, claim refs, evidence citations,
                   figure plan), write paper.md + handoff.json/.md
paper review    -> reviewer briefs for FRESH subagents; --ingest enforces the
                   gate (min average score, zero major weaknesses)
paper revise    -> loop step: record round in loop_ledger.json, archive
                   reviews, emit revision brief with evidence-bound routing
                   (stops on gate pass, round budget, or stagnation)
paper latex     -> paper.tex + references.bib for a local LaTeX build
```

The loop "run until the result is good" is contractual, not ad-hoc: rounds
repeat write -> compose -> fresh review until the gate passes, and major
weaknesses that need new evidence are routed to the experiment loop
(`additional_experiment_policy`) instead of being papered over with prose.

All artifacts live under `.ouroboros/paper-writer/` in the target repository.

## Boundary

- The plugin is deterministic: it never generates prose and never runs
  experiments. `writer_policy.writer_model` (default `claude-opus-4-8`) tells
  the host which model must write; `additional_experiment_policy` tells the
  host how to close evidence gaps through `ouroboros_start_auto`.
- `compose` is the anti-fabrication gate: a draft is rejected if it misses
  required sections, cites evidence ids that are not in the bundle, or never
  references a contracted claim. Numbers must carry `[E-...]` evidence ids.
- Submission is never automatic; `handoff.md` lists the human steps left.

## Interview

Question set for scoping a paper before `prepare`:
`assets/interview/paper-scope.md`. Venue rules and the ICLR readiness
checklist: `assets/venue/iclr-readiness.md` (every item must be re-checked
against the current year's CFP).

## Local run

```bash
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer inspect /path/to/repo
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer prepare /path/to/repo \
  --thesis "..." --venue iclr --paper-type position --claims-file claims.json
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer harvest /path/to/repo \
  --test-log /tmp/pytest.log
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer gap /path/to/repo
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer brief /path/to/repo
PYTHONPATH=plugins/paper-writer python3 -m ouroboros_paper_writer compose /path/to/repo \
  --draft /tmp/draft.md
```

Exit codes: `gap` returns 1 while evidence gaps remain; `compose` returns 1
when the draft fails verification. Both are intended as loop conditions for
the host agent (run more experiments / rewrite, then retry).
