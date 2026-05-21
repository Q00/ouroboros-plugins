# OpenHands AgentOS Assimilation PR Plan

Source epic: Q00/ouroboros-plugins#42. Related ecosystem boundary: Q00/ouroboros-plugins#27.

The implementation should be reviewed as **4 PRs**. Together they preserve the OpenHands UX while keeping OpenHands outside Ouroboros core and inside an audited UserLevel plugin boundary.

## PR 1 — Design and contract foundation

Scope: add the plugin manifest, README/product boundary, catalog/top-level README registration, and this PR sequence. No OpenHands invocation or dependency on SDK internals. Merge condition: manifest validation passes and the repo explains why OpenHands integration belongs in `ouroboros-plugins`, not core.

## PR 2 — Read-only `inspect`

Scope: implement CLI readiness inspection, version/help capability detection for `--headless`, `--json`, `--task`, `--file`, and `--resume`, native config file presence reporting without reading secrets, isolated-config default, sandbox recommendation, and headless/process-sandbox risk warnings. Non-scope: task execution and writes outside test temp dirs.

## PR 3 — Bounded JSONL `run`

Scope: implement a trust-gated wrapper around `openhands --headless --json`; require explicit bounded workspace; reject escaping output/task-file paths; default to isolated config/cache/home under `.omx/artifacts/openhands/<run>`; prefer Docker sandbox; capture JSONL/stdout/stderr/metadata/audit; redact command/env provenance; preserve OpenHands exit codes and failed/completed state. Non-scope: mutation of `ooo auto` or interpretation of OpenHands internals beyond JSONL summaries.

## PR 4 — Handoff, summarize, AgentOS loop, final quality gate

Scope: implement `summarize`, `handoff`, and `agentos` run+handoff wrapper; document examples; leave SDK expansion as future phase 5; run final verification, changed-file cleanup, and code-review gate. Merge condition: after PRs 1-4 merge, issue #42 phases 0-4 are complete.

## Epic completion checklist

- [x] Plugin is installable by manifest contract.
- [x] OpenHands CLI can be inspected read-only.
- [x] Headless JSON runs are gated by explicit shell trust and bounded workspace.
- [x] Run output becomes durable Ouroboros artifacts.
- [x] Handoff artifacts can be reviewed or passed into later Ouroboros workflows.
- [x] OpenHands-specific behavior remains in this plugin, not in core.
- [ ] Phase 5 SDK-backed orchestration remains documented future work.
