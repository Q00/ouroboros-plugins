# Agent Skills command mapping

## Lifecycle aliases

| Upstream | Ouroboros | Target skill |
|---|---|---|
| `/spec` | `ooo agent-skills spec` | `spec-driven-development` |
| `/plan` | `ooo agent-skills plan` | `planning-and-task-breakdown` |
| `/build` | `ooo agent-skills build` | `incremental-implementation` |
| `/test` | `ooo agent-skills test` | `test-driven-development` |
| `/review` | `ooo agent-skills review` | `code-review-and-quality` |
| `/code-simplify` | `ooo agent-skills code-simplify` | `code-simplification` |
| `/ship` | `ooo agent-skills ship` | `shipping-and-launch` |

## Direct skills

All 23 upstream skill directories are exposed as `ooo agent-skills <skill>`.
The direct command names intentionally match the upstream directory names.

## Ship fan-out

`ship` records the upstream readiness fan-out personas:

- `code-reviewer`
- `security-auditor`
- `test-engineer`

Parallel execution is a runtime concern. Where the runtime cannot fan out, the
handoff remains valid as a sequential fallback checklist and go/no-go synthesis.
