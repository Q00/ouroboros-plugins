# openhands-agentos

Ouroboros plugin for preserving the OpenHands CLI UX as an audited AgentOS subsystem.

OpenHands owns agent execution, sandboxing, interactive/headless CLI behavior, and provider configuration. Ouroboros should not reimplement that behavior in core. This plugin keeps OpenHands as a UserLevel program while adding explicit trust, bounded workspace, redacted provenance, JSONL capture, and handoff artifacts.

## Commands

```bash
PYTHONPATH=plugins/openhands-agentos python3 -m openhands_agentos inspect
PYTHONPATH=plugins/openhands-agentos python3 -m openhands_agentos run --workspace /path/to/repo --task "Fix the failing test" --out .omx/artifacts/openhands/demo/events.jsonl --trusted-shell-execute
PYTHONPATH=plugins/openhands-agentos python3 -m openhands_agentos handoff --run /path/to/repo/.omx/artifacts/openhands/demo/events.jsonl --out /path/to/repo/.omx/handoffs/openhands/demo.md
PYTHONPATH=plugins/openhands-agentos python3 -m openhands_agentos agentos --workspace /path/to/repo --goal "Fix the failing test" --trusted-shell-execute
```

Dispatcher equivalents: `ooo openhands inspect`, `ooo openhands run`, `ooo openhands handoff`, and `ooo openhands agentos`.

## Safety boundary

- `inspect` is read-only and does not read OpenHands config contents.
- `run` and `agentos` require `--trusted-shell-execute` because OpenHands headless runs auto-approve actions.
- The workspace must be explicit and bounded; output and task-file paths must stay inside that workspace.
- Config defaults to isolated `HOME`, `XDG_CONFIG_HOME`, and `XDG_CACHE_HOME` under `.omx/artifacts/openhands/<run>`.
- `--config-mode native` and `--sandbox process` are explicit operator choices.
- Metadata records redacted command/environment provenance; raw secrets are not written by the plugin.

## Why this satisfies the UserLevel plugin contract

This is intentionally more than a command wrapper. It maps an external agent tool into the Issue #27 plugin contract by declaring capability/permission needs, requiring explicit trust for shell execution, bounding workspace writes, preserving provenance, emitting audit events, and producing handoff artifacts that can be reviewed or consumed by later Ouroboros workflows.

## Product boundary

This plugin owns OpenHands CLI availability inspection, trust-gated `openhands --headless --json` invocation, durable JSONL/stdout/stderr/metadata/audit capture, and Markdown/JSON handoff generation.

Ouroboros core owns plugin install/trust lifecycle, ledger/state primitives, and later consumption of handoff artifacts. `ooo auto` does not need OpenHands-specific logic. A future SDK-backed phase can reuse these artifacts if the OpenHands SDK surface becomes stable enough to adopt.
