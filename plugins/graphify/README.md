# graphify

Ouroboros plugin adapter for assimilating [`safishamsi/graphify`](https://github.com/safishamsi/graphify) into the AgentOS capability layer as a permissioned, auditable knowledge-graph workflow.

Graphify remains the upstream implementation. This plugin provides the AgentOS-native surface: manifest, permission declarations, trust gates, provenance, state, and handoff artifacts.

## Install and trust

```bash
ouroboros plugin add . --plugin graphify
ouroboros plugin trust graphify --scope filesystem:read --scope filesystem:write --scope shell:execute
uv tool install graphifyy   # or: pipx install graphifyy
```

The adapter never installs Graphify automatically. If `graphify` is missing, it returns a structured `blocked` result explaining how to install `graphifyy`.

Optional scopes are granted only for matching commands:

- `network:read`: URL ingestion and GitHub clone targets.
- `network:write`: model backends and external API/database pushes.
- `mcp:execute`: Graphify MCP server mode.
- `database:write`: Neo4j push. This is a schema pressure point for a richer future database scope.
- `github:read`: PR dashboard/impact flows if exposed later.

## Command mapping

Upstream assistant UX maps to AgentOS as:

```bash
ooo graphify .
ooo graphify ./docs --update
ooo graphify query "what connects auth to the database?"
ooo graphify path "UserService" "DatabasePool"
ooo graphify explain "RateLimiter"
ooo graphify add https://arxiv.org/abs/1706.03762
```

Direct adapter invocation during development:

```bash
PYTHONPATH=plugins/graphify python3 -m graphify_plugin .
PYTHONPATH=plugins/graphify python3 -m graphify_plugin query "what are the central modules?" --graph graphify-out/graph.json
```

The adapter forwards unknown Graphify flags, preserving upstream UX. It adds:

- `--allow-sensitive`: permits operations already trusted by the plugin manager, such as network ingestion, watch/MCP, model backends, and Neo4j push.
- `--handoff-out <path>`: writes handoff JSON to a specific path.
- `--no-handoff`: prints result JSON without writing a handoff file.

## Gated operations

The direct adapter blocks permission-sensitive operations unless `--allow-sensitive` is present:

| Operation | Gate | Reason |
| --- | --- | --- |
| `add <url>` or URL build target | `network:read` | Fetches remote content into local graph state. |
| model/backend flags | `network:write` | May send user content to model providers. |
| `--mcp` | `mcp:execute` | Starts a long-running tool surface. |
| `--watch` | confirmation | Long-running filesystem watcher. |
| `--neo4j-push <bolt-url>` | `network:write`, `database:write` | Writes to an external database. |

Hook installation, merge-driver installation, global platform skill installers, and destructive helpers remain outside the v0 public command surface.

## Handoff and audit evidence

Every invocation prints JSON and, by default, writes a handoff file under:

```text
.omx/handoffs/graphify/<timestamp>-<command>.json
```

The handoff includes:

- plugin version and upstream Graphify version if discoverable;
- command family, argv, return code, risk, and permissions used;
- generated artifacts such as `graphify-out/GRAPH_REPORT.md`, `graphify-out/graph.json`, and exports;
- graph stats parsed from `graphify-out/graph.json` when available;
- stdout/stderr excerpts for query/path/explain evidence;
- permission-sensitive operations used;
- next suggested AgentOS commands.

`ooo auto`, planning, review, QA, and handoff workflows should consume these generic artifacts. Ouroboros core does not need Graphify-specific branches.

## Non-goals

- Do not vendor Graphify into Ouroboros core.
- Do not auto-install `graphifyy` or optional extras.
- Do not silently run hooks, model APIs, MCP/watch processes, or Neo4j writes.
- Do not expose Graphify maintenance helpers as public AgentOS commands until they have a clear contract.

See [`docs/issue-37-graphify-pr-plan.md`](../../docs/issue-37-graphify-pr-plan.md) for the six-PR epic plan and schema pressure points.
