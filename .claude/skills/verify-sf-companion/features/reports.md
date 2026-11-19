# Reports

Reports is the index of finished client reports, newest first, and each row opens the stored report.

Covers: section:reports

Code paths: apps/web/src/content/hub.ts, apps/web/src/content/item.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/entry.server.ts

## Sub-features

- `reports-index` lists every report with its project and date.
- `reports-index-empty` says the index holds nothing when no report is stored.
- `reports-index-trailing-slash` serves the same index at `/reports/` with the trailing slash.
- `reports-item` opens one stored report from its index row.
- `reports-scope` keeps exploration items off the index.

## How to get to it (user POV)

- Open `/reports`.
- Choose Reports in Primary navigation.
- Choose `All 10` under the Reports heading on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. `fixture-hub/` supplies ten reports and ten explorations.

- Index. Choose Reports in Primary navigation. Require the `Reports` heading and `10 items.`, plus the rows `yeo-ux · 2026-11-12` and `ezyfit · 2026-10-30`.
- Trailing slash. `GET /reports/` must answer 200 with the `Reports` heading and `10 items.`, not a 400.
- Item. Choose the `Client pricing review` row. Require `Fixture client pricing body.` at HTTP 200 and no site navigation. Save `hub-report-item-<case>.png` and `hub-report-item-<case>.aria.txt`.
- Scope. Require no `Motion study` link on the index.
- Empty (`reports-index-empty`). In the empty launch, require `No reports yet.` and `0 items.`

## Gotchas

- Uploading and deleting go through `PUT` and `DELETE` on the same URL with `Authorization: Bearer <SHARE_TOKEN>`; the hub reads the same store, so an upload appears on the index after the next page load. That path is mapped in `share.md`.
- A local launch keeps uploads in `apps/web/content/hub/`. Nothing writes to R2 unless a `CONTENT` binding exists.
