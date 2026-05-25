# visual-companion

Ouroboros plugin adapter for the `visual-companion` Codex skill.

The plugin is intentionally an I/O bridge, not a design generator. Agents or
workflows author HTML screens; this plugin serves those screens in a local
browser session, receives click/form events, and records JSON handoff evidence.

## Commands

```bash
ooo visual-companion start --project-dir .
ooo visual-companion show --html path/to/screen.html --state-dir <state-dir>
ooo visual-companion wait --state-dir <state-dir> --timeout-ms 1800000
ooo visual-companion read --state-dir <state-dir>
ooo visual-companion stop --session-dir <session-dir>
```

Direct adapter invocation during development:

```bash
PYTHONPATH=plugins/visual-companion python -m visual_companion_plugin start --project-dir .
PYTHONPATH=plugins/visual-companion python -m visual_companion_plugin show --html screen.html --state-dir .brainstorm/<session>/state
PYTHONPATH=plugins/visual-companion python -m visual_companion_plugin wait --state-dir .brainstorm/<session>/state
PYTHONPATH=plugins/visual-companion python -m visual_companion_plugin read --state-dir .brainstorm/<session>/state
PYTHONPATH=plugins/visual-companion python -m visual_companion_plugin stop --session-dir .brainstorm/<session>
```

## Install and trust

From this repository root:

```bash
ouroboros plugin add . --plugin visual-companion
ouroboros plugin trust visual-companion --scope filesystem:read --scope filesystem:write --scope shell:execute
```

## Output artifacts

Each invocation writes handoff evidence under the resolved output root:

```text
<output-root>/.omx/handoffs/visual-companion/
```

The visual session itself is persisted under `<output-root>/.brainstorm/`.
`--project-dir` takes precedence. Without it, the adapter prefers
`OUROBOROS_PLUGIN_OUTPUT_DIR`, then `OUROBOROS_PLUGIN_WORKDIR`, then the current
working directory. If the current working directory is the installed plugin
home, artifacts fall back to a user-local Ouroboros artifact directory so the
trusted plugin home is not modified at runtime.

Add `.brainstorm/` to the target project's ignore rules when those screens
should remain local-only.

## Non-goals

- The plugin does not generate polished UI templates in v1.
- The plugin does not decide visual design direction.
- The plugin does not automate a browser; it serves local pages and receives
  browser-originated events.
- The plugin does not install Node or other runtime dependencies.
