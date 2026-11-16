# Companion verification map

Run `../run.sh` from this directory, or `.claude/skills/verify-sf-companion/run.sh` from the repo root. Each run owns a disposable checkout copy and fresh browser contexts. Synthetic data comes from `../fixture.json`, through the same build-time feed file as production.

## Features

- [Factory readings and empty state](factory.md) covers navigation, plan readings, KPI provenance, and a missing feed.
- [Usage windows and details](usage.md) covers every window button, changed burn readings, fixed KPI readings, and disclosures.
- [Anonymous access gate](access.md) covers the optional live Cloudflare Access redirect.

## Proof rules

Require successful builds and eight passing browser cases in `result.json`. Every browser case saves its actions, dimensions, ARIA snapshot, and screenshot. Any console error, uncaught browser error, failed local response, or horizontal overflow fails verification. Failed runs retain partial evidence and return a nonzero exit code. Do not call skipped checks verified.

The app also has Home, Explorations, Reports, and entry reader routes. This initial map covers the factory goal. It does not claim entry content, Copy link, authenticated production access, or deployed build parity.
