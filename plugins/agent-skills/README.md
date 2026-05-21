# agent-skills

AgentOS/Ouroboros assimilation adapter for
[`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills).

The assimilation target is the upstream `agent-skills` repository. This plugin
is the adapter substrate that makes those workflows discoverable,
permissioned, auditable, provenance-tracked, handoff-capable, and composable
with Ouroboros Seed / Ledger / State / Provenance / Handoff primitives.

This plugin follows the #27 capability-assimilation contract: it is a curated
reference adapter that proves an external skill pack can become Ouroboros-native
without turning this repository into a marketplace, adding domain-specific
branches to core, or exposing a generic unbounded subprocess wrapper.

## Commands

Lifecycle aliases preserve the upstream command muscle memory:

```bash
ooo agent-skills spec --scope "Build a plugin adapter for external skill packs"
ooo agent-skills plan --scope docs/spec.md
ooo agent-skills build --scope docs/plan.md
ooo agent-skills test --verification-command "pytest"
ooo agent-skills review --scope HEAD
ooo agent-skills code-simplify --scope plugins/agent-skills
ooo agent-skills ship --scope release-candidate
```

Every upstream skill is also exposed directly, for example:

```bash
ooo agent-skills code-review-and-quality --scope HEAD
ooo agent-skills security-and-hardening --scope plugins/agent-skills
ooo agent-skills browser-testing-with-devtools --scope http://localhost:3000
ooo agent-skills source-driven-development --scope "upgrade API usage"
```

The local entrypoint used by tests and plugin dispatchers is:

```bash
PYTHONPATH=plugins/agent-skills python -m agent_skills_adapter --list-skills
PYTHONPATH=plugins/agent-skills python -m agent_skills_adapter review --scope HEAD
```

## Output artifacts

By default, each invocation writes a structured handoff under:

```text
.omx/handoffs/agent-skills/<command>/<run-id>.md
.omx/handoffs/agent-skills/<command>/<run-id>.json
.omx/handoffs/agent-skills/<command>/<run-id>.audit.json
```

These artifacts include:

- plugin name and version,
- upstream repository URL,
- upstream commit and skill path,
- command invoked and arguments/scope,
- permissions and capabilities used,
- risk classification and execution mode,
- evidence and verification command records,
- blocked authority conditions,
- recommended next action,
- `ooo auto` handoff readiness.

## Permission model

Required baseline permissions:

- `filesystem:read` — inspect repository files, diffs, docs, and tests.
- `filesystem:write` — write handoff, provenance, audit-compatible, spec, plan,
  ADR, and verification artifacts.

Optional permissions are never implied:

- `shell:execute` — record trusted test/build/lint execution authority.
- `network:read` — record trusted documentation or upstream source lookup.
- `browser:devtools` — record trusted browser automation authority.

The adapter does not deploy, push, merge, delete resources, or mutate external
systems by default. Guarded edit and browser workflows produce handoffs unless
the caller has already granted the necessary authority through the plugin trust
layer. Capabilities describe Ouroboros substrate access; permissions describe
external authority. Keeping those separate is required by the #27 contract.

## Why this is not a prompt-pack wrapper

A trivial wrapper would load upstream Markdown and tell the model to follow it.
This adapter instead maps upstream capabilities into the current Ouroboros
contract: manifest commands, risk tiers, bounded permissions, core capabilities,
structured handoffs, upstream provenance, and audit-compatible events. The full
upstream prompt pack remains upstream; this repository records enough metadata
to make execution native to AgentOS/Ouroboros without hiding where the workflow
came from.

## Install and trust

From this repository root:

```bash
ouroboros plugin add . --plugin agent-skills
ouroboros plugin trust agent-skills --scope filesystem:read --scope filesystem:write
```

Grant optional scopes only for workflows that actually need them:

```bash
ouroboros plugin trust agent-skills --scope shell:execute
ouroboros plugin trust agent-skills --scope network:read
ouroboros plugin trust agent-skills --scope browser:devtools
```
