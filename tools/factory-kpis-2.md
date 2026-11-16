# Remaining factory numbers (SOFT-2546)

## Goal

Show real factory output and waste on `/factory/`, using the existing tile contract and read-only sources. Missing facts stay explained omissions, never estimated zeros.

## Work plan

- [x] Read the Rat Stack principles index and trace the exporter, tile schema, and source adapters.
- [x] Blocking first steps. Inspect source shapes before selecting metrics.
- [x] Independent workstreams. No delegation requested; keep the coupled exporter and contract in one session.
- [x] Shared mutable state. Work only in `/tmp/sf-2546`; do not write to Hypertask, production feeds, or the hourly checkout.
- [x] Smallest safe decomposition. Reuse the tile registry and omission path instead of introducing a new reporting store.
- [x] Open the draft PR before implementing collectors.
- [x] Add available sources and seeded tile-isolation tests.
- [x] Run Python tests and `pnpm run check` before each push. Full CI stays on GitHub-hosted runners.
- [x] Record complete live source coverage and omissions here and in the PR body.

## Data ownership

GitHub owns PR timestamps and Actions results. Fleet owns live chat observations, identity-gap rules, and slot decisions. Hypertask owns ticket transitions. The exporter is the only writer of the derived feed; this change does not add a ledger or replace upstream facts with update dates.

## Decisions and evidence

| Decision | Why | Evidence |
| --- | --- | --- |
| Extend the existing tile contract with `merges`, `identity`, and `ci` | Model the Domain keeps the existing source registry and schema in charge | Python validator and Effect schema accept the same seven IDs |
| Keep missing facts as omission notes or explicit missing sub-values | Store Source Facts and Keep Unknown Distinct rule out estimated zeros | Seeded source-failure, empty-cohort, unknown-failure, and missing-receipt tests |
| Reuse one PR read | Merge and verifier tiles use the same authority and snapshot | Fixture isolation changes PR creation time without changing verifier or CI output |
| Use complete rolling 24h CI cohorts, seven-day merge throughput | Weekly Actions history is too large for an hourly health reading; no sampling is hidden | A 2.5-hour Hypertask slice alone returned 873 runs |
| Page the API explicitly and batch failure annotations | Installed `gh` has no `--slurp`; Actions search caps each range at 1,000 runs | Live CLI rejection, partition-boundary test, and annotation-overflow test |
| Inspect credential-file existence only | Solo-wake checks existence, not file contents | Live inventory gave 11/15 matched chats; seeded extraction test exports no token contents or credential paths |
| Do not publish partial escapes or guessed slots | Numerators and coordinator boundaries must be real | Board 11514 read returned access denied; installed `fleet/slots` has no saved tick output |

An early fleet PR read measured 28 merges in 24h, 812 in 7d, and 34.0 median open-to-merge minutes. These are source observations from this session, not fixed values in the feed. The complete 18-repository CI read measured 3,365 completed runs in 24h, 32 confirmed infrastructure failures, zero confirmed code failures, and 253 unclassified failures. Only 1/28 merged PRs had an exact-SHA successful Production receipt, with an observed 4.9-minute merge-to-receipt median. That is partial deployment coverage, not a whole-fleet latency claim.

## Omitted tiles

- Delivered tickets (1), lead time (2), rework and reopen percentage (6), and cost per delivered ticket (8) remain blocked by [HYCI-9390](https://app.hypertask.ai/detail/project-15/9390). No update-date substitution or zero-cost inference is made.
- Escapes (5) is omitted because complete bug or incident PR-link coverage cannot be read across the three boards. The live board 11514 read was denied. A revert-only rate would be incomplete.
- Workers versus slots (10) is omitted because `fleet/slots` stores no per-coordinator tick receipts. Its default cap is not a fleet-wide cap; busy chats are not an authoritative worker count or shortfall reason.

## Verification

- 23 focused Python tests pass, including per-tile seeded isolation and complete-source failure handling.
- The three focused Factory page Scene tests pass with the new IDs, values, provenance, and missing-data explanation.
- `pnpm run check` passes. No TypeScript comments were added.
- Full checks, tests, and build belong to GitHub-hosted CI. An independent pstack verifier is still required before any merge.

[Draft PR 4](https://github.com/valentinyeo/sf-companion/pull/4) was opened before collector implementation. No production checkout, deployed feed, Hypertask state, certificates, or system proxies were changed.
