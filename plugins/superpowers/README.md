# superpowers

Ouroboros-native adapter for [`obra/superpowers`](https://github.com/obra/superpowers).

This plugin exposes every pinned upstream Superpowers skill as an explicit
`ooo superpowers ...` command while preserving the Ouroboros plugin contract:
manifest validation, scoped capabilities, external permissions, risk
classification, trust boundaries, audit/provenance artifacts, Seed-compatible
handoff, and resumable state.

This is the reference capability-assimilation case from
[issue #28](https://github.com/Q00/ouroboros-plugins/issues/28), related to the
AgentOS direction in [issue #27](https://github.com/Q00/ouroboros-plugins/issues/27).

## Why this is not a thin wrapper

The adapter does not blindly print a `SKILL.md` and ask an agent to follow it.
Every invocation answers:

- which upstream skill was selected,
- which upstream version/commit/license supplied it,
- which Ouroboros command represented it,
- which capabilities and external permissions are required,
- which artifacts were produced,
- which audit events were emitted,
- which verification evidence is required before completion,
- which continuation surface should run next.

## Pinned upstream snapshot

- Repository: `https://github.com/obra/superpowers`
- Version: `v5.1.0`
- Commit: `f2cbfbefebbfef77321e4c9abc9e949826bea9d7`
- License: MIT

Vendored files live under `plugins/superpowers/vendor/superpowers`.

## Commands

Local development:

```bash
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros list
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros inspect brainstorming
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros prepare-handoff brainstorming \
  --goal "Design a React todo app"
PYTHONPATH=plugins/superpowers python3 -m superpowers_ouroboros test-driven-development \
  --goal "Add retry behavior"
```

Manifest-facing examples:

```bash
ooo superpowers list
ooo superpowers inspect brainstorming
ooo superpowers brainstorming --goal "Build a React todo app"
ooo superpowers writing-plans --input docs/specs/todo.md
ooo superpowers test-driven-development --goal "Add retry behavior"
ooo superpowers systematic-debugging --input "Tests are flaky"
ooo superpowers subagent-driven-development --input docs/plans/todo.md
ooo superpowers requesting-code-review --input "main..HEAD"
ooo superpowers verification-before-completion --goal "tests pass"
ooo superpowers finishing-a-development-branch --input "feature/todo"
```

## Artifact layout

Commands write by default to the current working directory:

```text
.omx/superpowers/
  skill-index.json
  runs/<run-id>/
    invocation.json
    provenance.json
    handoff.md
    seed.md
    evidence.json
    audit.jsonl
```

`seed.md` is a Seed-preparation artifact. Downstream `ooo auto`, `$ralph`, or
`$team` execution remains responsible for real implementation and verification.

## Skill coverage

The current pinned snapshot includes:

- `using-superpowers`
- `brainstorming`
- `writing-plans`
- `executing-plans`
- `subagent-driven-development`
- `dispatching-parallel-agents`
- `test-driven-development`
- `systematic-debugging`
- `requesting-code-review`
- `receiving-code-review`
- `verification-before-completion`
- `finishing-a-development-branch`
- `using-git-worktrees`
- `writing-skills`

## Risk policy

Read-only guidance/review gates are `read_only`. Artifact generation, planning,
state writes, and workspace setup are `write`. Destructive behavior is excluded
from v0 execution. `finishing-a-development-branch` prepares options and evidence
only; it does not merge, push, delete, discard, or mutate PRs.
