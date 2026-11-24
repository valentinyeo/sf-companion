# Usage page

Usage lives at its own URL, `/usage`, and has its own primary navigation entry. It shows one card per plan plan-pick knows, each with its own quota reading, reset line, burn line, optional pace line, optional skip line with the skip's end date and reason, optional note, optional Windows disclosure, and runner text. The window buttons above the cards change the burn window. The Factory page keeps the export stamp, the shipping chart, and the KPI tiles.

Covers: route:Usage

Code paths: apps/web/src/features/usage.ts, apps/web/src/features/cue.ts, apps/web/src/features/factory.ts, apps/web/src/features/factory.stylex.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/client/app/model.ts, apps/web/src/client/app/message.ts, apps/web/src/client/app/update.ts, apps/web/src/content/feed.ts, apps/web/src/entry.server.ts

## Sub-features

- `usage-entry` loads `/usage` directly and reaches it from primary navigation.
- `usage-cards` shows every plan card with its reading, reset line, burn, pace, skip line and runner text.
- `usage-window` selects 1h, 3h, 6h, 12h, 24h, 7d, and 30d.
- `usage-burn` changes the displayed burn to match the selected window.
- `usage-kpi-fixed` leaves Factory's KPI tiles and their readings untouched after every window choice.
- `usage-details` expands the card's Windows disclosure.

## How to get to it (user POV)

- Open `/usage` directly.
- Choose Usage in Primary navigation.
- Choose `Open` in the Usage section on Home.
- Choose the Usage link on Factory.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. These actions run for each seeded viewport and color scheme. The fixture carries ten cards covering percent, credit, no-reading, skipped and noted modes.

- Entry. `page.goto('/usage')` must return 200 and show `getByRole('heading', {name: 'Usage', exact: true})`, with the `Software Factory Companion` link in Primary navigation. Then choose the site name, then `Usage` in `getByRole('navigation', {name: 'Primary navigation'})`. Then from Home choose `Open` in the Usage section, and from `/factory` choose the `Usage` link in the page body. Each one must land on the Usage heading.
- Cards. Require headings `Claude Code`, `Codex`, `Grok`, `OpenCode`, `Vercel`, `DeepSeek`, `OpenRouter`, `Antigravity`, `CommandCode`, and `Cursor`. Inside the Claude Code list item require `67%` and `+13.2 vs pace · over pace`. Inside Vercel require `$105.28 left`. Inside DeepSeek require `$11.28 left`. Inside OpenCode require `no reading`. Inside Antigravity require `Quota used up at 2026-11-24T00:46:05Z · limit unknown`. Inside Cursor require `Skipped until 2036-11-20 20:22 UTC (manual skip (lane-limits))`.
- Baseline. Require `+2% · £0.00 in 1h on runners`. Capture `seeded-<width>-<theme>-before.png` on `/usage`.
- Select. For each window, click `page.getByRole('group', {name: 'Usage window'}).getByRole('button', {name: window, exact: true})`. Require that button's `aria-pressed` to become `true`.
- Read burn. On 7d, require `+14% · £7.00 in 7d on runners`. The helper returns to 1h after exercising every button.
- Read KPIs. Open `/factory` after the buttons; require `29 / day · 87 / week` and no `Usage window` group there.
- Expand details. Click `getByText('Windows', {exact: true})` inside the Claude Code card; require `Weekly 67%` visible.
- Proof. `seeded-<width>-<theme>.png` is the page the case ended on; `-final.png` is the last page the case visited. Compare the before image with the expanded usage image.

## Gotchas

- Buttons affect usage burn only. KPI tiles live on `/factory` and their numbers must not follow the buttons.
- A selected button alone does not prove client hydration. The changed 7d reading must appear.
- Hidden disclosure text is not proof of expansion. Require visibility.
- The card's reset line and runner text come from the feed, so a missing card usually means a feed decode failure, not a rendering bug.
- `/usage` must be in `apps/infra/alchemy.local.ts` `hubRoutes`, or the old Worker answers that path in production.
