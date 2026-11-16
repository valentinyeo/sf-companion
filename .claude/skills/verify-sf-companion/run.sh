#!/usr/bin/env bash
set -euo pipefail
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --live ) ]]; then
  echo "Usage: $0 [--live]" >&2
  exit 2
fi
skill=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd "$skill/../../.." && pwd)
if [[ -n ${PROOF_DIR:-} ]]; then
  [[ "$PROOF_DIR" = /* ]] || { echo 'PROOF_DIR must be absolute' >&2; exit 2; }
  mkdir -- "$PROOF_DIR"
else
  PROOF_DIR=$(mktemp -d /tmp/sf-companion-proof.XXXXXX)
fi
export PROOF_DIR
PROOF_DIR=$(realpath "$PROOF_DIR")
export PROOF_DIR
case "$PROOF_DIR/" in "$repo/"*) echo 'Proof must be outside the checkout' >&2; exit 2;; esac
printf 'Proof: %s\n' "$PROOF_DIR"
printf '%s\n' '{"status":"failed","error":"Bootstrap incomplete; inspect install.log and tools.log"}' > "$PROOF_DIR/result.json"
scratch=$(mktemp -d /tmp/sf-companion-verify.XXXXXX)
runner=
cleanup() {
  if [[ -n "$runner" ]]; then
    kill -TERM "$runner" 2>/dev/null || true
    wait "$runner" 2>/dev/null || true
  fi
  rm -rf -- "$scratch"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$scratch/site" "$scratch/tools"
tar -C "$repo" --exclude=.git --exclude=node_modules --exclude=dist \
  --exclude=.turbo --exclude=.alchemy --exclude=.agent_sources/github.com \
  --exclude=.env --exclude='.env.*local' --exclude=apps/web/content/feed/factory.json \
  -cf - . | tar -C "$scratch/site" -xf -
git -C "$repo" rev-parse HEAD > "$PROOF_DIR/revision.txt"
git -C "$repo" diff --binary HEAD > "$PROOF_DIR/worktree.patch"
cp -R "$skill" "$PROOF_DIR/skill"
(cd "$scratch/site" && pnpm install --frozen-lockfile --ignore-scripts) > "$PROOF_DIR/install.log" 2>&1
pnpm --dir "$scratch/tools" add --save-exact --ignore-scripts playwright@1.65.1 > "$PROOF_DIR/tools.log" 2>&1
pnpm --dir "$scratch/tools" exec playwright install chromium >> "$PROOF_DIR/tools.log" 2>&1
node "$skill/verify.mjs" "$scratch/site" "$scratch/tools/node_modules/playwright/index.mjs" "${1:-}" &
runner=$!
wait "$runner"
runner=
