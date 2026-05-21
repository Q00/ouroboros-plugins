# gsd-agentos

`gsd-agentos` is a reference Ouroboros plugin that assimilates the
[`gsd-build/get-shit-done`](https://github.com/gsd-build/get-shit-done) command
surface into the AgentOS ecosystem without bypassing the plugin firewall.

It preserves the recognizable GSD command model:

```bash
ooo gsd new-project
ooo gsd plan-phase 1
ooo gsd execute-phase 1
ooo gsd verify-work 1
ooo gsd progress --next
```

while representing every command as a declared, risk-classified, permissioned,
auditable Ouroboros capability.

## Contract artifacts

- `ouroboros.plugin.json` declares every exposed `gsd` command.
- `gsd_agentos/command_catalog.json` is the reviewed contract catalog generated
  from pinned upstream `commands/gsd/*.md` files.
- `gsd_agentos/*` implements inspection, policy checks, provenance, handoffs,
  and bounded shell execution.

## Local CLI

```bash
PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos list
PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos explain plan-phase
PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos validate-catalog
```

Policy-checked invocation requires explicit trust scopes through the dispatcher.
For local tests, the plugin accepts the equivalent environment variable:

```bash
OUROBOROS_TRUST_SCOPES=filesystem:read \
  PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos invoke help --target-repo .

OUROBOROS_TRUST_SCOPES=filesystem:read,filesystem:write \
  PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos invoke plan-phase 1 --target-repo . --handoff
```

Commands that run upstream machinery require `shell:execute` and `--execute`:

```bash
OUROBOROS_TRUST_SCOPES=filesystem:read,filesystem:write,shell:execute \
GSD_AGENTOS_UPSTREAM_RUNNER="/path/to/safe-gsd-runner" \
  PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos invoke verify-work 1 --target-repo . --execute
```

If no runner is configured, `--execute` records an explain-only runner result so
AgentOS still receives bounded provenance.

Destructive commands (`ship`, `complete-milestone`, `pr-branch`, `undo`,
`autonomous`, `audit-fix`, `update`) require command-level confirmation:

```bash
OUROBOROS_TRUST_SCOPES=filesystem:read,filesystem:write,shell:execute \
  PYTHONPATH=plugins/gsd-agentos python3 -m gsd_agentos invoke ship 4 --target-repo . --execute --confirm ship
```

## Handoffs

Write-capable invocations create AgentOS-readable bundles under:

```text
.ouroboros/handoffs/gsd/
  <timestamp>-<command>.md
  <timestamp>-<command>.json
  audit.jsonl
```

The JSON maps GSD artifacts to AgentOS concepts:

| GSD artifact | AgentOS projection |
| --- | --- |
| `.planning/PROJECT.md` | project context / Seed context |
| `.planning/REQUIREMENTS.md` | requirements / acceptance criteria |
| `.planning/ROADMAP.md` | staged plan / phase graph |
| `.planning/STATE.md` | resumability / progress state |
| `.planning/phases/**/*.md` | evidence, execution handoff, or verification result |

## Boundary

This plugin does **not** copy GSD internals into Ouroboros core and does **not**
add GSD-specific branches to `ooo auto`. GSD remains an external capability
suite; Ouroboros owns declaration, permissions, provenance, handoff, audit, and
resumability at the plugin boundary.

## Why this is #27 capability assimilation

Issue #27 defines Ouroboros plugins as the layer that turns external tools and
workflows into structured, auditable, permissioned, Seed-compatible
capabilities. `gsd-agentos` follows that boundary in these ways:

- **External capability:** upstream GSD remains outside Ouroboros core.
- **Contract boundary:** `ouroboros.plugin.json` and the reviewed catalog declare
  the command surface before any invocation can happen.
- **Capabilities vs permissions:** manifest capabilities declare Ouroboros
  substrate access; permissions declare external filesystem, shell, and network
  authority.
- **Risk semantics:** commands are classified as `read_only`, `write`, or
  `destructive`; destructive commands require command-level confirmation.
- **Audit/provenance:** invocations record plugin version, upstream commit,
  command source, argv, target repo, status, and artifact metadata.
- **Handoff:** write-capable commands project GSD planning artifacts into
  AgentOS-readable handoff bundles.
- **Firewall preservation:** blocked commands report missing trust or
  confirmation before upstream behavior can run.
- **No marketplace expansion:** this reference adapter does not add arbitrary GSD
  extension discovery, auto-update, or subdirectory-based install semantics.
- **No `ooo auto` branching:** GSD handoffs can be consumed by Ouroboros flows,
  but `ooo auto` does not gain GSD-specific routing logic.

In short, this plugin is intentionally more than a `python -m some_tool` wrapper:
it is a reviewed adapter from a broad external workflow surface into AgentOS
contract vocabulary.
