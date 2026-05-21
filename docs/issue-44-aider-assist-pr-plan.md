# Issue #44 Aider Assist PR Plan

Source: [Q00/ouroboros-plugins#44](https://github.com/Q00/ouroboros-plugins/issues/44)

## Decision: four stacked PRs

Issue #44 is large enough to need **4 stacked PRs**. A single PR would mix the
contract decision, write authority, verification loops, and architect/session
UX. More than four PRs would create ceremony without a cleaner merge boundary.

The stack is based on `origin/main`; each later PR branches from the previous
one so reviewers can merge in order.

### PR1 — Contract, manifest, skeleton, read-only `ask`

Scope:

- Add `plugins/aider-assist/` as the reference plugin package.
- Add a schema-valid `ouroboros.plugin.json` declaring `aider ask`, `edit`,
  `fix`, and `architect` command surfaces with conservative risks.
- Document the AgentOS capability-assimilation boundary and relationship to
  issue #27.
- Implement the Python CLI skeleton and the read-only `ask` command.
- Resolve Aider through the public CLI (`aider` on `PATH` or
  `AIDER_ASSIST_AIDER_BIN`) rather than importing Aider internals.
- Emit `.omx/artifacts/plugins/aider-assist/<run-id>/` artifacts including
  invocation, stdout/stderr, answer, and handoff.
- Add tests for manifest validity and fake-Aider ask artifact creation.

Out of scope:

- Write-capable edits.
- Verification repair loops.
- Interactive passthrough.

### PR2 — Bounded `edit`

Scope:

- Implement `ooo aider edit` / `python -m aider_assist edit` with an explicit
  editable `--file` allowlist.
- Refuse edit runs with no editable files.
- Capture pre/post git state, diff, and touched files.
- Default Aider auto-commit off so Ouroboros owns provenance.
- Emit structured handoff evidence and tests.

Out of scope:

- Running test/lint commands after edits.
- Architect mode.

### PR3 — Verification and `fix`

Scope:

- Add `--test-cmd` and `--lint-cmd` capture for write-capable runs.
- Implement `fix` as a bounded repair workflow over failing verification
  context.
- Re-run verification after Aider and represent `completed`, `failed`, or
  `blocked` with evidence.
- Add tests for verification capture and failure behavior.

Out of scope:

- Full interactive terminal session support.

### PR4 — `architect`, redaction hardening, final readiness

Scope:

- Implement read-only-by-default `architect` planning artifacts.
- Preserve safe Aider model/provider metadata without writing secrets.
- Harden redaction for artifact/handoff content.
- Update README acceptance checklist and deferred interactive-session plan.
- Run final validation, changed-file cleanup, and code-review gate.

Out of scope:

- `aider session` interactive passthrough. It remains deferred until transcript,
  diff, trust-boundary, and post-session handoff semantics are designed.

## Completion condition

After PR1–PR4 merge, the epic is complete for the v0 AgentOS assimilation
surface: read-only ask, bounded edit, verification-backed fix, and architect
planning all run through the plugin contract with permission declarations,
auditable artifacts, provenance, and handoff semantics.
