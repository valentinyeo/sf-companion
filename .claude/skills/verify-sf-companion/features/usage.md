# Usage cards and windows

Usage shows one card per plan, each with its own quota reading, reset line, burn line, optional pace line, optional Windows disclosure, and runner text. The window buttons below the heading change the burn window without touching KPI readings.

Covers: factory:usage

Code paths: apps/web/src/features/factory.ts, apps/web/src/client/app/model.ts, apps/web/src/client/app/message.ts, apps/web/src/client/app/update.ts, apps/web/src/content/feed.ts

## Sub-features

- `usage-cards` shows every plan card with its reading, reset line, burn, pace, and runner text.
- `usage-window` selects 1h, 3h, 6h, 12h, 24h, 7d, and 30d.
- `usage-burn` changes the displayed burn to match the selected window.
- `usage-kpi-fixed` preserves every KPI reading while the window changes.
- `usage-details` expands the card's Windows disclosure.

## How to get to it (user POV)

- Open Factory with a feed present.
- Use the buttons below Usage.
- Open Windows on the Claude Code card.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. These actions run for each seeded viewport and color scheme. The fixture carries seven cards covering percent, credit, and no-reading modes.

- Cards. Require headings `Claude Code`, `Codex`, `Grok`, `OpenCode`, `Vercel`, `DeepSeek`, and `OpenRouter`. Inside the Claude Code list item require `67%` and `+13.2 vs pace · over pace`. Inside Vercel require `$105.28 left`. Inside DeepSeek require `$11.28 left`. Inside OpenCode require `no reading`.
- Baseline. Require `+2% · £0.00 in 1h on runners`. Capture `seeded-<width>-<theme>-before.png`.
- Select. For each window, click `page.getByRole('group', {name: 'Usage window'}).getByRole('button', {name: window, exact: true})`. Require that button's `aria-pressed` to become `true`.
- Read burn. On 7d, require `+14% · £7.00 in 7d on runners`. The helper returns to 1h after exercising every button.
- Read KPIs. Require `29 / day · 87 / week` after every selection.
- Expand details. Click `getByText('Windows', {exact: true})` inside the Claude Code card; require `Weekly 67%` visible.
- Proof. `seeded-<width>-<theme>.png` is the factory view after the drives; `-final.png` is the last page the case visited. Compare the before image with the expanded factory image.

## Gotchas

- Buttons affect usage burn only. KPI numbers must not follow them.
- A selected button alone does not prove client hydration. The changed 7d reading must appear.
- Hidden disclosure text is not proof of expansion. Require visibility.
- The card's reset line and runner text come from the feed, so a missing card usually means a feed decode failure, not a rendering bug.
