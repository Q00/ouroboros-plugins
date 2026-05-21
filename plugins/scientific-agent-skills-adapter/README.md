# Scientific Agent Skills adapter

Reference AgentOS/Ouroboros adapter for assimilating
[`K-Dense-AI/scientific-agent-skills`](https://github.com/K-Dense-AI/scientific-agent-skills)
without bypassing the plugin firewall.

This plugin proves the issue #35 boundary: the upstream repository remains an
external capability pack, while `ouroboros-plugins` carries the contract,
generated registry, manifest aliases, risk/permission metadata, and handoff-first
runtime semantics.

## Commands

```bash
PYTHONPATH=plugins/scientific-agent-skills-adapter python3 -m scientific_agent_skills_adapter doctor
PYTHONPATH=plugins/scientific-agent-skills-adapter python3 -m scientific_agent_skills_adapter list --domain chemistry
PYTHONPATH=plugins/scientific-agent-skills-adapter python3 -m scientific_agent_skills_adapter inspect rdkit
PYTHONPATH=plugins/scientific-agent-skills-adapter python3 -m scientific_agent_skills_adapter prepare rdkit --task "cluster these molecules"
PYTHONPATH=plugins/scientific-agent-skills-adapter python3 -m scientific_agent_skills_adapter run opentrons-integration --task "draft a protocol" --dry-run
```

When dispatched through AgentOS, the manifest exposes the same surface as:

```bash
ooo scientific list [--domain <domain>] [--risk <risk>]
ooo scientific inspect <skill>
ooo scientific explain <skill> [--task <goal>]
ooo scientific prepare <skill> --task <goal> [--output <path>]
ooo scientific run <skill> --task <goal> [--dry-run]
ooo scientific trust-report <skill>
ooo scientific doctor
ooo scientific <skill-slug> --task <goal>
```


## Issue #27 contract alignment

This adapter follows the #27 capability-assimilation contract:

- `ouroboros-plugins` remains a curated contract/reference repository, not the
  marketplace or canonical home for the long-tail scientific pack.
- The upstream repository is assimilated through generated metadata,
  provenance, risk, permissions, audit, and handoff artifacts rather than raw
  command wrapping.
- Core capabilities are declared only when this adapter actually uses them;
  future `runtime` or `mcp` authority must be added only with a corresponding
  trusted execution path and tests.
- `ooo auto` consumes generated handoffs while staying domain-agnostic.

## Safety model

- `list`, `inspect`, `explain`, `trust-report`, and `doctor` are read-only.
- `prepare` writes only `.ouroboros/scientific-agent-skills/*` handoff,
  provenance, Seed, and audit artifacts.
- `run --dry-run` is equivalent to a prepared handoff and does not execute
  upstream scripts.
- Actual `run` is blocked for write/destructive/manual-review skills. This
  reference adapter intentionally does not execute high-risk upstream scripts,
  call lab automation/cloud APIs, or grant blanket shell/network authority.

## Regeneration

The checked-in registry and manifest were generated from a pinned upstream
checkout:

```bash
git clone https://github.com/K-Dense-AI/scientific-agent-skills /tmp/scientific-agent-skills
python3 scripts/generate_scientific_adapter.py /tmp/scientific-agent-skills
python3 scripts/validate_contract.py
python3 -m pytest tests/test_scientific_agent_skills_adapter.py
```

Use `--check` in CI or review workflows to detect manifest/registry drift
against a provided upstream checkout.
