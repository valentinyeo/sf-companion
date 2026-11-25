Coverage: 16 of 16 features across 12 files.

# Companion verification map

`scripts/feature_coverage.py` derives every user-facing feature from source — the route union, the hub sections, the factory sections, the share handlers, the deployed Website, and the PR verifier picker invocation — and fails when a feature has no file here, a file covers a feature the source no longer has, or the coverage line above goes stale.

Run `../run.sh` from this directory, or `.claude/skills/verify-sf-companion/run.sh` from the repo root. Each run owns a disposable checkout copy and fresh browser contexts. Synthetic data comes from `../fixture.json` for the factory feed and `../fixture-hub/` for the hub content store, through the same files production reads. The fixture holds 30 days of shipping data, all seven KPI tiles, eight KPI notes, ten usage cards, every usage window, and five shipping notes; the hub store holds ten items per section. Those counts are the production floor in the Scale section below. A third launch, `sparse`, writes a copy of the same fixture with `usage.cards` emptied and `kpis.shipping` dropped, so the unavailability states are driven on a real feed rather than on a missing file. Every sub-feature id is a journey id: `run.sh --journeys=<ids>` drives only those journeys. Each feature file lists the source files it covers on its `Code paths:` line, so a diff selects its journeys, and its `Covers:` line names the features the coverage check counts.

## Features

- [Home](home.md) covers the front page, both hub sections, and the Factory and Usage handoffs.
- [Explorations](explorations.md) covers the explorations index, one stored item, and its scope.
- [Reports](reports.md) covers the reports index, one stored item, and its scope.
- [Stored items](items.md) covers item serving: GET, HEAD, missing, and invalid slugs.
- [Factory page](factory.md) covers entry, export time, navigation, layout, and the link to Usage.
- [Usage page](usage.md) covers the menu entry, every plan card, fixed 1h burn with no window picker, and the Windows disclosure.
- [KPI tiles](kpis.md) covers all seven tiles, their own windows, cues, and measurement details.
- [Shipping chart](shipping.md) covers the 30-date chart, cell sources, and stated omissions.
- [Empty and missing states](empty.md) covers a missing feed, a feed with no shipping block, a feed with no plan cards, the KPI unavailability notes, an empty hub, and the not-found page.
- [Anonymous access gate](access.md) covers the optional live Cloudflare Access redirect.
- [Share endpoint](share.md) covers publish, delete, auth, and input validation.
- [Verifier selection](verifier.md) covers the PR picker CLI, its GLM Flash choice, author-family exclusion, and rejected authors.

## Proof rules

Require successful builds and fourteen passing cases in `result.json` for a full run: twelve browser views, one share case, and one verifier-selection CLI case. The twelve are seeded, empty, and sparse at 1280×900 and 390×844 in light and dark. The share case drives the HTTP share API with a request context and opens no page, so it is a case, not a browser view. A scoped run passes only the cases its journeys drive. Every browser case saves its actions, dimensions, ARIA snapshot, and screenshots: `<case>.png` is the page the factory drives ended on and `<case>-final.png` is the last page it visited. Any console error, uncaught browser error, failed local response other than the expected 404, or horizontal overflow fails verification. Failed runs retain partial evidence and return a nonzero exit code. Do not call skipped checks verified.

A journey for a page the checkout does not declare sits in `result.json` under `skipped` with the missing route as the reason, so a base revision still proves every other journey. Every journey action in `result.json` names the journey it drove. The doctor readiness check that loads `/factory` before any journey runs is recorded with `journey: null`. The share and verifier-selection cases record their actions without a browser page. `verify.mjs` refuses to start when this map lists a sub-feature id that `verify.mjs` never gates with `wants("<id>")`, and it fails a run when a requested journey records no action. A listed journey with no evidence is a failed run, never a skipped check.

Every browser case also saves a Playwright trace, and `traces.json` names the trace files that cover each journey. A release needs that trace or video for each journey of every changed feature, and `scripts/release_gate.py` fails when one is missing, when the trace holds no recorded browser action, or when its case log never drove that journey. The live `access-anonymous` request, share journeys, and verifier-selection CLI run with no browser page, so they are listed as untraced with a reason rather than claimed as recorded.

The map covers Home, Explorations, Reports, Items, Factory, Usage, KPI tiles, Shipping, Empty states, Access, Share, and verifier selection. Stored items are served as the bytes kept in the content store, so the map does not claim site-styled item pages, authenticated production access, or deployed build parity.

## Caught bugs

[CAUGHT.md](../CAUGHT.md) logs the recent bugs a check caught before the owner saw them: one row per bug with the date, the pull request, what was wrong, which check caught it, and whether the owner saw it. The rows are why this map exists. A row is written from the pull request's `pstack-verifier` comments or, for a live defect, from the revert body, never from memory, and the log is evidence rather than a gate, so no check fails when a row is missing.

## Scale

The journeys start at the size production runs at, not at a toy size, so a journey that passes here still has the list lengths, chart rows and note counts a user meets. Production counts were measured on 2026-11-24 by the worker against the live site and exporter contract. The Fixture column is what `../fixture.json` and `../fixture-hub/` hold today. `scripts/check_fixture_scale.py` reads this table and fails when a fixture count falls below its production count, when the Fixture column no longer matches the fixture, or when a row is missing.

| Measure            | Production | Fixture |
| ------------------ | ---------- | ------- |
| Hub reports        | 9          | 10      |
| Hub explorations   | 1          | 10      |
| Usage cards        | 9          | 10      |
| Usage burn windows | 1          | 1       |
| KPI tiles          | 4          | 7       |
| KPI notes          | 8          | 8       |
| Shipping days      | 30         | 30      |
| Shipping omissions | 2          | 2       |
| Shipping notes     | 5          | 5       |

Re-measure after production changes:

1. Hub: open https://yeoux.net/reports/ and https://yeoux.net/explorations/ with an Access session and count the listed rows.
2. Feed: count the file the deployed build carries, `apps/web/content/feed/factory.json`, with `scripts/check_fixture_scale.py --measure --feed <path>`. Pass `--hub-index <path>` as well to count an exported hub index instead of reading the pages by hand.
3. Write the new counts into the Production column and the new date into the paragraph above, then grow the fixture until the check passes.
