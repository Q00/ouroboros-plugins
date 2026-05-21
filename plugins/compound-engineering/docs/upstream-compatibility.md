# Upstream compatibility

The adapter preserves Compound Engineering's semantic command names and workflow ordering while replacing slash commands such as `/ce-plan` with schema-valid AgentOS commands such as `ooo compound plan`.

## Preserved

- All 37 upstream skills are vendored under `assets/skills`.
- All upstream agent prompt assets are vendored under `assets/agents`.
- The core loop remains `brainstorm -> plan -> work -> code-review -> compound`.
- Command artifacts keep upstream repository, version, and skill provenance.

## Intentional divergences

- `ce` is not used as the namespace because the current schema requires at least three characters.
- The adapter emits bounded handoff artifacts rather than accepting arbitrary shell text.
- Destructive workflows are blocked unless the command is explicitly confirmed and trusted.
- Command aliases and command-scoped manifest permissions are documented follow-up schema pressure points rather than preemptive schema changes.
