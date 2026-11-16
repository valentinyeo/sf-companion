#!/usr/bin/env bash
set -euo pipefail
feed=apps/web/content/feed/factory.json
web_build_hash() {
  pnpm exec turbo run build --filter=@sf-companion/web --dry=json \
    | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const t=JSON.parse(s).tasks.find(x=>x.taskId==="@sf-companion/web#build");console.log(t.hash)})'
}
backup=""
if [ -f "$feed" ]; then backup=$(mktemp); cp "$feed" "$backup"; fi
restore() { if [ -n "$backup" ]; then mv "$backup" "$feed"; else rm -f "$feed"; fi; }
trap restore EXIT
echo '{"feedRebuildProbe":1}' > "$feed"
first=$(web_build_hash)
echo '{"feedRebuildProbe":2}' > "$feed"
second=$(web_build_hash)
if [ "$first" = "$second" ]; then
  echo "web build hash ignores $feed: a numbers-only refresh would serve stale Factory data" >&2
  exit 1
fi
echo "feed change rebuilds web: $first -> $second"
