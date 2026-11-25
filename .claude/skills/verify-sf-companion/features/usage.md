# Usage page

Usage lives at its own URL, `/usage`, and has its own primary navigation entry. It shows one data age line under the title and one card per plan plan-pick knows: each plan with its own quota reading, reset line, fixed 1h burn line, optional pace line, optional skip line with the skip's end date and reason, optional note, optional Windows disclosure, a load line counting live chat sessions and live plan-pick runners, and live runner text. Every card heading shows a `↗` cue, carries an `aria-label` naming the action, `Open <provider> usage page`, links to that plan's own usage page in a new tab, and underlines on hover and focus. The `↗` is `aria-hidden`, so the heading's own name stays the provider name. The cards are ordered by load, heaviest first, and idle cards come last. There is no burn-window button picker. The Factory page keeps the export stamp, the shipping chart, and the KPI tiles.

Covers: route:Usage

Code paths: apps/web/src/features/usage.ts, apps/web/src/features/cue.ts, apps/web/src/features/factory.ts, apps/web/src/features/factory.stylex.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/client/app/model.ts, apps/web/src/client/app/message.ts, apps/web/src/client/app/subscription.ts, apps/web/src/client/app/update.ts, apps/web/src/content/feed.ts, apps/web/src/entry.server.ts

## Sub-features

- `usage-entry` loads `/usage` directly and reaches it from primary navigation.
- `usage-updated` shows one data age line under the title, `Updated HH:MM (N min ago)`, where `HH:MM` is the feed's `generatedAt` in the viewer's local time and `N` is the whole minutes since that stamp. The line is client-rendered and `N` re-reads the browser clock every 30 seconds without a reload.
- `usage-cards` shows every plan card: each plan with its heading showing a `↗` link cue, its reading, reset line, pace, skip line, load line and live runner text, heaviest load first and idle cards last. OpenCode reads Go usage.
- `usage-burn` shows the fixed 1h burn reading with no window picker buttons or copy about them.
- `usage-details` expands the card's Windows disclosure.

## How to get to it (user POV)

- Open `/usage` directly.
- Choose Usage in Primary navigation.
- Choose `Open` in the Usage section on Home.
- Choose the Usage link on Factory.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. These actions run for each seeded viewport and color scheme. The fixture carries seven cards covering percent, credit, no-reading, noted, live-runner and idle modes.

- Entry. `page.goto('/usage')` must return 200 and show `getByRole('heading', {name: 'Usage', exact: true})`, with the `Software Factory Companion` link in Primary navigation. Then choose the site name, then `Usage` in `getByRole('navigation', {name: 'Primary navigation'})`. Then from Home choose `Open` in the Usage section, and from `/factory` choose the `Usage` link in the page body. Each one must land on the Usage heading.
- Cards. Require headings `Claude Code`, `Codex`, `Antigravity`, `OpenCode`, `Vercel Token Pass`, `OpenRouter`, and `CommandCode`, in that order, with no `Grok`, `DeepSeek` or `Cursor` card. Inside the Claude Code list item require `67%`, `+13.2 vs pace · over pace` and `41 chats`. Inside Codex require `3 chats · 2 runners`. Inside Antigravity require `Quota used up at 2026-11-24T00:46:05Z · limit unknown`, `2 runners` and `2 gemini-4-neon high`. Inside OpenCode require `100%`, `Prepaid credit estimate: $6.20 left`, `1 runner` and `1 DeepSeek 4.1 Flash medium`. Inside Vercel Token Pass require `81%`, `resets 5 Dec`, `$28.90 of $150 pass credit left` and `idle`. Inside OpenRouter require `$45.85 left`. Inside CommandCode require `idle`. Capture `seeded-<width>-<theme>-before.png` on `/usage`.
- Heading links. Every card heading shows the `↗` cue, and its link is named `Open <provider> usage page` (`Open Claude Code usage page`, for example) rather than the provider name alone. Hovering or focusing that link underlines the heading. The link opens a new tab with `rel` `noopener`. Require these exact `href` values: Claude Code `https://claude.ai/new#settings/usage`, Codex `https://chatgpt.com/settings/usage?tab=overview`, Antigravity `https://antigravity.google/`, OpenCode `https://opencode.ai/console/wrk_01KF5VZPS53BNVE2RR9QAYJSB4/go`, Vercel Token Pass `https://vercel.com/hypertaskai/~/ai-gateway/token-pass`, OpenRouter `https://openrouter.ai/settings/credits`, and CommandCode `https://commandcode.ai/`.
- Data age. Under the `Usage` heading require one line matching `Updated HH:MM (N min ago)`. `N` must equal the whole minutes between the feed's `generatedAt` and the browser's `Date.now()` within one minute, which proves the line is client-rendered from the viewer's clock rather than baked into the static page. No reload happens between the page load and the line appearing.
- Fixed 1h burn. Require `+2% · £0.00 in 1h on runners`, no `Usage window` group, and no `The buttons change the burn window only.` line.
- Expand details. Click `getByText('Windows', {exact: true})` inside the Claude Code card; require `Weekly 67%` visible. Click `getByText('Windows', {exact: true})` inside the OpenCode card; require `month 100%` visible.
- Proof. `seeded-<width>-<theme>-before.png` captures `/usage` showing the OpenCode number, live runners, and the picker gone.

## Gotchas

- Burn uses one fixed 1h window; no window buttons exist on `/usage` or `/factory`.
- The data age line is absent from the static HTML the build writes, because no server knows the viewer's timezone or clock. It only appears after hydration, so a missing line means the client subscription is not running, not that the feed is stale.
- Hidden disclosure text is not proof of expansion. Require visibility.
- The card's reset line and runner text come from the feed, so a missing card usually means a feed decode failure, not a rendering bug.
- `/usage` must be in `apps/infra/alchemy.local.ts` `hubRoutes`, or the old Worker answers that path in production.
