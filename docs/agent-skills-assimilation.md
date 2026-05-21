# Agent Skills Assimilation Plan

This document scopes the implementation for
[Q00/ouroboros-plugins#34](https://github.com/Q00/ouroboros-plugins/issues/34):
assimilating `addyosmani/agent-skills` into the AgentOS/Ouroboros plugin
contract.

## PR breakdown

The epic should land as five reviewable PRs. The implementation in this branch
contains all five scopes so they can be split into stacked PRs or merged as a
single integration if maintainers prefer.

1. **PR 1 — contract mapping and MVP skeleton**
   - Add this design document and `plugins/agent-skills/`.
   - Add a schema-valid `ouroboros.plugin.json`.
   - Lock upstream provenance: repository, observed commit
     `f17c6e88c904dc747381c374312c2d58e10647ae`, upstream plugin version, and
     license treatment.
   - Add lifecycle MVP commands: `spec`, `plan`, `review`, `ship`, and
     `using-agent-skills`.

2. **PR 2 — complete command inventory**
   - Expose all seven upstream lifecycle aliases: `spec`, `plan`, `build`,
     `test`, `review`, `code-simplify`, and `ship`.
   - Expose all 23 upstream `skills/*/SKILL.md` directories as direct commands
     under the canonical `agent-skills` namespace.
   - Keep command names predictable from upstream skill names.

3. **PR 3 — handoff, provenance, and audit-compatible artifacts**
   - Implement `python -m agent_skills_adapter` dispatch.
   - Generate `.omx/handoffs/agent-skills/<command>/<run-id>.md` and `.json`.
   - Generate an audit-event-shaped `.audit.json` beside each handoff.
   - Record arguments, scope, permissions used, capabilities used, upstream
     skill path, upstream commit, and suitability for `ooo auto` handoff.

4. **PR 4 — command behavior and permission gates**
   - Distinguish report, artifact-write, guarded-edit, and ship fan-out modes.
   - Record optional `shell:execute`, `network:read`, and `browser:devtools`
     authority only when explicit CLI flags are supplied by a trusted caller.
   - Do not execute shell commands, drive browsers, push, merge, delete, deploy,
     or mutate external systems by default.
   - Mark browser automation as blocked until `browser:devtools` authority is
     explicitly present.

5. **PR 5 — documentation, examples, and validation**
   - Document install/trust flow, command examples, risk classes, and why this is
     an AgentOS-native assimilation adapter rather than a prompt-pack copy.
   - Update the repository catalog.
   - Add tests for inventory completeness, manifest validation, handoff output,
     audit shape, and guarded browser behavior.

## Scope boundary

The adapter is not a marketplace listing and does not vendor the full upstream
prompt pack. It translates the upstream command surface into the Ouroboros
contract: declared commands, bounded permissions, core capabilities, structured
handoffs, provenance, and audit-compatible events. Runtime execution is handed
off to `ooo auto` or future Workflow IR/run-step consumers where trust grants
and project-specific verification can be enforced.

## Canonical command namespace

The namespace is `agent-skills`. It names the upstream repository being
assimilated and avoids hiding provenance behind a generic alias. Future aliases
can be considered after this base namespace is proven.

## Handoff contract

Each invocation writes:

```text
.omx/handoffs/agent-skills/<command>/<run-id>.md
.omx/handoffs/agent-skills/<command>/<run-id>.json
.omx/handoffs/agent-skills/<command>/<run-id>.audit.json
```

The JSON payload includes plugin identity, upstream repository/commit/path,
command arguments, risk/mode, permissions used, capabilities used, evidence,
verification commands, blocked authority, recommended next action, and whether
it is suitable for `ooo auto` handoff.
