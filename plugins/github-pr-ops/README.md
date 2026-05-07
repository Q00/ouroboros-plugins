# github-pr-ops

Reference skeleton for a UserLevel GitHub PR operations plugin.

This plugin is intentionally a skeleton. It demonstrates the boundary that
#689-style behavior should use instead of entering core `ooo auto`.

## Product Boundary

This plugin may eventually support workflows such as:

- Review a pull request
- Summarize merge readiness
- Apply team-specific merge policy
- Prepare a merge decision

It should use Ouroboros core primitives for:

- State
- Ledger
- Provenance
- Safety boundaries
- Execution handoff
- Audit

It should not require `ooo auto` to understand GitHub PR operations directly.
