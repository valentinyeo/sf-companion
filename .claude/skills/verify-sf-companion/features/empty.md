# Empty and missing states

The site says what is missing instead of rendering an empty frame or an invented zero. A missing feed, an empty hub section, and an unknown URL each get their own explicit message.

Covers: factory:no-feed, route:NotFound

Code paths: apps/web/src/features/factory.ts, apps/web/src/features/usage.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/content/feed.ts, apps/web/src/content/item.ts

## Sub-features

- `factory-empty` shows the factory shell with no numbers when the feed is absent.
- `usage-empty` shows the usage shell with no numbers and no window buttons when the feed is absent.
- `home-empty` says a hub section holds nothing instead of a blank list.
- `not-found` answers an unknown URL with the not-found page and a way home.

## How to get to it (user POV)

- Open `/factory` or `/usage` on a build with no feed file.
- Open `/` with an empty hub content store.
- Open any URL the site does not serve, such as `/no-such-page`.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The helper removes the bundled feed and the hub store for the empty launch, then rebuilds.

- Factory. Require `No factory numbers yet.`, no `Output and waste` heading, and no `PRs shipped vs plan burn` heading.
- Usage. Open `/usage` and require `No usage numbers yet.` and no `Usage window` group.
- Home. Require `No explorations yet.` and `No reports yet.`, and no item links.
- Indexes. Open `/reports` and `/explorations` and require `0 items.` with the matching empty line.
- Not found. `page.goto('/no-such-page')` must answer 404 and show the `Page not found` heading with the `Go to the home page.` link. Choosing that link returns Home.

## Gotchas

- The empty launch removes the feed file rather than emptying its numbers. A zeroed feed is a different, measured state.
- The 404 status is expected for `not-found`; the case recorder ignores that one response and its browser console line, and fails on any other error status.
- Missing KPI numbers print as unavailability notes in the feed, not as zeroes.
