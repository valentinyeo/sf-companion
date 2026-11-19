# Companion verification map

Run `../run.sh` from this directory, or `.claude/skills/verify-sf-companion/run.sh` from the repo root. Each run owns a disposable checkout copy and fresh browser contexts. Synthetic data comes from `../fixture.json` for the factory feed and `../fixture-hub/` for the hub content store, through the same files production reads. Every sub-feature id is a journey id: `run.sh --journeys=<ids>` drives only those journeys. Each feature file lists the source files it covers on its `Code paths:` line, so a diff selects its journeys.

## Features

- [Home](home.md) covers the hub front page, both sections, and an empty hub.
- [Explorations](explorations.md) covers the explorations index and one stored item.
- [Reports](reports.md) covers the reports index and one stored report.
- [Factory readings and empty state](factory.md) covers navigation, plan readings, KPI provenance, and a missing feed.
- [Usage windows and details](usage.md) covers every window button, changed burn readings, fixed KPI readings, and disclosures.
- [Anonymous access gate](access.md) covers the optional live Cloudflare Access redirect.

## Proof rules

Require successful builds and eight passing browser cases in `result.json` for a full run. A scoped run passes only the cases its journeys drive. Every browser case saves its actions, dimensions, ARIA snapshot, and screenshot. Any console error, uncaught browser error, failed local response, or horizontal overflow fails verification. Failed runs retain partial evidence and return a nonzero exit code. Do not call skipped checks verified.

Every action in `result.json` names the journey it drove. `verify.mjs` refuses to start when this map lists a sub-feature id that `verify.mjs` never gates with `wants("<id>")`, and it fails a run when a requested journey records no action. A listed journey with no evidence is a failed run, never a skipped check.

The map covers Home, Explorations, Reports, and Factory. Stored items are served as the bytes kept in the content store, so the map does not claim site-styled item pages, authenticated production access, or deployed build parity.
