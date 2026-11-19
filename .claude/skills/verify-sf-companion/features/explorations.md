# Explorations

Explorations is the index of working notes and experiments, newest first, and each row opens the stored item.

Code paths: apps/web/src/content/hub.ts, apps/web/src/content/item.ts, apps/web/src/content/bucket.ts, apps/web/src/content/share.ts, apps/web/src/features/hub.stylex.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/entry.server.ts

## Sub-features

- `explorations-index` lists exploration items with project and date.
- `explorations-item` serves one stored item at `/explorations/<slug>`.
- `explorations-scope` keeps report items off the index.

## How to get to it (user POV)

- Open `/explorations`.
- Choose Explorations in Primary navigation.
- Choose `All N` under the Explorations heading on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. `fixture-hub/` supplies one exploration and two reports.

- Index. Require the `Explorations` heading, `1 items.`, the `Motion study` link, and no `Retainer summary` link.
- Item. Open `/explorations/2a5e8f4d-motion-study.html` and require `Fixture motion body.` at HTTP 200 and no site navigation. Save `hub-exploration-item-<case>.png` and `hub-exploration-item-<case>.aria.txt`.
- Empty. Require `No explorations yet.` and `0 items.`

## Gotchas

- An item response is the stored bytes, not a Foldkit page. The browser loads the artefact's own HTML.
- A missing slug answers 404 from the content store, not the site shell.
