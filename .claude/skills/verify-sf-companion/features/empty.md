# Empty and missing states

The site says what is missing instead of rendering an empty frame or an invented zero. A missing feed, a section or block the feed does not carry, an empty hub section, and an unknown URL each get their own explicit message.

Covers: factory:no-feed, route:NotFound

Code paths: apps/web/src/features/factory.ts, apps/web/src/features/usage.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/content/feed.ts, apps/web/src/content/hub.ts, apps/web/src/content/item.ts

## Sub-features

- `factory-empty` shows the factory shell with no numbers when the feed is absent.
- `usage-empty` shows the usage shell with no numbers and no window buttons when the feed is absent.
- `shipping-missing` says the daily shipping data is unavailable when the feed carries no shipping block, instead of drawing an empty chart.
- `kpi-unavailable` prints every KPI metric it cannot measure with its reason, never as a zero.
- `usage-no-plans` says no plans exist when the feed carries no plan cards, instead of an empty list.
- `home-empty` says a hub section holds nothing instead of a blank list.
- `not-found` answers an unknown URL with the not-found page and a way home.

## How to get to it (user POV)

- Open `/factory` or `/usage` on a build with no feed file.
- Open `/factory` on a feed whose `kpis` block has no `shipping` block, or open `/usage` on a feed whose `usage.cards` list is empty.
- Open `/` with an empty hub content store.
- Open any URL the site does not serve, such as `/no-such-page`.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The helper removes the bundled feed and the hub store for the empty launch, then rebuilds. For the sparse launch it writes `fixture.json` with `usage.cards` emptied and `kpis.shipping` dropped, and keeps the rest of the feed, including its KPI unavailability notes.

- Factory. Require `No factory numbers yet.`, no `Output and waste` heading, and no `PRs shipped vs plan burn` heading.
- Usage. Open `/usage` and require `No usage numbers yet.` and no `Usage window` group.
- Shipping. On the sparse launch require the `PRs shipped vs plan burn` heading, the line `Daily shipping data unavailable. This feed predates the daily collector.`, and no `Daily shipping and burn chart` region.
- KPI notes. On the sparse launch require the `Output and waste` heading and both notes: `Cost per delivered ticket unavailable. Dated deliveries are blocked by HYCI-9390. Not a measured zero.` and `Escapes unavailable. The exporter login cannot read all three boards. Not a measured zero.`
- No plans. On the sparse launch open `/usage` and require `No plans yet.` and no `Claude Code` card heading.
- Home. Require `No explorations yet.` and `No reports yet.`, and no item links.
- Indexes. Open `/reports` and `/explorations` and require `0 items.` with the matching empty line.
- Not found. `page.goto('/no-such-page')` must answer 404 and show the `Page not found` heading with the `Go to the home page.` link. Choosing that link returns Home.

## Gotchas

- The empty launch removes the feed file rather than emptying its numbers. A zeroed feed is a different, measured state.
- `shipping-missing` and `usage-no-plans` drop one block from a real feed; they do not zero a reading. A zeroed reading is what `kpi-zero`-style bugs look like, and it must fail.
- The 404 status is expected for `not-found`; the case recorder ignores that one response and its browser console line, and fails on any other error status.
- Missing KPI numbers print as unavailability notes from `kpis.notes` in the feed, not as zeroes. `kpi-unavailable` drives the two the feature map names.
