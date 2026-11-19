# Home

Home is the hub front page: the site title, an Explorations section, a Reports section, and Factory and Usage handoffs. Each hub section shows its five newest rows and a link to its full list.

Covers: route:Home

Code paths: apps/web/src/features/page.ts, apps/web/src/content/item.ts, apps/web/src/features/route.ts, apps/web/src/entry.server.ts

## Sub-features

- `home-sections` shows both hub sections with their newest rows and the Factory and Usage handoffs.
- `home-links` sends each row to its stored item and each section heading to its index.

## How to get to it (user POV)

- Open `/`.
- Choose the site name in Primary navigation from any page.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. `fixture-hub/` supplies ten explorations and ten reports. Home lists five per section.

- Seeded. Require the `Software Factory Companion` heading, the `Explorations`, `Reports`, `Factory`, and `Usage` headings, the newest report rows `Client pricing review`, `Verifier scope audit`, `Factory feed notes`, `Retainer summary`, `Build cost review`, and the newest exploration rows `Route parser notes`, `Feed schema sketch`, `Motion study`, `Hydration check`, `Style tokens study`.
- Hidden rows. Require no link to `Support volume report` or `Nightly run log`; those sit below the five-row limit.
- Counts. Require exactly two `All 10` links, one under each hub section.
- Rows. Require `yeo-ux · 2026-11-12` beside the pricing row.
- Section links. Choose `All 10` inside the Reports section and require the Reports index. Then choose `All 10` inside the Explorations section and require the Explorations index.
- Row links. Choose `Client pricing review` and require its stored body. Choose `Motion study` and require its stored body.
- Proof. Read `hub-home-<case>.png` for the front page.

## Gotchas

- Rows come from the hub content store. Local launches read `apps/web/content/hub/`, which stands in for the R2 bucket; a deployed Worker reads R2 through its `CONTENT` binding.
- The seeded titles are synthetic. They are not client work.
- Rows are ordered by item date, newest first, and the limit is five per section, so an older title is absent by design, not broken.
