# Reports

Reports is the index of finished client reports, newest first, and each row opens the stored report.

Code paths: apps/web/src/content/hub.ts, apps/web/src/content/item.ts, apps/web/src/content/bucket.ts, apps/web/src/content/share.ts, apps/web/src/features/hub.stylex.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/entry.server.ts

## Sub-features

- `reports-index` lists report items with project and date.
- `reports-item` serves one stored report at `/reports/<slug>`.
- `reports-scope` keeps exploration items off the index.

## How to get to it (user POV)

- Open `/reports`.
- Choose Reports in Primary navigation.
- Choose `All N` under the Reports heading on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. `fixture-hub/` supplies two reports and one exploration.

- Index. Require the `Reports` heading, `2 items.`, `Client pricing review` with `yeo-ux · 2026-11-12`, and `Retainer summary` with `ezyfit · 2026-10-30`.
- Item. Open `/reports/4b7c1d2e-client-pricing.html` and require `Fixture client pricing body.` at HTTP 200. The body is the stored artefact byte for byte, so the page has no site navigation. Save `hub-report-item-<case>.png` and `hub-report-item-<case>.aria.txt`.
- Empty. Require `No reports yet.` and `0 items.`

## Gotchas

- Uploading and deleting go through `PUT` and `DELETE` on the same URL with `Authorization: Bearer <SHARE_TOKEN>`; the hub reads the same store, so an upload appears on the index after the next page load.
- A local launch keeps uploads in `apps/web/content/hub/`. Nothing writes to R2 unless a `CONTENT` binding exists.
