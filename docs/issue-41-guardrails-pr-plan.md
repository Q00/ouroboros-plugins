# Issue #41 Guardrails AgentOS Assimilation PR Plan

Source epic: [Q00/ouroboros-plugins#41](https://github.com/Q00/ouroboros-plugins/issues/41)

## Target outcome

Assimilate Guardrails AI as an Ouroboros-native `guardrails-eval` plugin that
preserves the Guardrails mental model (`Guard`, validators, specs,
`ValidationOutcome`) while projecting every invocation into the Ouroboros plugin
contract: declared commands, bounded permissions, audit/provenance-compatible
payloads, durable reports, state references, and handoff artifacts.

## PR count and merge order

The epic should be implemented as **4 PRs**. This keeps review boundaries small
while ensuring the last PR leaves the epic merge-complete.

### PR1 — Contract and boundary plan

Scope:

- Confirm the MVP fits manifest schema `0.1`; no schema expansion is required.
- Capture Guardrails-specific command semantics and non-goals.
- Define normalized report and handoff shapes.
- Define permission/risk split for local validation versus future Hub/server
  lifecycle commands.
- Resolve MVP open questions so implementation does not drift during later PRs.

Decisions:

- MVP supports local post-process validation of known output. It does not call
  remote LLMs, install Hub validators, start Guardrails server mode, or expose
  arbitrary Guardrails CLI passthrough.
- MVP plugin name is `guardrails-eval`; command namespace is `guardrails`.
- MVP spec loading supports RAIL specs via `Guard.for_rail(...)` and JSON guard
  dictionaries via `Guard.from_dict(...)` when `guardrails-ai` is installed.
  Python config execution is not in MVP because executing repo code would exceed
  the local validation trust boundary.
- Validation failure exits non-zero by default for gate usage, with an explicit
  opt-out flag for report-only inspection.
- Reports may include validated output, but raw target text is represented by
  bounded references and hashes by default to avoid persisting unbounded prompts
  or secrets in provenance.

Acceptance evidence:

- This document exists and the plugin implementation below follows it.

### PR2 — MVP plugin skeleton and `validate-output`

Scope:

- Add `plugins/guardrails-eval/ouroboros.plugin.json`.
- Add `plugins/guardrails-eval/guardrails_eval/` Python entrypoint package.
- Implement `validate-output` with `--spec`, `--output` or `--text`, optional
  `--metadata`, `--report`, `--handoff`, and validation-failure exit semantics.
- Implement repo-relative path validation for repository-scoped paths.
- Implement a Guardrails adapter that returns a clean missing-dependency error
  when `guardrails-ai` is unavailable.
- Emit normalized JSON report plus concise stdout summary.

Out of scope:

- Hub validator install lifecycle.
- Server mode.
- Python config execution.

### PR3 — Ouroboros evidence commands

Scope:

- Add `validate-artifact` as a first-class artifact-gate command, sharing the
  validation core with `validate-output` but projecting the target as an
  Ouroboros artifact.
- Add handoff artifact emission with stable consumer hints for future `ooo auto`,
  workflow IR, and acceptance gates.
- Add provenance/ledger/state-compatible event payloads to the report without
  mutating core state directly.
- Add `summarize-report` as a read-only report summarizer.
- Bound metadata and payload persistence with redaction/hashing rules.

Out of scope:

- Writing directly to an Ouroboros ledger or state store. The plugin emits
  compatible evidence payloads; the command dispatcher/runtime owns persistence.

### PR4 — Contract validation, tests, docs, catalog

Scope:

- Add manifest validation coverage through existing contract validator.
- Add plugin tests for passing/failing validation via a fake Guardrails module,
  missing dependency errors, unsupported spec types, path bounding, report shape,
  handoff shape, `validate-artifact`, and `summarize-report`.
- Add plugin README with direct Python usage and intended `ooo guardrails ...`
  command usage.
- Register the plugin in `catalog/index.json`.
- Run repository verification.

## Epic completion condition

After all 4 PRs merge, issue #41's MVP acceptance criteria are met:

- Guardrails concepts are preserved through command names, spec terminology, and
  normalized `ValidationOutcome` fields.
- Guardrails outcomes are consumable as Ouroboros report/handoff evidence.
- Local validation is bounded to filesystem read/write permissions.
- No arbitrary passthrough, Hub install, server mode, or manifest schema
  expansion is included in MVP.
- Future Hub/server work remains explicitly separated into later lifecycle PRs.
