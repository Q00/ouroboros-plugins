# target-capabilities

Reference package for assimilating an **external target repository** into the
Ouroboros AgentOS plugin ecosystem.

This package is intentionally generic. It proves the contract surface for issue
#29: command-level risk, exact permissions, bounded artifacts, provenance,
handoffs, fail-closed dependency detection, and destructive-operation gating.
It is not a marketplace mirror and it does not vendor an external project.

## Commands

```bash
PYTHONPATH=plugins/target-capabilities python3 -m target_capabilities list-commands
PYTHONPATH=plugins/target-capabilities python3 -m target_capabilities doctor --target-root /path/to/target
PYTHONPATH=plugins/target-capabilities python3 -m target_capabilities inspect --target-root /path/to/target --target-repository owner/repo
PYTHONPATH=plugins/target-capabilities python3 -m target_capabilities plan --target-root /path/to/target --target-repository owner/repo
PYTHONPATH=plugins/target-capabilities python3 -m target_capabilities publish --target-root /path/to/target
```

`--target-root` can also be supplied as `TARGET_CAPABILITIES_ROOT`.

## Artifact contract

Each command writes:

```text
.ouroboros/artifacts/target-capabilities/<command>/<run-id>/
  result.json
  report.md
  stdout.txt
  stderr.txt
  provenance.json
  handoff.json
.ouroboros/handoffs/target-capabilities/<command>/<run-id>.json
```

The JSON printed to stdout is the same structured result recorded in
`result.json`. Handoffs point to bounded artifact paths so `ooo auto` or another
harness can continue without embedding unbounded target-repository content.

## Trust boundary

- Inspection commands only read target metadata, but they are declared `write` risk because this reference package writes bounded local artifacts and handoffs.
- `plan` writes a generated `assimilation-plan.md` artifact inside the run
  directory.
- `publish` is a destructive reference command. It always returns `blocked` in
  this v0 package, even when `--trusted-scope` and `--confirm-destructive` are
  supplied, because real remote mutation belongs to a future trust-proven
  command pack.
