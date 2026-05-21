# SWE-agent Harness Plugin

`plugins/swe-agent-harness` assimilates upstream [`SWE-agent/SWE-agent`](https://github.com/SWE-agent/SWE-agent) into AgentOS as a permissioned, auditable issue-to-patch execution harness.

The goal is UX-preserving assimilation, not vendoring and not a trivial unbounded wrapper. This plugin follows #27: `Q00/ouroboros-plugins` remains a curated contract/reference repository, not a marketplace, and SWE-agent becomes Ouroboros-native only by declaring capabilities, permissions, risk, audit, provenance, and handoff semantics. Users who know `sweagent` should recognize the command shape:

```bash
sweagent run --config config/default.yaml \
  --agent.model.name gpt-4o \
  --env.repo.github_url https://github.com/org/repo \
  --problem_statement.github_url https://github.com/org/repo/issues/123

# AgentOS-native equivalent
ooo swe-agent run --config config/default.yaml \
  --agent.model.name gpt-4o \
  --env.repo.github_url https://github.com/org/repo \
  --problem_statement.github_url https://github.com/org/repo/issues/123
```

The plugin adds AgentOS metadata around the run:

- bounded artifact directory and run id
- permission/risk classification
- stdout/stderr capture
- `run-spec.json`
- `provenance.json`
- `audit-summary.json`
- `handoff.json` and `handoff.md`
- normalized patch/prediction/trajectory pointers when upstream artifacts exist

## Commands

| Command | Risk | Purpose |
|---|---:|---|
| `ooo swe-agent run ...` | write | Pass through to `sweagent run` after trust checks and artifact setup. |
| `ooo swe-agent run-replay ...` | write | Pass through to `sweagent run-replay` and attach replay artifacts. |
| `ooo swe-agent inspect <path>` | read_only | Summarize existing SWE-agent artifacts without mutation. |
| `ooo swe-agent quick-stats <dir>` | read_only | Count trajectories, predictions, patches, logs, and configs. |
| `ooo swe-agent collect-artifacts <dir>` | write | Convert existing SWE-agent output into an AgentOS artifact bundle. |
| `ooo swe-agent handoff <bundle>` | write | Regenerate `handoff.json` and `handoff.md`. |
| `ooo swe-agent verify-artifacts <bundle>` | read_only | Check required AgentOS metadata files. |

Deferred commands: `run-batch`, `apply-patch`, `open-pr`, and offensive/security modes.

## Local development usage

From the repository root:

```bash
PYTHONPATH=plugins/swe-agent-harness python3 -m swe_agent_harness inspect /path/to/swe-agent-output
PYTHONPATH=plugins/swe-agent-harness python3 -m swe_agent_harness quick-stats /path/to/swe-agent-output
PYTHONPATH=plugins/swe-agent-harness python3 -m swe_agent_harness collect-artifacts /path/to/swe-agent-output
PYTHONPATH=plugins/swe-agent-harness python3 -m swe_agent_harness run --agentos-dry-run --config config/default.yaml
```

Real execution requires explicit shell/runtime trust acknowledgement in the adapter and corresponding plugin trust in the host:

```bash
PYTHONPATH=plugins/swe-agent-harness python3 -m swe_agent_harness run \
  --agentos-allow-execute \
  --config config/default.yaml \
  --env.repo.github_url https://github.com/org/repo \
  --problem_statement.github_url https://github.com/org/repo/issues/123
```

If `sweagent` is unavailable, or shell/runtime trust is missing, the plugin writes blocked artifacts instead of pretending a run occurred.

## AgentOS flags

Namespaced flags do not collide with upstream dotted overrides:

- `--agentos-artifact-dir <dir>`: explicit AgentOS bundle directory.
- `--agentos-run-id <id>`: explicit run id.
- `--agentos-sweagent-bin <path-or-name>`: upstream executable, default `sweagent` or `$SWE_AGENT_BIN`.
- `--agentos-dry-run`: write metadata without invoking SWE-agent.
- `--agentos-allow-execute`: acknowledge shell/runtime authority for real runs.
- `--agentos-allow-host-patch`: allow upstream args that appear to apply a patch to the host repo.
- `--agentos-allow-open-pr`: allow upstream args that appear to push/open a GitHub PR.

Host patch application and PR creation are not automatic.

## Capabilities and permissions

Capabilities:

- `seed:write`
- `ledger:write`
- `state:write`
- `provenance:write`
- `runtime:execute`
- `handoff:attach`
- `progress:write`

Permissions:

- required: `filesystem:read`, `filesystem:write`, `shell:execute`, `runtime:execute`
- optional: `network:read`, `network:write`, `github:read`, `github:pull_request:write`

`github:pull_request:write` is declared as optional destructive authority and is not used by default.

## Artifact bundle

Default bundle path:

```text
.agentos/swe-agent/<run-id>/
```

Bundle contents:

```text
run-spec.json
upstream-command.txt
stdout.log
stderr.log
swe-agent-output/
patch.diff
prediction.pred
trajectory.traj
audit-summary.json
provenance.json
handoff.json
handoff.md
```

The plugin preserves upstream output under `swe-agent-output/` and adds normalized pointers/copies for downstream AgentOS handoff.

## Non-goals

- Do not vendor SWE-agent into Ouroboros core.
- Do not hide upstream YAML config or dotted override style.
- Do not silently apply patches to the host repository.
- Do not silently push branches or open PRs.
- Do not store raw secrets, OAuth tokens, or unbounded private prompts in provenance.
- Do not expand manifest schema v0.1 speculatively.
