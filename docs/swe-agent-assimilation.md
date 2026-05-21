# SWE-agent AgentOS Assimilation RFC

Status: implementation slice for Q00/ouroboros-plugins#43, grounded in the plugin-contract thesis from Q00/ouroboros-plugins#27.

## Decision

`plugins/swe-agent-harness` assimilates `SWE-agent/SWE-agent` as an external autonomous software-engineering harness. It preserves the upstream `sweagent` mental model while adding AgentOS authority, artifact, provenance, audit, and handoff semantics around the run.

This is not a core vendoring effort and not a marketplace listing. SWE-agent stays an external executable or local checkout. The plugin is the AgentOS boundary adapter.

## PR split and scope

The epic should land as **5 PRs**. Each PR is independently reviewable and maps to a durable implementation slice.

### PR 1 — Design/RFC and PR scope contract

Scope:

- Add this RFC and an explicit issue #43 acceptance mapping.
- Define UX parity with upstream `sweagent` commands.
- Define the adapter-vs-vendoring boundary.
- Define artifact bundle layout, command risk tiers, permission model, failure semantics, and schema-pressure follow-ups.
- Link the plugin to #27 as a reference external-agent assimilation case.

Out of scope:

- Runtime execution.
- Manifest schema expansion.

### PR 2 — Plugin skeleton, manifest, and operator docs

Scope:

- Add `plugins/swe-agent-harness/ouroboros.plugin.json` against schema v0.1.
- Add Python package entrypoint `python -m swe_agent_harness`.
- Add plugin README with command parity, capabilities, permissions, risk tiers, trust expectations, and non-goals.
- Add catalog entry and top-level README references.

Out of scope:

- Host patch application.
- GitHub branch push or PR creation.
- Vendoring SWE-agent.

### PR 3 — Artifact discovery and AgentOS handoff conversion

Scope:

- Implement artifact discovery for `.traj`, `.pred`, `.patch`, `.diff`, logs, and configs.
- Implement `collect-artifacts`, `handoff`, and `verify-artifacts`.
- Emit `run-spec.json`, `provenance.json`, `audit-summary.json`, `handoff.json`, and `handoff.md`.
- Preserve upstream output directories and normalize selected patch/prediction/trajectory pointers.
- Add fixture tests that require no upstream SWE-agent installation.

Out of scope:

- Running SWE-agent.
- Opening PRs or applying patches.

### PR 4 — Bounded SWE-agent pass-through runner and permission semantics

Scope:

- Implement `run` and `run-replay` pass-through to the upstream `sweagent` executable.
- Preserve dotted override args and upstream command shape.
- Add namespaced `--agentos-*` flags for artifact dir, run id, dry-run, executable path, and explicit trust acknowledgements.
- Inject a bounded upstream output directory when none is supplied.
- Capture stdout/stderr.
- Produce blocked semantics when shell/runtime trust is missing, upstream executable is missing, or args request host patch/PR mutation without explicit trust.

Out of scope:

- Schema changes for command-level permissions; document the pressure instead.

### PR 5 — Read-only tooling, tests, and final quality gate

Scope:

- Implement `inspect` and `quick-stats` over existing SWE-agent artifacts as read-only commands.
- Add smoke tests for manifest validation, artifact conversion, blocked permissions, dry-run metadata, and read-only summaries.
- Run contract validation and tests.
- Run cleanup and review gates before final completion.

Out of scope:

- `run-batch`, `apply-patch`, `open-pr`, and offensive/security modes. These need follow-up trust and policy design.

## Command parity target

| Upstream | AgentOS-native target | Initial status |
|---|---|---|
| `sweagent run ...` | `ooo swe-agent run ...` | implemented as bounded pass-through |
| `sweagent run-replay ...` | `ooo swe-agent run-replay ...` | implemented as bounded pass-through |
| `sweagent inspect ...` | `ooo swe-agent inspect ...` | implemented as read-only summary |
| `sweagent quick-stats ...` | `ooo swe-agent quick-stats ...` | implemented as read-only summary |
| existing output collection | `ooo swe-agent collect-artifacts ...` | AgentOS-native helper |
| handoff regeneration | `ooo swe-agent handoff ...` | AgentOS-native helper |
| artifact validation | `ooo swe-agent verify-artifacts ...` | AgentOS-native helper |
| `sweagent run-batch ...` | `ooo swe-agent run-batch ...` | deferred |
| patch application | `ooo swe-agent apply-patch ...` | deferred explicit trust path |
| PR creation | `ooo swe-agent open-pr ...` | deferred destructive trust path |

## Artifact bundle contract

Every AgentOS-managed run or collection writes a bundle under `.agentos/swe-agent/<run-id>/` unless overridden:

```text
run-spec.json
upstream-command.txt
stdout.log
stderr.log
swe-agent-output/
patch.diff
prediction.pred
trajectory.traj
audit-summary.json
provenance.json
handoff.json
handoff.md
```

The plugin preserves upstream artifacts first, then adds AgentOS metadata. It does not overwrite upstream trajectory formats or force users out of existing SWE-agent inspection/replay workflows.

## Permissions and risk tiers

- `inspect`, `quick-stats`, `verify-artifacts`: `read_only`.
- `collect-artifacts`, `handoff`: `write` because they create local AgentOS metadata.
- `run`, `run-replay`: `write` and confirmation-required because they invoke shell/runtime authority and may call model/network providers depending on config.
- PR creation and host patch application: deferred and must remain separately trusted.

The manifest declares plugin-level permissions because schema v0.1 has no command-level permission matrix. Command-level permission declarations are a documented schema-pressure point, not a speculative schema expansion.

## Failure semantics

The adapter distinguishes:

- `blocked`: trust, executable, or policy checks prevented invocation.
- `failed`: adapter or upstream execution failed.
- `completed`: run finished without necessarily submitting a patch.
- `submitted`: a patch/diff artifact exists.
- `partial`: metadata/artifacts exist but completion is uncertain.
- `cancelled`: reserved for runtime cancellation.

Blocked trust denials emit `plugin.failed` audit summaries with `status=blocked`.

## Schema pressure follow-ups

Do not expand v0.1 manifest for this plugin. Open follow-up issues when needed for:

1. Command-level permissions and risk details.
2. Artifact type declarations.
3. Secret/environment declarations without secret values.
4. Network endpoint categories/allowlists.
5. Long-running progress/resume fields.

## Acceptance mapping

Issue #43 is complete when the five PR scopes above are merged. Together they provide the design, manifest, docs, bounded runner, artifact conversion, permission semantics, read-only tooling, and smoke tests required for SWE-agent to be recognizable as SWE-agent while governed by AgentOS plugin contracts.
