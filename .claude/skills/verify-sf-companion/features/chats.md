# Chats page

Chats lives at its own URL, `/chats`, and has its own primary navigation entry. It lists every live chat on both factory servers, one table per server, with a count and a data age line: chat name, project folder, harness, model and effort. Nothing else reaches the page. The collector reads the roster on this server and the same registry and transcripts on the inne server, writes one snapshot, and publishes it to the content bucket, so the page shows data minutes old without a build or a deploy.

Covers: route:Chats

Code paths: apps/web/src/features/chats.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/content/chats.ts, apps/web/src/client/app/model.ts, apps/web/src/entry.server.ts, tools/collect-chats.py, tools/sf-companion-chats

## Sub-features

- `chats-entry` loads `/chats` directly and reaches it from primary navigation and from the Chats section on Home.
- `chats-rows` shows one table per server with a live chat count, and each row carries the chat name, project folder, harness, model and effort. Harness names are the friendly ones: Claude Code, Codex, Pi, Antigravity, Cursor. A field the collector could not read reads `unknown`. No home path and no email address reaches the page.
- `chats-age` shows one data age line under the title, `Updated HH:MM (N min ago)`, where `N` is the whole minutes between the snapshot's `generatedAt` and the browser clock.
- `chats-not-connected` shows `not connected yet` under a server whose collector did not answer, while the other server keeps its rows.
- `chats-empty` shows an explicit empty line instead of an empty table when no snapshot exists.

## How to get to it (user POV)

- Open `/chats` directly.
- Choose Chats in Primary navigation.
- Choose `Open` in the Chats section on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The seeded launch writes `fixture-chats.json` into `apps/web/content/feed/chats.json` with its stamps moved to three minutes before the build, so the age line is real. The sparse launch writes the same snapshot with the inne server marked not connected. The empty launch removes the snapshot.

- Entry. `page.goto('/chats')` must return 200 and show `getByRole('heading', {name: 'Chats', exact: true})`, with the `Software Factory Companion` link in Primary navigation. Then choose `Open` in the Chats section on Home, then choose `Chats` in `getByRole('navigation', {name: 'Primary navigation'})`. Each one must land on the Chats heading.
- Rows. Require `53 live chats` under the `Contabo` heading and 54 rows in its `Live chats` region, and `20 live chats` under `inne Hetzner` with 21 rows. The `HT Bugs` row carries `hypertask`, `Claude Code`, `claude-opus-5-5` and `high`. Cells `Cursor`, `Antigravity`, `Pi` and `Codex` exist, and at least one cell reads `unknown`. The body text holds no `/home/` path and no email address. Capture `seeded-<width>-<theme>-before.png` on `/chats`.
- Data age. Under the `Chats` heading require one line matching `Updated HH:MM (N min ago)` and require `N` between 1 and 8, which proves the line is computed from the snapshot stamp rather than baked into the page.
- Not connected. In the sparse launch require `not connected yet` under `inne Hetzner` and `53 live chats` under `Contabo`.
- Empty. In the empty launch require `No chat snapshot yet.` and no table.

## Gotchas

- The snapshot is not in the repository: it is written by `tools/collect-chats.py` and read from the content bucket at request time, so `/chats` is server-rendered per visit and is not in `prerenderPaths`. A page whose numbers never change is reading the bundled copy the collector last wrote, not the live object.
- A row reading `unknown` is the honest state for a chat whose harness session file could not be read; it is never a default taken from a config file.
- The inne server is reached through the same read-only route as `inne-comms`, one `ssh` run as user `inne`. When that run fails the server reads `not connected yet` rather than showing stale rows.
- `/chats` must be in `apps/infra/alchemy.local.ts` `hubRoutes`, or the old Worker answers that path in production.
- `tools/sf-companion-chats` publishes to the R2 bucket the Worker already binds as `CONTENT`; it never rebuilds and never deploys.
