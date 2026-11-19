# Explorations

Explorations is the index of working notes and experiments, newest first, and each row opens the stored item.

Covers: route:List, section:explorations

Code paths: apps/web/src/content/hub.ts, apps/web/src/content/item.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/entry.server.ts

## Sub-features

- `explorations-index` lists every exploration with its project and date.
- `explorations-item` opens one stored exploration from its index row.
- `explorations-scope` keeps report items off the index.

## How to get to it (user POV)

- Open `/explorations`.
- Choose Explorations in Primary navigation.
- Choose `All 10` under the Explorations heading on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. `fixture-hub/` supplies ten explorations and ten reports.

- Index. Choose Explorations in Primary navigation. Require the `Explorations` heading, `10 items.`, and the row `Motion study` with `2026-11-05`.
- Item. Choose the `Motion study` row. Require `Fixture motion body.` at HTTP 200 and no site navigation. Save `hub-exploration-item-<case>.png` and `hub-exploration-item-<case>.aria.txt`.
- Scope. Require no `Client pricing review` and no `Retainer summary` link on the index.
- Empty. In the empty launch, require `No explorations yet.` and `0 items.`

## Gotchas

- An item response is the stored bytes, not a Foldkit page. The browser loads the artefact's own HTML.
- A missing slug answers 404 from the content store, not the site shell. Stored-item serving is mapped in `items.md`.
