# Issue 46 PR Plan: Langfuse as an Ouroboros AgentOS Plugin

Source epic: <https://github.com/Q00/ouroboros-plugins/issues/46>

## Decision: 4 PRs

The epic should be delivered as **4 reviewable PRs**. The scopes are cumulative and merge-safe; after PR 4 lands, issue 46's Phase 1 definition of done is satisfied.

### PR 1 — Contract, docs, and plugin skeleton

**Purpose:** establish the Langfuse boundary as a first-class Ouroboros UserLevel program without implementing network writes.

**Scope:**
- `plugins/langfuse-observability/ouroboros.plugin.json`
- README with goals, non-goals, configuration, command UX, and safety model.
- Python package entrypoint and empty command dispatch.
- Catalog entry.
- Contract validation coverage.

**Done when:** manifest validates, command namespace is `langfuse`, `score` is declared `write` with confirmation, and no destructive/self-host/prompt/dataset behavior is included.

### PR 2 — `inspect` evidence import loop

**Purpose:** make Langfuse traces consumable as redacted Ouroboros handoff/provenance artifacts.

**Scope:**
- Trace URL/ID parsing.
- Offline fixture mode for tests and demos.
- Authenticated read path against Langfuse Public API.
- Secret/large-payload redaction.
- JSON and Markdown artifacts under `.omx/handoffs/langfuse/`.
- Tests for parsing, redaction, artifact generation, fixtures, and missing credentials.

**Done when:** `ooo langfuse inspect <trace-url-or-id>` can produce stable JSON/Markdown handoff artifacts from fixture data or authenticated Langfuse reads without requiring `network:write`.

### PR 3 — `score` dry-run and confirmed publish loop

**Purpose:** close the evidence loop by projecting Ouroboros evaluator results back to Langfuse scores while preserving local provenance.

**Scope:**
- Read local Ouroboros handoff artifact.
- Extract trace/observation context or accept explicit flags.
- Required `--name` and `--value`.
- `--dry-run` payload generation with no network write.
- Real POST to Langfuse scores behind explicit `--confirm`.
- Structured success/failure result artifacts under `.omx/handoffs/langfuse/`.
- Tests for dry-run, confirmation boundary, missing credentials, and secret redaction.

**Done when:** dry-run proves the exact publish payload and real writes are impossible without both credentials and explicit confirmation.

### PR 4 — Final integration hardening and acceptance verification

**Purpose:** make the plugin ready to merge as the epic-resolving Phase 1 bridge.

**Scope:**
- End-to-end docs and examples.
- AgentOS audit/provenance fields in artifacts.
- Validator and test-suite updates.
- Final cleanup/review fixes.

**Done when:** `python3 scripts/validate_contract.py`, focused CLI smoke tests, and `pytest` pass; artifacts are sufficient for downstream handoff, audit, and resume/review flows.

## Deferred follow-up PR families

These remain out of scope for issue 46 Phase 1 and should become new epics/issues: `langfuse-prompts`, `langfuse-datasets-evals`, and `langfuse-selfhost`.
