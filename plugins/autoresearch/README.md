# autoresearch

Ouroboros plugin for connecting Karpathy-style autoresearch loops to
`ooo auto`.

The upstream workflow in
[`karpathy/autoresearch`](https://github.com/karpathy/autoresearch) treats
`program.md` as the research brief, keeps `prepare.py` fixed, repeatedly edits
`train.py`, runs bounded experiments with `uv run train.py`, and compares
results with `val_bpb`. This plugin keeps that workflow out of Ouroboros core
while making the handoff explicit and auditable.

## Commands

```bash
PYTHONPATH=plugins/autoresearch python3 -m ouroboros_autoresearch inspect /path/to/autoresearch
PYTHONPATH=plugins/autoresearch python3 -m ouroboros_autoresearch prepare /path/to/autoresearch \
  --goal "Improve validation bpb within the standard five-minute loop"
```

When an Ouroboros command dispatcher is available, the manifest exposes the
same workflow as:

```bash
ooo auto-research inspect /path/to/autoresearch
ooo auto-research prepare /path/to/autoresearch --goal "Improve validation bpb"
```

Install from this repository root:

```bash
ouroboros plugin add . --plugin autoresearch
```

With Ouroboros `v0.39.1+`, `plugin add` prints the required
`filesystem:read` and `filesystem:write` permissions with their manifest
reasons and asks whether to grant them immediately. Declining keeps the plugin
installed but invocation remains blocked until the scopes are granted with
`ouroboros plugin trust autoresearch --scope filesystem:read --scope filesystem:write`.

`inspect` is read-only. It checks that the target checkout has the expected
`program.md`, `prepare.py`, and `train.py` files. The layout can be adapted for
compatible forks with repository-relative flags:

- `--program-file` (default: `program.md`)
- `--target-file` (default: `train.py`)
- `--support-file` (default: `prepare.py`)

`prepare` accepts the same layout flags and the handoff-budget flags declared in
`ouroboros.plugin.json`:

- `--goal` (required) — research objective for the Ouroboros handoff
- `--metric` (default: `val_bpb`) — primary comparison metric
- `--max-experiments` (default: `8`) — experiment-count budget
- `--experiment-seconds` (default: `300`) — per-experiment wall-clock budget
- `--train-command` (default: `uv run train.py`) — verification command

`prepare` writes:

- `.ouroboros/autoresearch/seed.md`
- `.ouroboros/autoresearch/auto_goal.txt`
- `.ouroboros/autoresearch/handoff.json`

The generated handoff includes the recommended
`ouroboros auto "$(cat .../auto_goal.txt)"` command, the editable file
boundary, experiment budget, metric, and verification command. `--attach-source`
is intentionally not used here because current Ouroboros uses it only for
attaching an already-started run handle, not for loading a Seed or brief file.

The optional layout flags (`--program-file`, `--target-file`, and
`--support-file`) must be repository-relative paths. Absolute paths and `..`
escapes are rejected so the handoff remains bounded to the inspected checkout.

## Product Boundary

This plugin owns the autoresearch-specific workflow:

- Mapping `program.md` and `train.py` into an Ouroboros Seed
- Preserving the experiment budget and metric as auditable constraints
- Handing the prepared Seed to `ooo auto`

`ooo auto` remains responsible for interview, Seed execution, ledger, and
runtime orchestration. Ouroboros core does not need to understand neural
network research loops directly.
