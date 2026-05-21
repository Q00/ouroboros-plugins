# aider-assist

`aider-assist` assimilates [Aider](https://github.com/aider-ai/aider) into the
Ouroboros plugin ecosystem as a bounded AgentOS capability.

The goal is not to hide Aider behind an unbounded subprocess wrapper. Aider
keeps its recognizable UX concepts — message, editable files, read-only files,
ask/code/architect modes, lint/test repair, model settings — while Ouroboros
owns the surrounding OS boundary: permissions, provenance, audit, artifacts,
and handoff.

This is a concrete implementation of the issue #27 capability-assimilation
thesis referenced by issue #44: external agent tools become permissioned,
auditable, Seed-compatible capabilities instead of core-specific branches.

## Install strategy

v0 expects the public Aider CLI to be available as `aider` on `PATH`, or via:

```bash
export AIDER_ASSIST_AIDER_BIN=/path/to/aider
```

The adapter does **not** import Aider internals. The CLI boundary is easier to
trust, fake in tests, and replace with `uvx aider-chat` or managed installs in
a later PR without changing the plugin contract.

## Commands

```bash
PYTHONPATH=plugins/aider-assist python3 -m aider_assist ask \
  --message "What owns retry behavior?" \
  --file src/client.py \
  --read docs/networking.md
```

Manifest command equivalents:

```bash
ooo aider ask --message "Explain this module" --file src/foo.py
ooo aider edit --message "Refactor safely" --file src/foo.py --test-cmd "pytest tests/test_foo.py"
ooo aider fix --test-cmd "pytest tests/test_regression.py" --file src/foo.py
ooo aider architect --message "Design a migration" --file src/service.py --read docs/architecture.md
```

## Artifact contract

Every run writes a bounded run directory:

```text
.omx/artifacts/plugins/aider-assist/<run-id>/
  invocation.json
  stdout.txt
  stderr.txt
  answer.md
  handoff.md
```

`edit` also writes:

```text
diff.patch
touched-files.txt
```

Later PRs add `verification.json` for test/lint-backed workflows.

Artifacts are intentionally local and auditable. They must not contain raw API
keys, provider secrets, or raw sensitive environment values.

## Safety defaults

- `ask` treats both `--file` and `--read` as read-only context.
- `edit` requires explicit editable file bounds and refuses unbounded runs.
- `fix` requires explicit editable file bounds when implemented in PR3.
- Aider auto-commit is disabled by default in write modes so Ouroboros owns
  provenance.
- Interactive `session` mode is deferred until transcript capture, pre/post
  diff, trust boundary, and post-session handoff semantics are designed.

## Alignment with issue #27

`aider-assist` is included here as a contract-bearing reference plugin, not as
marketplace inventory. It proves the #27 thesis for a high-authority external
coding agent:

- **External capability identity:** Aider remains the upstream AI pair-programmer
  and is invoked through its public CLI.
- **Ouroboros translation:** each run emits invocation, provenance, result, and
  handoff artifacts under `.omx/artifacts/plugins/aider-assist/<run-id>/`.
- **Boundary:** selected files are normalized to repository-relative paths;
  write modes require explicit editable file bounds in later PRs.
- **Capabilities vs permissions:** manifest capabilities describe Ouroboros
  ledger/provenance/state/handoff/progress use, while permissions declare
  filesystem, shell, and model-provider network authority separately.
- **Risk clarity:** `ask` and `architect` are read-only with respect to the
  repository, but still require trust for `network:write` because Aider may call
  a configured model provider. `edit` and `fix` are write-risk commands.
- **Core boundary:** `ooo auto` may consume the produced handoffs, but Aider
  semantics stay in this plugin rather than becoming core routing branches.

This keeps core small while allowing a serious external agent tool to become
permissioned, auditable, and resumable inside the AgentOS ecosystem.
