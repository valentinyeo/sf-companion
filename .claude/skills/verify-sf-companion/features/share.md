# Share endpoint

The share endpoint writes and removes stored items through the same URLs that serve them. A publish appears on its index after the next page load, and a delete removes both the object and its listing.

Covers: share:upload, share:delete

Code paths: apps/web/src/content/share.ts, apps/web/src/content/hub.ts, apps/web/src/entry.server.ts

## Sub-features

- `share-publish` stores a new item and shows it on its index.
- `share-delete` removes an item and confirms a second delete answers 404.
- `share-auth` rejects a write without the share token.
- `share-validate` rejects a malformed date, project, or slug.

## How to get to it (user POV)

- A publisher sends `PUT /reports/<slug>` with `Authorization: Bearer <SHARE_TOKEN>`, `X-Date`, `X-Project`, and `X-Title`.
- A publisher sends `DELETE /reports/<slug>` with the same bearer token.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The helper starts the seeded launch with `SF_SHARE_TOKEN=verify-share-token`, the local stand-in for the Worker's `SHARE_TOKEN` binding. Use `request.newContext({baseURL})`.

- Auth. `PUT /explorations/verify-publish.html` with a body and no `Authorization` must answer 401. The same `DELETE` must answer 401.
- Validate. With the bearer token, `X-Date: 17/10/2026` must answer 400 and name the date format. `X-Project: Yeo UX` must answer 400 and name the allowed characters. `PUT /reports/bad%24slug.html` with the token must answer 400 `Invalid slug`.
- Publish. `PUT /explorations/verify-publish.html` with the token, `X-Date: 2026-11-16`, `X-Project: verify`, `X-Title: Verification publish`, and an HTML body must answer 200 with a `url`. Then `GET /explorations` must show `Verification publish` with `verify · 2026-11-16` and `11 items.`.
- Delete. `DELETE` the same URL with the token must answer 200 with `deleted: true`. Then `GET /explorations` must show `10 items.` and no `Verification publish`. A second delete must answer 404.
- Proof. The share case writes its own action log and JSON entry to the proof directory.

## Gotchas

- The publish runs after the hub journeys in the same seeded launch and its delete restores the store, so later assertions see the fixture again.
- A local launch writes into `apps/web/content/hub/`. Nothing writes to R2 unless a `CONTENT` binding exists.
- An empty `PUT` body deletes instead of storing; that is the upload handler's contract, not a separate route.
