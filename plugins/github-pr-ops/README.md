# github-pr-ops

Reference skeleton for a UserLevel GitHub PR operations plugin.

This plugin is intentionally a skeleton. It demonstrates the boundary that
#689-style behavior should use instead of entering core `ooo auto`.

## Product Boundary

This plugin currently exposes one command:

- `review` — read-only inspection of a pull request

Eventual workflows (deferred):

- Summarize merge readiness
- Apply team-specific merge policy
- Prepare a merge decision

### Why `merge` is not in v0

The destructive `merge` command is intentionally **not part of v0**. It will
return when the destructive permission trust UX is locked (see
[Q00/ouroboros-plugins#9](https://github.com/Q00/ouroboros-plugins/issues/9)).
v0's purpose is to exercise the contract end-to-end with a read-only path;
declaring `merge` now would ship a command that cannot actually be invoked.

It should use Ouroboros core primitives for:

- State
- Ledger
- Provenance
- Safety boundaries
- Execution handoff
- Audit

It should not require `ooo auto` to understand GitHub PR operations directly.
