# Agent Skills Assimilation Plan

This document scopes the implementation for
[Q00/ouroboros-plugins#34](https://github.com/Q00/ouroboros-plugins/issues/34):
assimilating `addyosmani/agent-skills` into the AgentOS/Ouroboros plugin
contract.

It is intentionally aligned with
[Q00/ouroboros-plugins#27](https://github.com/Q00/ouroboros-plugins/issues/27):
`Q00/ouroboros-plugins` is a curated contract/reference repository, not a
marketplace; plugins are not unbounded command wrappers; and external
capabilities become Ouroboros-native only when they are translated into explicit
commands, permissions, capabilities, provenance, audit evidence, and handoff
artifacts.

## PR breakdown

The epic should land as five reviewable stacked PRs. Each PR has a narrow merge
unit and proves one part of the AgentOS capability-assimilation boundary.

1. **PR 1 — contract mapping and stack scope**
   - Add this design document.
   - Lock the five-PR implementation plan before code lands.
   - Record the #27 alignment rules that later PRs must preserve.

2. **PR 2 — manifest and complete command inventory**
   - Add `plugins/agent-skills/` with a schema-valid
     `ouroboros.plugin.json`.
   - Lock upstream provenance: repository, observed commit
     `f17c6e88c904dc747381c374312c2d58e10647ae`, upstream plugin version, and
     license treatment.
   - Expose all seven upstream lifecycle aliases: `spec`, `plan`, `build`,
     `test`, `review`, `code-simplify`, and `ship`.
   - Expose all 23 upstream `skills/*/SKILL.md` directories as direct commands
     under the canonical `agent-skills` namespace.
   - Keep command names predictable from upstream skill names.

3. **PR 3 — handoff, provenance, and audit-compatible runtime**
   - Implement `python -m agent_skills_adapter` dispatch.
   - Generate `.omx/handoffs/agent-skills/<command>/<run-id>.md` and `.json`.
   - Generate an audit-event-shaped `.audit.json` beside each handoff.
   - Record arguments, scope, permissions used, capabilities used, upstream
     skill path, upstream commit, and suitability for `ooo auto` handoff.

4. **PR 4 — command behavior, permission gates, and regression tests**
   - Distinguish report, artifact-write, guarded-edit, and ship fan-out modes.
   - Record optional `shell:execute`, `network:read`, and `browser:devtools`
     authority only when explicit CLI flags are supplied by a trusted caller.
   - Do not execute shell commands, drive browsers, push, merge, delete, deploy,
     or mutate external systems by default.
   - Mark browser automation as blocked until `browser:devtools` authority is
     explicitly present.
   - Add tests for inventory completeness, manifest validation, handoff output,
     audit shape, guarded browser behavior, and ship fan-out metadata.

5. **PR 5 — catalog publication and final validation**
   - Update the repository catalog only after the plugin exists and is tested.
   - Run full repository validation for the completed stack.

## #27 alignment checklist

Each PR must preserve these contract rules:

- **Core stays small.** The adapter prepares handoffs for `ooo auto` and future
  Workflow IR consumers; it does not add agent-skills-specific branching to
  Ouroboros core.
- **This repository remains a contract/reference repository.** The adapter is
  included because it proves external skill-pack assimilation, not because this
  repository is becoming a general marketplace.
- **The plugin is not a trivial wrapper.** It declares a command surface, risk
  classes, bounded permissions, core capabilities, provenance, audit-compatible
  events, and structured handoff artifacts.
- **Capabilities and permissions stay distinct.** Core access such as Seed,
  Ledger, State, Provenance, Handoff, Runtime, MCP, and Progress is declared
  separately from external authority such as filesystem, shell, network, and
  browser/devtools access.
- **Install does not imply trust.** Optional shell, network, and browser/devtools
  authority must remain explicit and guarded.
- **No destructive defaults.** Push, merge, delete, deploy, and external system
  mutation are excluded from the default command surface.
- **Audit/provenance/handoff are mandatory evidence.** Every invocation should
  produce bounded evidence explaining what was invoked, which upstream source it
  came from, which authority was used or blocked, and what downstream action is
  safe.

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
