# guardrails-eval

Ouroboros plugin for using [Guardrails AI](https://github.com/guardrails-ai/guardrails)
as a bounded validation/evaluation adapter.

The plugin preserves familiar Guardrails concepts — guard specs, validators,
`Guard.parse(...)`, and `ValidationOutcome` — while emitting normalized
Ouroboros report and handoff artifacts for audit, provenance, ledger, state, and
workflow acceptance gates.

## Commands

Direct Python usage from this repository root:

```bash
PYTHONPATH=plugins/guardrails-eval python3 -m guardrails_eval validate-output \
  --spec guards/toxic-language.rail \
  --output .omx/artifacts/model-output.txt \
  --report .omx/reports/guardrails-toxic-language.json \
  --handoff .omx/handoffs/guardrails-toxic-language.json

PYTHONPATH=plugins/guardrails-eval python3 -m guardrails_eval validate-artifact \
  --spec guards/structured-report.json \
  --artifact .omx/artifacts/research-summary.md \
  --report .omx/reports/guardrails-research-summary.json \
  --handoff .omx/handoffs/guardrails-research-summary.json

PYTHONPATH=plugins/guardrails-eval python3 -m guardrails_eval summarize-report \
  --report .omx/reports/guardrails-research-summary.json
```

When an Ouroboros command dispatcher is available, the manifest exposes the
same workflow as:

```bash
ooo guardrails validate-output --spec <path> (--output <path>|--text <text>)
ooo guardrails validate-artifact --spec <path> --artifact <path>
ooo guardrails summarize-report --report <path>
```

## Dependency boundary

`guardrails-ai` is intentionally an environment dependency rather than vendored
code. If it is missing, validation commands fail with a clear installation
message. Install it in the plugin environment, for example:

```bash
pip install guardrails-ai
```

The MVP supports:

- `.rail` specs loaded with `Guard.for_rail(...)`;
- `.json` guard dictionaries loaded with `Guard.from_dict(...)`;
- known-output post-processing via `Guard.parse(llm_output=..., num_reasks=0)`.

The MVP does **not** execute Python config files, install Hub validators, start
Guardrails server mode, call remote LLMs, or expose arbitrary Guardrails CLI
passthrough. Those require separate trust paths and later lifecycle commands.

## Reports and handoffs

Reports include:

- Guardrails-native outcome fields: `validation_passed`, `validated_output`,
  `validation_summaries`, `reask`, and `error`;
- redacted raw-output references using `sha256` and `length`;
- Ouroboros result metadata: status, permissions used, capabilities used, and
  audit event names;
- provenance, ledger-event, state-update, and handoff sections that downstream
  workflows can consume.

Validation failure exits with code `1` by default so the command can act as an
acceptance gate. Use `--no-fail-on-validation-fail` when a report-only workflow
should return success after writing evidence.

All file paths are repository-relative and must stay inside the current working
repository. Absolute paths and `..` escapes are rejected.
