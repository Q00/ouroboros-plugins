# Langfuse Observability Plugin

Assimilates Langfuse traces, observations, scores, and evaluation evidence into Ouroboros AgentOS handoff/provenance workflows.

## Commands

```bash
ooo langfuse inspect <trace-url-or-id>
ooo langfuse score <artifact-path> --name correctness --value 0.8 --dry-run
ooo langfuse score <artifact-path> --name correctness --value 0.8 --confirm
```

## Configuration

Environment variables are used first:

```bash
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

Secrets are never written to terminal output, artifacts, audit events, or Markdown summaries.

## AgentOS boundary

- `inspect` is read-only and writes redacted local handoff artifacts under `.omx/handoffs/langfuse/`.
- `score --dry-run` writes a local provenance artifact and performs no network write.
- Real `score` publication requires credentials and explicit `--confirm`.
- Prompt management, datasets/evals, and self-host lifecycle commands are intentionally deferred.

## Local validation

```bash
python3 scripts/validate_contract.py
PYTHONPATH=plugins/langfuse-observability python3 -m langfuse_observability inspect trace_123 --offline-fixture plugins/langfuse-observability/tests/fixtures/langfuse-trace.json
PYTHONPATH=plugins/langfuse-observability python3 -m langfuse_observability score .omx/handoffs/langfuse/trace_123.json --name correctness --value 0.8 --dry-run
pytest
```
