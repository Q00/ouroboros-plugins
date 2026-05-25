#!/usr/bin/env bash
# Issue #28 — Superpowers AgentOS verification
#
# Reproduces the L0/L1/L2/L2b verification surface from the issue thread and
# optionally launches the L3a downstream-handoff smoke (ouroboros auto
# --skip-run) in the background.
#
# Usage:
#   bash scripts/verify_issue28_superpowers.sh
#
# Environment overrides:
#   SOURCE_REPO          path to the canonical clone (default: this repo)
#   WORKTREE             scratch worktree pinned to origin/main
#   EVIDENCE_ROOT        where logs + artifacts land
#   KEEP_WORKTREE=1      reuse an existing worktree dir
#   RUN_L3A=1            also launch ouroboros auto --skip-run in background
#   L3A_INTERVIEW_ROUNDS interview round budget for L3a (default: 6)

set -euo pipefail

SOURCE_REPO="${SOURCE_REPO:-/Users/jh0927/ouroboros-plugins}"
WORKTREE="${WORKTREE:-/tmp/ouroboros-plugins-issue28-verify}"
EVIDENCE_ROOT="${EVIDENCE_ROOT:-/tmp/superpowers-agentos-e2e-$(date -u +%Y%m%dT%H%M%SZ)}"
KEEP_WORKTREE="${KEEP_WORKTREE:-0}"
RUN_L3A="${RUN_L3A:-0}"
L3A_INTERVIEW_ROUNDS="${L3A_INTERVIEW_ROUNDS:-6}"

export SOURCE_REPO WORKTREE EVIDENCE_ROOT

log() { printf '\n== %s ==\n' "$*"; }

run_logged() {
  local logfile="$1"
  shift
  mkdir -p "$(dirname "$logfile")"
  printf '+ %q ' "$@" | tee "$logfile.cmd" >/dev/null
  printf '\n' | tee -a "$logfile.cmd" >/dev/null
  "$@" 2>&1 | tee "$logfile"
}

log "Issue #28 superpowers verification"
echo "source repo: $SOURCE_REPO"
echo "worktree:    $WORKTREE"
echo "evidence:    $EVIDENCE_ROOT"
echo "run L3a:     $RUN_L3A"

mkdir -p "$EVIDENCE_ROOT/logs"

if [ ! -d "$SOURCE_REPO/.git" ]; then
  echo "ERROR: SOURCE_REPO is not a git repository: $SOURCE_REPO" >&2
  exit 2
fi

cd "$SOURCE_REPO"
run_logged "$EVIDENCE_ROOT/logs/git-fetch.log" git fetch origin main --prune

if [ -d "$WORKTREE" ]; then
  if [ "$KEEP_WORKTREE" = "1" ]; then
    echo "Keeping existing worktree because KEEP_WORKTREE=1: $WORKTREE"
  else
    echo "Removing existing worktree dir: $WORKTREE"
    git worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"
  fi
fi

if [ ! -d "$WORKTREE/.git" ]; then
  run_logged "$EVIDENCE_ROOT/logs/git-worktree-add.log" git worktree add "$WORKTREE" origin/main
fi

cd "$WORKTREE"

log "environment"
{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo=$WORKTREE"
  echo "commit=$(git rev-parse HEAD)"
  echo "branch=$(git branch --show-current || true)"
  echo "python=$(python3 --version 2>&1)"
  echo "ouroboros=$(command -v ouroboros || true)"
  echo "ouroboros_version=$(ouroboros --version 2>&1 | tail -n1 | tr -d '\n' || true)"
  echo "ooo=$(command -v ooo || true)"
} | tee "$EVIDENCE_ROOT/environment.txt"

log "setup venv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
run_logged "$EVIDENCE_ROOT/logs/pip-install.log" pip install -r requirements-dev.txt

# ----------------------------------------------------------------------------
# L0 — contract + tests
# ----------------------------------------------------------------------------
log "L0 — contract + tests"
run_logged "$EVIDENCE_ROOT/logs/compileall.log" python3 -m compileall -q plugins/superpowers/superpowers_ouroboros
run_logged "$EVIDENCE_ROOT/logs/validate-contract.log" python3 scripts/validate_contract.py
run_logged "$EVIDENCE_ROOT/logs/unittest.log" python3 -m unittest tests.test_superpowers_plugin tests.test_validator tests.test_autoresearch_plugin

L0_RESULT="PASS"

# ----------------------------------------------------------------------------
# L1 — plugin lifecycle / trust gate
# ----------------------------------------------------------------------------
log "L1 — plugin lifecycle / trust gate"
L1_RESULT="SKIPPED - ouroboros CLI missing"
if command -v ouroboros >/dev/null 2>&1; then
  run_logged "$EVIDENCE_ROOT/plugin-add.log" ouroboros plugin add . --plugin superpowers \
    --plugin-home-root "$EVIDENCE_ROOT/plugin-home" \
    --trust-root "$EVIDENCE_ROOT/trust-root" \
    --cache-root "$EVIDENCE_ROOT/cache" \
    --lockfile "$EVIDENCE_ROOT/plugins.lock" \
    --catalog-state "$EVIDENCE_ROOT/plugin-catalogs.json"

  run_logged "$EVIDENCE_ROOT/plugin-inspect-before-trust.log" ouroboros plugin inspect superpowers \
    --lockfile "$EVIDENCE_ROOT/plugins.lock" \
    --trust-root "$EVIDENCE_ROOT/trust-root"

  run_logged "$EVIDENCE_ROOT/plugin-trust.log" ouroboros plugin trust superpowers \
    --scope filesystem:read \
    --scope filesystem:write \
    --lockfile "$EVIDENCE_ROOT/plugins.lock" \
    --trust-root "$EVIDENCE_ROOT/trust-root" \
    --audit-log "$EVIDENCE_ROOT/plugin-trust-audit.jsonl" \
    --granted-by user:issue28-verify

  run_logged "$EVIDENCE_ROOT/plugin-inspect-after-trust.log" ouroboros plugin inspect superpowers \
    --lockfile "$EVIDENCE_ROOT/plugins.lock" \
    --trust-root "$EVIDENCE_ROOT/trust-root"

  run_logged "$EVIDENCE_ROOT/plugin-list-after-trust.json" ouroboros plugin list \
    --lockfile "$EVIDENCE_ROOT/plugins.lock" \
    --trust-root "$EVIDENCE_ROOT/trust-root" \
    --json

  python3 - <<'PY' | tee "$EVIDENCE_ROOT/trust-audit-schema-validation.log"
import json, os
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("schemas/0.1/audit-event.schema.json").read_text())
validator = Draft202012Validator(schema)
events_path = Path(os.environ["EVIDENCE_ROOT"]) / "plugin-trust-audit.jsonl"
events = []
errors = []
for i, line in enumerate(events_path.read_text().splitlines(), 1):
    if not line.strip():
        continue
    event = json.loads(line)
    payload = event.get("payload", event)
    events.append(event.get("event_type") or event.get("type") or event.get("name"))
    line_errors = list(validator.iter_errors(payload))
    if line_errors:
        errors.append({"line": i, "errors": [e.message for e in line_errors]})
status = "passed" if not errors else "failed"
print(json.dumps({"events": events, "schema_errors": errors, "status": status}, indent=2))
assert status == "passed", "trust audit schema validation failed"
PY

  L1_RESULT="PASS"
else
  echo "ouroboros CLI not found; skipping plugin lifecycle" | tee "$EVIDENCE_ROOT/plugin-lifecycle-skipped.log"
fi

# ----------------------------------------------------------------------------
# L2 — installed plugin invocation, artifacts, provenance, audit
# ----------------------------------------------------------------------------
log "L2 — superpowers test-driven-development invocation"

if [ -d "$EVIDENCE_ROOT/plugin-home/superpowers" ]; then
  PLUGIN_HOME="$EVIDENCE_ROOT/plugin-home/superpowers"
else
  PLUGIN_HOME="$WORKTREE/plugins/superpowers"
fi
echo "plugin home in use: $PLUGIN_HOME"

PYTHONPATH="$PLUGIN_HOME" \
  python3 -m superpowers_ouroboros \
  --output-dir "$EVIDENCE_ROOT/work/.omx/superpowers" \
  test-driven-development \
  --goal 'Add retry behavior' \
  --input 'network client' \
  > "$EVIDENCE_ROOT/command-output.json"

cat "$EVIDENCE_ROOT/command-output.json"

python3 - <<'PY' | tee "$EVIDENCE_ROOT/artifact-audit-validation.log"
import json, os
from pathlib import Path
from jsonschema import Draft202012Validator

evidence = Path(os.environ["EVIDENCE_ROOT"])
worktree = Path(os.environ["WORKTREE"])
payload = json.loads((evidence / "command-output.json").read_text())
run_dir = Path(payload["run_dir"])

required = ["invocation.json", "provenance.json", "handoff.md",
            "seed.md", "evidence.json", "audit.jsonl"]
missing = [f for f in required if not (run_dir / f).is_file()]
assert not missing, f"missing artifacts: {missing}"

schema = json.loads((worktree / "schemas/0.1/audit-event.schema.json").read_text())
validator = Draft202012Validator(schema)

audit_events = []
audit_errors = []
for i, line in enumerate((run_dir / "audit.jsonl").read_text().splitlines(), 1):
    if not line.strip():
        continue
    event = json.loads(line)
    audit_events.append(event.get("event_type") or event.get("type") or event.get("name"))
    line_errors = list(validator.iter_errors(event))
    if line_errors:
        audit_errors.append({"line": i, "errors": [e.message for e in line_errors]})

provenance = json.loads((run_dir / "provenance.json").read_text())
prov_required = ["upstream_repo", "upstream_version", "upstream_commit",
                 "upstream_license", "upstream_skill"]
prov_missing = [f for f in prov_required if f not in provenance]

invocation = json.loads((run_dir / "invocation.json").read_text())
raw_goal_stored = invocation.get("goal") not in (None, "")
raw_input_stored = invocation.get("input") not in (None, "")

result = {
    "status": "passed" if not audit_errors and not prov_missing else "failed",
    "run_dir": str(run_dir),
    "audit_events": audit_events,
    "audit_schema_errors": audit_errors,
    "provenance_missing_fields": prov_missing,
    "raw_goal_stored": raw_goal_stored,
    "raw_input_stored": raw_input_stored,
    "upstream_skill": provenance.get("upstream_skill"),
}
print(json.dumps(result, indent=2))
assert result["status"] == "passed", "L2 validation failed"

bundle = evidence / "run-artifacts"
bundle.mkdir(exist_ok=True)
for f in required:
    (bundle / f).write_bytes((run_dir / f).read_bytes())
PY

L2_RESULT="PASS"

# ----------------------------------------------------------------------------
# L2b — destructive-described workflow guard
# ----------------------------------------------------------------------------
log "L2b — finishing-a-development-branch report-only guard"

PYTHONPATH="$PLUGIN_HOME" \
  python3 -m superpowers_ouroboros \
  --output-dir "$EVIDENCE_ROOT/work/.omx/superpowers-finish" \
  finishing-a-development-branch \
  --input 'feature/example' \
  > "$EVIDENCE_ROOT/finishing-output.json"

python3 - <<'PY' | tee "$EVIDENCE_ROOT/destructive-guard-validation.log"
import json, os
from pathlib import Path

evidence = Path(os.environ["EVIDENCE_ROOT"])
payload = json.loads((evidence / "finishing-output.json").read_text())
run_dir = Path(payload["run_dir"])

handoff = (run_dir / "handoff.md").read_text()
evidence_json = json.loads((run_dir / "evidence.json").read_text())

# Report-only guard: handoff must explicitly state that destructive upstream
# actions are not performed by this command.
report_only_signal = any(
    needle in handoff.lower()
    for needle in (
        "report-only",
        "report only",
        "do not perform",
        "no merge",
        "non-destructive",
        "destructive upstream actions are report-only",
    )
)

result = {
    "status": "passed" if report_only_signal else "failed",
    "run_dir": str(run_dir),
    "contains_report_only_note": report_only_signal,
    "evidence_keys": sorted(evidence_json.keys()) if isinstance(evidence_json, dict) else None,
}
print(json.dumps(result, indent=2))
assert result["status"] == "passed", "L2b destructive guard failed"
PY

L2B_RESULT="PASS"

# ----------------------------------------------------------------------------
# L3a — downstream `ouroboros auto --skip-run` handoff consumption (optional)
# ----------------------------------------------------------------------------
L3A_RESULT="SKIPPED - set RUN_L3A=1 to enable"
L3A_LOG="$EVIDENCE_ROOT/l3a-auto.log"
L3A_OUT="$EVIDENCE_ROOT/l3a-auto.out"
L3A_PID_FILE="$EVIDENCE_ROOT/l3a-auto.pid"
L3A_STATUS_FILE="$EVIDENCE_ROOT/l3a-auto.status"

if [ "$RUN_L3A" = "1" ]; then
  if ! command -v ouroboros >/dev/null 2>&1; then
    L3A_RESULT="SKIPPED - ouroboros CLI missing"
  else
    log "L3a — launching ouroboros auto --skip-run in background"

    RUN_DIR="$(python3 -c 'import json,os; print(json.load(open(os.environ["EVIDENCE_ROOT"]+"/command-output.json"))["run_dir"])')"
    HANDOFF_PATH="$RUN_DIR/handoff.md"

    L3A_PROMPT=$(cat <<EOM
Use the prepared Superpowers handoff at $HANDOFF_PATH to author an A-grade
execution Seed for adding retry behavior to a network client. Preserve
upstream provenance and verification evidence.

Fill these interview slots from the handoff:
- actors: Ouroboros operator + Superpowers TDD skill
- inputs: handoff.md and seed.md from $RUN_DIR
- outputs: Seed file and verification plan
- constraints: filesystem:read and filesystem:write only; no network or shell
- non_goals: live merge, push, branch deletion, PR mutation
- failure_modes: retry storm; idempotency violation; missing audit event
- runtime_context: codex runtime, dry-run preferred
EOM
)

    nohup ouroboros auto \
      --skip-run \
      --max-interview-rounds "$L3A_INTERVIEW_ROUNDS" \
      --runtime codex \
      "$L3A_PROMPT" \
      >"$L3A_OUT" 2>"$L3A_LOG" &
    L3A_PID=$!
    echo "$L3A_PID" > "$L3A_PID_FILE"
    echo "started" > "$L3A_STATUS_FILE"
    echo "L3a auto pid=$L3A_PID"
    echo "L3a auto log=$L3A_LOG"
    L3A_RESULT="LAUNCHED pid=$L3A_PID"
  fi
fi

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
log "summary"

cat > "$EVIDENCE_ROOT/summary.md" <<EOF
# superpowers Issue #28 AgentOS verification

- Evidence root: \`$EVIDENCE_ROOT\`
- Worktree: \`$WORKTREE\`
- Commit: \`$(git rev-parse HEAD)\`
- Ouroboros CLI: \`$(command -v ouroboros || echo missing)\`
- ooo dispatcher: \`$(command -v ooo || echo missing)\`

## Results

| Level | Outcome |
|-------|---------|
| L0 contract + tests | $L0_RESULT |
| L1 plugin lifecycle + trust | $L1_RESULT |
| L2 invocation + artifacts + provenance | $L2_RESULT |
| L2b destructive guard | $L2B_RESULT |
| L3a auto --skip-run | $L3A_RESULT |

## Dispatcher namespace

The Ouroboros CLI v0.39.x does not yet expose \`ouroboros superpowers <skill>\`
or \`ooo superpowers <skill>\` as a command namespace.
The L2 evidence above invokes the installed plugin via
\`python3 -m superpowers_ouroboros\`, matching the manifest \`entrypoint\`.

This script intentionally does not gate verdicts on dispatcher availability.
Track that gap as a separate follow-up issue.

EOF

if [ "$RUN_L3A" = "1" ]; then
cat >> "$EVIDENCE_ROOT/summary.md" <<EOF
## L3a follow-up

The downstream \`ouroboros auto --skip-run\` job was launched in the background.
Poll its status with:

    ps -p \$(cat $L3A_PID_FILE) || echo finished
    tail -n 100 $L3A_OUT
    tail -n 100 $L3A_LOG

When it finishes, append the final exit code to:

    $L3A_STATUS_FILE
EOF
fi

cat "$EVIDENCE_ROOT/summary.md"

log "DONE"
echo "Evidence root: $EVIDENCE_ROOT"
