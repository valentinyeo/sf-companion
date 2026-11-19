# Shipping chart

PRs shipped vs plan burn is a scrollable table of the last 30 UTC dates: merged PRs, observed weekly quota points per plan, attributed pounds, and pounds per PR. Every cell expands to its source and window, and a plan with no readings is stated as omitted rather than shown as zero.

Covers: factory:prs-shipped-vs-plan-burn

Code paths: apps/web/src/features/factory.ts, apps/web/src/content/feed.ts

## Sub-features

- `shipping-chart` shows all 30 dated rows with their columns.
- `shipping-source` expands a measured cell to its source and UTC window.
- `shipping-omission` states each plan with no readings as omitted.

## How to get to it (user POV)

- Open Factory with a feed present.
- Read the PRs shipped vs plan burn section. Expand any value for its source. Scroll the chart sideways on a phone.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The fixture carries 30 dates, from 2026-10-17 to 2026-11-15, with claude and codex quota readings and grok and opencode omitted.

- Chart. Require the heading `PRs shipped vs plan burn` and the region `Daily shipping and burn chart`. Require the caption `Last 30 UTC dates · fleet merges, observed weekly quota points and attributed £`.
- Rows. Require row headers `2026-11-15` and `2026-10-17`, and exactly 30 row headers in the region.
- Source. In the 2026-11-15 row, click `2 PRs` and require `GitHub search · fleet mergedAt` visible, plus the day's UTC window.
- Omission. Require `Grok, OpenCode omitted: pacing sampler retired on 2026-11-15.` and no `Grok pts` column header.
- Proof. The per-case screenshot shows the chart head and the expanded cell.

## Gotchas

- The chart scrolls inside its own region on a 390-wide viewport. The document itself must not overflow; the case recorder checks that.
- A missing cell reads `Unavailable` with a reason, never a zero.
- Rows are rendered newest first, so the newest date is the first row, not the last.
