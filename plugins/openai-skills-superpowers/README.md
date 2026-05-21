# openai-skills-superpowers

`openai-skills-superpowers` adapts OpenAI/Agent Skills into Ouroboros UserLevel commands.
It is a capability-assimilation layer for AgentOS, not a marketplace and not a
bulk copy of each skill into `plugins/`.

Codex-style invocation:

```text
$openai-docs explain the current Apps SDK packaging model
```

maps to the Ouroboros command shape:

```bash
ooo superpower run openai-docs -- "explain the current Apps SDK packaging model"
```

The adapter keeps the skill workflow source authoritative (`SKILL.md` plus
progressively selected resources) while adding manifest resolution, trust and
permission checks, risk classification, audit/provenance events, and handoff
artifacts.

## Commands

Local module commands mirror the manifest command surface:

```bash
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers catalog refresh \
  --source openai/skills \
  --ref 590b49edc158611a2b2ed715ae73f27eb70d251a

PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers catalog list
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers inspect openai-docs
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers handoff security-threat-model \
  --task "model this repo's trust boundaries" \
  --out .ouroboros/handoffs/security-threat-model.json
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers run openai-docs -- \
  "explain how to build a plugin"
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers trust-plan hatch-pet
PYTHONPATH=plugins/openai-skills-superpowers python3 -m ouroboros_superpowers doctor
```

When an Ouroboros dispatcher is available, the same operations are exposed as:

```bash
ooo superpower catalog refresh --source openai/skills --ref <pinned-sha>
ooo superpower catalog list
ooo superpower inspect <skill-name>
ooo superpower handoff <skill-name> --task <task> --out <path>
ooo superpower run <skill-name> -- <task>
ooo superpower trust-plan <skill-name>
ooo superpower doctor
```


## Alignment with issue #27

Issue #27 defines Ouroboros plugins as capability assimilation, not command
wrapping or marketplace packaging. `openai-skills-superpowers` follows that contract:

- **Contract/reference repository:** one reference adapter lives under
  `plugins/openai-skills-superpowers`; individual OpenAI skills are catalog entries, not
  separate plugins submitted to this repository.
- **Not a trivial wrapper:** the adapter translates Agent Skills into declared
  commands, capabilities, permissions, risk profiles, audit/provenance events,
  blocked/completed outcomes, and handoff artifacts.
- **Capabilities vs permissions:** manifest capabilities declare Ouroboros
  primitives (`handoff`, `provenance`, `ledger`, `state`, `progress`), while
  permissions declare external authority (`filesystem:*`, `network:read`,
  `shell:execute`, GitHub/external writes).
- **Lifecycle/trust/firewall:** `run` performs runtime risk checks and blocks
  write-capable, script-backed, external-write, and destructive skills until a
  future plugin-manager trust context can prove exact granted scopes.
- **`ooo auto` boundary:** handoffs are consumable by `ooo auto`, but this
  plugin does not add skill-specific routing branches to `ooo auto` or core.
- **Schema discipline:** v0 uses the existing manifest contract plus runtime
  risk overlays; direct aliases and schema extensions are deferred until the
  contract proves they are necessary and auditable.

## Catalog and duplicate policy

The catalog records skill name, bucket (`.curated` or `.system`), source path,
repository, ref/commit, description, license presence, resource inventory,
inferred permissions, risk tier, and command exposure. If a skill name appears
in both `.curated` and `.system`, unqualified lookup resolves to `.curated`;
use `system/<skill-name>` to inspect or run the system duplicate.

System skills are included in the catalog and hidden from `catalog list` unless
`--include-system` is supplied.

## Permission and risk policy

`superpower run` is conservative:

- Read-only skills can run as handoff/run projections.
- Write-capable skills are blocked in this standalone adapter until a
  plugin-manager trust context can prove exact granted scopes.
- Script-backed skills are blocked in this standalone adapter; `trust-plan`
  explains the future scopes needed for manager-mediated execution.
- External-write and destructive skills are blocked until manager-mediated trust
  and confirmation semantics are available.
- Direct aliases such as `ooo openai-docs` are deferred until namespace
  collision and alias ownership policy is stronger.

The adapter does not execute hidden external writes. For script-backed skills,
this PR deliberately stops at `trust-plan` and blocked run outcomes because this
repository does not yet expose a plugin-manager trust-context object to the
entrypoint. Future manager-mediated execution must prove exact granted scopes
before exposing script paths or recording executed-script provenance.

## Handoff and `ooo auto` boundary

`superpower handoff` writes `kind: superpower_handoff` JSON containing the skill
source, task, permission/risk profile, instruction excerpt, progressively loaded
resources, and next steps. `ooo auto` may consume this handoff as an input brief,
but `ooo auto` should not become a skill-specific router.

## Provenance

Audit lines are written to `.ouroboros/openai-skills-superpowers/audit.jsonl` by default and
use the standard plugin event vocabulary:

- `plugin.invoked`
- `plugin.permission_used`
- `plugin.completed`
- `plugin.failed`

Each event records the skill, bucket, source repository/ref/path, permissions,
status, and command argv.
