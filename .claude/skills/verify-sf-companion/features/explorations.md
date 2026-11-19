# Explorations

Explorations is the index of working notes and experiments, newest first, and each row opens the stored item.

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
- Item. Open `/explorations/2a5e8f4d-motion-study.html` and require `Fixture motion body.` at HTTP 200.
- Empty. Require `No explorations yet.` and `0 items.`

## Gotchas

- An item response is the stored bytes, not a Foldkit page. The browser loads the artefact's own HTML.
- A missing slug answers 404 from the content store, not the site shell.
