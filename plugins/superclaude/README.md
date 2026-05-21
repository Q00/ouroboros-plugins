# SuperClaude Ouroboros Plugin

Ouroboros-native adapter for the pinned SuperClaude Framework plugin assets.

- Upstream repository: <https://github.com/SuperClaude-Org/SuperClaude_Framework>
- Snapshot commit: `226c45cc93b865108843a669c6545d421784b68c`
- Snapshot date: `2026-04-27T08:38:57+05:30`
- Upstream version: `4.3.0`
- Upstream license: MIT, preserved in `upstream/LICENSE.SuperClaude`

This plugin assimilates SuperClaude into the AgentOS/Ouroboros plugin contract without adding SuperClaude-specific branches to Ouroboros core. The MVP is not an unrestricted shell wrapper. It exposes SuperClaude commands, skills, agents, modes, MCP recommendations, lifecycle-hook intent, audit payloads, and handoff artifacts through a manifest-governed subprocess adapter.

## Install and trust

```bash
ouroboros plugin add https://github.com/Q00/ouroboros-plugins --plugin superclaude
ouroboros plugin trust superclaude --scope filesystem:read
# Add only when needed:
ouroboros plugin trust superclaude --scope filesystem:write
ouroboros plugin trust superclaude --scope shell:execute
ouroboros plugin trust superclaude --scope network:read
```

During local development:

```bash
ouroboros plugin add . --plugin superclaude
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros help
```

## UX mapping

| SuperClaude mental model | Ouroboros MVP command |
|---|---|
| `/sc:analyze src --focus security` | `ooo superclaude analyze src --focus security` |
| `/sc:brainstorm "idea"` | `ooo superclaude brainstorm "idea"` |
| `/sc:pm` | `ooo superclaude pm` |
| `/sc:research topic` | `ooo superclaude research topic` |
| `/sc:test --type unit` | `ooo superclaude test --type unit` |
| `/sc:workflow feature` | `ooo superclaude workflow feature` |
| Explicit skill invocation | `ooo superclaude skill <skill-name> ...` |

The desired short alias `ooo sc <command>` is intentionally **not** declared in this MVP because schema `0.1` requires command namespaces to match `^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$`; the two-character namespace `sc` is invalid. A future schema/runtime alias extension can map `sc` to `superclaude` without bypassing validation.

## Command surface

All 30 upstream command files from the pinned snapshot are exposed under the canonical `superclaude` namespace:

```text
agent analyze brainstorm build business-panel cleanup design document estimate explain git help implement improve index index-repo load pm recommend reflect research save sc select-tool spawn spec-panel task test troubleshoot workflow
```

Additional MVP routes expose concrete upstream skills:

```text
skill <skill-name>
confidence-check
token-efficiency
```

Overlapping skills (`brainstorm`, `deep-research`/`research`, `pm`, `troubleshoot`) preserve the normal command UX while the adapter also loads the corresponding `SKILL.md` when available. Non-overlapping skills are directly invocable through both `ooo superclaude skill confidence-check` / `ooo superclaude confidence-check` and `ooo superclaude skill token-efficiency` / `ooo superclaude token-efficiency`.

## Snapshot discrepancy

Upstream README prose mentions 7 skills, but the pinned snapshot contains 6 concrete `SKILL.md` folders:

```text
brainstorm confidence-check deep-research pm token-efficiency troubleshoot
```

This plugin exposes the 6 concrete skills found in the package and documents the mismatch instead of inventing an absent seventh skill.

## Agents, modes, MCP, and hooks

Packaged agents are stored under `assets/agents/` and can be listed or selected:

```bash
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros --list agents
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros analyze src --agent security-engineer
```

Packaged modes are stored under `assets/modes/` and selected with `--mode`:

```bash
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros brainstorm "new workflow" --mode Brainstorming
```

MCP recommendations are stored in `assets/mcp/mcp.json` and documented only. The plugin does **not** install MCP servers implicitly. Commands that require current web/MCP research should request `network:read` explicitly.

Upstream Claude Code hooks are stored in `assets/hooks/hooks.json`. The MVP maps them to documented lifecycle expectations; it does not execute hidden hooks outside the Ouroboros firewall.

## Alignment with #27 capability assimilation

This plugin is a reference capability-assimilation plugin under the direction of issue #27. It is not a marketplace listing and not a request to add SuperClaude-specific branches to Ouroboros core.

It preserves the #27 boundary by translating SuperClaude into:

- explicit manifest commands instead of implicit slash-command routing,
- declared core capabilities distinct from external permissions,
- conservative shared risk tiers,
- trust-gated runtime behavior,
- audit event payloads and upstream provenance,
- handoff artifacts for planning/research/workflow commands,
- documented MCP/hook guidance without hidden execution, and
- follow-up contract questions where schema/runtime support is required.

The intended AgentOS path is:

```text
SuperClaude Framework assets
        ↓
Ouroboros plugin manifest + command firewall
        ↓
permissioned, auditable, handoff-capable adapter
        ↓
AgentOS-level capability without core expansion
```

## Runtime behavior

The adapter returns structured JSON. Read-only commands run without write trust:

```bash
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros analyze src --focus security
```

Write commands are blocked unless trust scopes are supplied by the runtime. For local smoke tests, simulate the firewall grant with `OUROBOROS_TRUSTED_SCOPES`:

```bash
OUROBOROS_TRUSTED_SCOPES=filesystem:write \
PYTHONPATH=plugins/superclaude python3 -m superclaude_ouroboros brainstorm "AgentOS plugin assimilation" --artifact-dir /tmp/sc-handoffs
```

Shell-backed commands also require `shell:execute`; network-backed research requires `network:read` only when `--web`, `--network`, or `--mcp` is requested. Destructive Git-style paths require `git:write` plus `--confirm-destructive`.

## Audit and handoff

Each invocation emits standard plugin audit event payloads in the JSON response. If `--audit-dir <dir>` is supplied, events are appended to `<dir>/superclaude-audit.jsonl`.

Planning/research/workflow-style commands write a handoff markdown artifact when `--artifact-dir <dir>` is supplied and required trust scopes are present. The artifact includes the pinned upstream provenance, selected command, selected skill, selected agent, and selected mode instructions.

## Contract follow-ups

Full-fidelity framework assimilation should be resolved through contract/RFC work, not adapter bypasses:

1. Command namespace aliases such as `sc`.
2. Optional two-character namespace relaxation.
3. Manifest-native asset metadata for agents, modes, and skills.
4. Lifecycle hook mapping.
5. Optional MCP recommendation metadata.
6. Prompt-native command assets that do not require a subprocess shim.
