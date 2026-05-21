# Issue #37 Graphify validation and merge readiness

This document is the final validation artifact for the six stacked Graphify PRs.

## Stacked PR sequence

1. `feat/issue37-graphify-pr1-contract` — contract scope and docs baseline.
2. `feat/issue37-graphify-pr2-manifest` — manifest, package identity, and catalog entry.
3. `feat/issue37-graphify-pr3-adapter` — thin upstream Graphify CLI adapter.
4. `feat/issue37-graphify-pr4-handoff` — handoff/provenance/artifact enrichment.
5. `feat/issue37-graphify-pr5-gates` — sensitive-operation gates.
6. `feat/issue37-graphify-pr6-validation` — final validation evidence.

## Acceptance mapping

- `plugins/graphify/ouroboros.plugin.json` validates against schema `0.1`.
- Baseline capabilities are declared without new manifest fields.
- `python -m graphify_plugin` resolves upstream Graphify or returns a structured blocked result.
- build/query/path/explain and update-style passthrough preserve upstream argv compatibility.
- handoff JSON records plugin/upstream metadata, command argv, permissions, target evidence, artifacts, graph stats, and stdout/stderr excerpts.
- URL/model/MCP/watch/Neo4j-sensitive operations are explicitly classified and blocked in direct adapter use unless `--allow-sensitive` is provided after trust/confirmation.
- Ouroboros core remains generic: downstream automation consumes handoffs rather than adding Graphify-specific branches.

## Verification commands

Run from the head of PR6:

```bash
python3 scripts/validate_contract.py
python3 -m unittest discover -s tests
```

Observed result on 2026-05-21:

```text
contract validation passed (3 plugin manifest(s) validated)
Ran 23 tests ... OK
```

## Deferred live checks

The test suite intentionally does not start live Graphify optional surfaces:

- real model-provider calls;
- long-running `--mcp` or `--watch` sessions;
- Neo4j push;
- hook/merge-driver installation.

Those remain explicit trust-gated operational checks, not CI defaults.
