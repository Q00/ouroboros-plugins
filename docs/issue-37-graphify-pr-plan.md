# Issue #37 Graphify assimilation PR plan

Source epic: <https://github.com/Q00/ouroboros-plugins/issues/37>

Goal: assimilate `safishamsi/graphify` into Ouroboros/AgentOS as a first-class knowledge-graph capability through `plugins/graphify/`, not by vendoring Graphify into core. The plugin is the packaging, adapter, trust, audit, provenance, and handoff surface.

## PR count and scopes

This epic should be implemented as **6 PRs**:

1. **PR 1 — Contract scope and docs baseline**
   - Scope: issue analysis, command/risk classification, non-goals, AgentOS handoff flows, schema pressure points.
   - Files: `docs/issue-37-graphify-pr-plan.md`, `plugins/graphify/README.md` draft.
   - No runtime behavior beyond documentation.

2. **PR 2 — Manifest and package skeleton**
   - Scope: `plugins/graphify/ouroboros.plugin.json`, Python package skeleton, test scaffolding.
   - Manifest must validate under schema `0.1` without new fields.
   - Declare conservative capabilities/permissions: filesystem and shell baseline; network/model/MCP/watch/Neo4j optional/gated.

3. **PR 3 — Thin adapter MVP**
   - Scope: `python -m graphify_plugin` adapter for `ooo graphify`, local build, `--update`, `query`, `path`, and `explain`.
   - Resolve upstream executable via `graphify` on `PATH`, then `python -m graphify`; never auto-install.
   - Capture stdout/stderr/exit code and emit structured result JSON.

4. **PR 4 — Audit, provenance, and handoff enrichment**
   - Scope: artifact discovery, graph stats from `graph.json`, plugin/upstream version evidence, permission-sensitive operation list, handoff JSON under `.omx/handoffs/graphify/`.
   - Query/path/explain output must be reusable as downstream evidence.

5. **PR 5 — Gated extended Graphify UX**
   - Scope: preserve broader Graphify UX for URL ingestion, GitHub URL clone, export flags, `--mcp`, `--watch`, and `--neo4j-push` through explicit gates.
   - Network/model/hook/MCP/watch/Neo4j operations stay blocked in direct adapter use unless an explicit allow flag is passed and remain optional permissions in the manifest.
   - Internal maintenance helpers remain hidden unless a stable user-facing contract is documented.

6. **PR 6 — Final validation and review hardening**
   - Scope: full manifest/test/docs validation, changed-file cleanup, and final review evidence.
   - Acceptance evidence must show that merging PRs 1–6 closes issue #37 without Ouroboros core changes except documented schema pressure points.

## Issue #27 alignment

Issue #27 defines `Q00/ouroboros-plugins` as a curated contract/reference repository, not a marketplace, and requires reference plugins to prove an assimilation boundary rather than merely wrap commands. The Graphify stack aligns as follows:

| #27 criterion | Graphify PR coverage |
| --- | --- |
| Core stays small; plugins assimilate capability | Graphify remains under `plugins/graphify/`; no Ouroboros core or `ooo auto` Graphify-specific branches are added. |
| Curated reference plugin, not marketplace growth | Graphify is justified as a contract-bearing knowledge-graph reference adapter, not as a generic third-party listing. |
| Not just a shell wrapper | PR3 launches upstream Graphify, while PR4/PR5 add bounded inputs, permission classification, audit/provenance, handoff artifacts, and blocked states. |
| Manifest is the minimum executable boundary | PR2 uses schema `0.1` with required identity, commands, capabilities, permissions, and entrypoint, without speculative fields. |
| Capabilities and permissions stay distinct | Core access is declared as ledger/state/provenance/handoff/progress/runtime/MCP capabilities; external authority is declared as filesystem/shell/network/GitHub/MCP/database permissions. |
| Risk taxonomy drives trust UX | Read-only query/path/explain are separated from write build/add/serve/push commands; sensitive surfaces remain optional and confirmation-gated. |
| Lifecycle/trust/firewall are mandatory | The adapter never auto-installs Graphify and returns structured blocked results for missing dependency, untrusted sensitive operations, and out-of-bound paths. |
| Audit/provenance/handoff make assimilation safe | PR4 emits reusable handoff JSON with plugin/upstream version, argv, permissions, target evidence, artifacts, graph stats, and excerpts. |
| `ooo auto` remains generic | Graphify outputs are handoffs/evidence that `ooo auto` may consume; no domain-specific router logic is added. |
| Schema expansion requires proof | The plan documents `mcp:execute`, `database:write`, and dynamic risk as pressure points while keeping v0 inside schema `0.1`. |

Review rule for the stack: a PR is not merge-ready if it weakens any #27 boundary above, even if its local tests pass.

## Confirmed v0 command surface

- `ooo graphify [path] [--update] [--mode deep] [--directed] [--no-viz] [--html] [--svg] [--graphml] [--neo4j] [--wiki] [--obsidian --obsidian-dir <path>]`
- `ooo graphify query "<question>" [--dfs] [--budget <tokens>] [--graph <path>]`
- `ooo graphify path "<source>" "<target>" [--graph <path>]`
- `ooo graphify explain "<node>" [--graph <path>]`
- `ooo graphify add <url> [--author <name>] [--contributor <name>]` gated by network permission.
- `ooo graphify --mcp`, `ooo graphify --watch`, and `ooo graphify --neo4j-push <bolt-url>` gated as long-running/external-write operations.

## Explicit non-goals

- Do not vendor or fork Graphify internals into Ouroboros core.
- Do not silently install `graphifyy`, hooks, merge drivers, model backends, or optional extras.
- Do not require every optional Graphify extra for baseline plugin installation.
- Do not teach `ooo auto` Graphify-specific branches; `ooo auto` consumes handoff artifacts generically.
- Do not hide external writes or model API calls behind broad filesystem/shell permissions.

## Schema pressure points

The current schema can represent v0 with conservative command and permission declarations. Potential future issues should be filed rather than silently extending the manifest:

- `mcp:call` appears in docs, while schema `0.1` supports `mcp` with `execute`; v0 uses `mcp:execute` semantics through capability `{ "name": "mcp", "access": "execute" }`.
- Neo4j push may deserve a future `database:write` permission class; v0 declares `database:write` as an optional external permission scope and treats it as gated.
- Dynamic per-flag command risk is richer than manifest command risk; v0 keeps command declarations conservative and enforces runtime gates in the adapter.
