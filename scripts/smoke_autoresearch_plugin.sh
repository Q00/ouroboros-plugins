#!/usr/bin/env bash
# Smoke-test the autoresearch plugin through the Ouroboros plugin manager.
#
# This is intentionally not wired into default CI: it requires an installed
# `ouroboros` CLI that supports UserLevel plugin dispatch and the v0.39.1+
# non-destructive permission prompt behavior. The script isolates lock/trust
# state under a temporary directory so it does not mutate the operator's normal
# ~/.ouroboros plugin installation.

set -euo pipefail

if ! command -v ouroboros >/dev/null 2>&1; then
  echo "error: ouroboros CLI not found on PATH" >&2
  exit 127
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/autoresearch-smoke.XXXXXX")"
cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

plugin_home_root="$tmp/plugin-homes"
lockfile="$tmp/plugins.lock"
trust_root="$tmp/trust"
catalog_state="$tmp/plugin-catalogs.json"
target_repo="$tmp/autoresearch-checkout"
mkdir -p "$target_repo"

cat > "$target_repo/program.md" <<'PROGRAM'
Improve validation bpb while preserving a bounded, reproducible experiment log.
PROGRAM
cat > "$target_repo/prepare.py" <<'PREPARE'
MAX_SEQ_LEN = 1024
PREPARE
cat > "$target_repo/train.py" <<'TRAIN'
print("val_bpb=1.0")
TRAIN

# Decline the install-time grant prompt if it appears; explicit trust commands
# below keep the smoke deterministic across interactive and non-interactive CLIs.
printf 'n\n' | ouroboros plugin add "$repo_root" \
  --plugin autoresearch \
  --plugin-home-root "$plugin_home_root" \
  --lockfile "$lockfile" \
  --trust-root "$trust_root" \
  --catalog-state "$catalog_state"

ouroboros plugin trust autoresearch --scope filesystem:read \
  --lockfile "$lockfile" \
  --trust-root "$trust_root"
ouroboros plugin trust autoresearch --scope filesystem:write \
  --lockfile "$lockfile" \
  --trust-root "$trust_root"

export OUROBOROS_PLUGIN_LOCKFILE="$lockfile"
export OUROBOROS_PLUGIN_TRUST_ROOT="$trust_root"
# Python plugin entrypoints run from the installed plugin home. Prevent
# interpreter bytecode caches from mutating the trusted artifact between the
# inspect and prepare invocations.
export PYTHONDONTWRITEBYTECODE=1

ouroboros auto-research inspect "$target_repo"
ouroboros auto-research prepare "$target_repo" \
  --goal "Improve validation bpb in a bounded smoke run" \
  --max-experiments 1 \
  --experiment-seconds 30

python3 - "$target_repo" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
handoff = root / ".ouroboros" / "autoresearch" / "handoff.json"
seed = root / ".ouroboros" / "autoresearch" / "seed.md"
auto_goal = root / ".ouroboros" / "autoresearch" / "auto_goal.txt"
for path in (handoff, seed, auto_goal):
    if not path.is_file():
        raise SystemExit(f"missing smoke artifact: {path}")
payload = json.loads(handoff.read_text())
assert payload["status"] == "prepared"
assert payload["ooo_auto"]["max_experiments"] == 1
assert payload["ooo_auto"]["experiment_seconds"] == 30
assert payload["provenance"]["files"]["target"]["path"] == "train.py"
assert "ouroboros_capability_mapping" in payload
PY

echo "autoresearch plugin-manager smoke passed"
