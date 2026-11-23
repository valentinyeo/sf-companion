# Stored items

A stored item is served at `/explorations/<slug>` or `/reports/<slug>` as the exact bytes kept in the content store, before the page renderer sees the request.

Covers: route:Entry, share:serve

Code paths: apps/web/src/content/share.ts, apps/web/src/content/hub.ts, apps/web/src/content/item.ts, apps/web/src/entry.server.ts, apps/web/src/features/route.ts

## Sub-features

- `items-serve` answers GET with the stored bytes and their content type.
- `items-head` answers HEAD with the same headers and no body.
- `items-missing` answers 404 for a slug the store does not hold.
- `items-invalid` answers 400 for a slug outside the allowed character set.
- `items-invalid-slug` answers 400 for a path whose slug holds a slash or is not a decodable slug.

## How to get to it (user POV)

- Follow a hub row, or open `/reports/<slug>` and `/explorations/<slug>` directly.

## Driving it with Playwright

Preconditions:

- Run `../run.sh` with the seeded hub store. Use the page's own request context so cookies and base URL match the browser.

- Serve. `GET /reports/4b7c1d2e-client-pricing.html` must answer 200, `content-type: text/html; charset=utf-8`, and the stored body. `GET /explorations/2a5e8f4d-motion-study.html` must answer 200.
- Head. `HEAD /reports/4b7c1d2e-client-pricing.html` must answer 200 with a positive `content-length` and an empty body.
- Missing. `GET /reports/0000-missing.html` must answer 404 with `Not found`.
- Invalid. `GET /reports/bad%24slug.html` must answer 400 with `{"error":"Invalid slug"}`.
- Invalid slug. `GET /reports/a/b`, `GET /reports/%24`, and `GET /reports/%FF` must answer the same 400. `%FF` is the undecodable case: `decodeURIComponent` throws on it, the raw `%FF` reaches the slug check, and the answer is 400 rather than a 500 from an unhandled `URIError`.

## Gotchas

- The JSON body and the 404 text come from `share.ts`, not from the site shell.
- A `$` or `/` in a slug is rejected before the store is read, so an invalid slug never leaks whether an object exists.
- A path that ends at the section, such as `/reports/`, is the section index, not an item with an empty slug. The index journeys in `reports.md` and `explorations.md` drive it.
- `%FF` is not a decodable byte sequence, so it is the only case here that reaches the `try`/`catch` around `decodeURIComponent` in `entry.server.ts`. Remove that `catch` and this journey fails with a 500.
