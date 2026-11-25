# Usage page

Usage lives at its own URL, `/usage`, and has its own primary navigation entry. It shows one card per plan plan-pick knows: each active plan with its own quota reading, reset line, fixed 1h burn line, optional pace line, optional skip line with the skip's end date and reason, optional note, optional Windows disclosure, and live runner text. The retired plans (Grok, Cursor and DeepSeek's own API) render greyed out with an `inactive` label and come last, with no reading, pace or runner line. There is no burn-window button picker. The Factory page keeps the export stamp, the shipping chart, and the KPI tiles.

Covers: route:Usage

Code paths: apps/web/src/features/usage.ts, apps/web/src/features/cue.ts, apps/web/src/features/factory.ts, apps/web/src/features/factory.stylex.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/client/app/model.ts, apps/web/src/client/app/message.ts, apps/web/src/client/app/update.ts, apps/web/src/content/feed.ts, apps/web/src/entry.server.ts

## Sub-features

- `usage-entry` loads `/usage` directly and reaches it from primary navigation.
- `usage-cards` shows every plan card: active plans with their reading, reset line, pace, skip line and live runner text, and retired plans greyed out with an `inactive` label and no reading or runner line, sorted after every active card. OpenCode reads Go usage.
- `usage-burn` shows the fixed 1h burn reading with no window picker buttons or copy about them.
- `usage-details` expands the card's Windows disclosure.

## How to get to it (user POV)

- Open `/usage` directly.
- Choose Usage in Primary navigation.
- Choose `Open` in the Usage section on Home.
- Choose the Usage link on Factory.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. These actions run for each seeded viewport and color scheme. The fixture carries ten cards covering percent, credit, no-reading, noted, live-runner and inactive modes.

- Entry. `page.goto('/usage')` must return 200 and show `getByRole('heading', {name: 'Usage', exact: true})`, with the `Software Factory Companion` link in Primary navigation. Then choose the site name, then `Usage` in `getByRole('navigation', {name: 'Primary navigation'})`. Then from Home choose `Open` in the Usage section, and from `/factory` choose the `Usage` link in the page body. Each one must land on the Usage heading.
- Cards. Require headings `Claude Code`, `Codex`, `OpenCode`, `Vercel`, `OpenRouter`, `Antigravity`, `CommandCode`, `Grok`, `DeepSeek`, and `Cursor`. Inside the Claude Code list item require `67%` and `+13.2 vs pace · over pace`. Inside OpenCode require `100%`, `Prepaid credit estimate: $6.20 left`, and `1 DeepSeek 4.1 Flash medium`. Inside Vercel require `$105.28 left`. Inside OpenRouter require `$45.85 left`. Inside Antigravity require `Quota used up at 2026-11-24T00:46:05Z · limit unknown` and `2 gemini-4-neon high`. Inside each of Grok, DeepSeek and Cursor require `inactive` and no `0 runners` line. Capture `seeded-<width>-<theme>-before.png` on `/usage`.
- Fixed 1h burn. Require `+2% · £0.00 in 1h on runners`, no `Usage window` group, and no `The buttons change the burn window only.` line.
- Expand details. Click `getByText('Windows', {exact: true})` inside the Claude Code card; require `Weekly 67%` visible. Click `getByText('Windows', {exact: true})` inside the OpenCode card; require `month 100%` visible.
- Proof. `seeded-<width>-<theme>-before.png` captures `/usage` showing the OpenCode number, live runners, and the picker gone.

## Gotchas

- Burn uses one fixed 1h window; no window buttons exist on `/usage` or `/factory`.
- Hidden disclosure text is not proof of expansion. Require visibility.
- The card's reset line and runner text come from the feed, so a missing card usually means a feed decode failure, not a rendering bug.
- `/usage` must be in `apps/infra/alchemy.local.ts` `hubRoutes`, or the old Worker answers that path in production.
