# Factory feed exporter

`export-factory-feed.py` writes the single JSON file the companion site reads for its Usage and KPIs modules.

Set these environment variables before running it:

- `ADVISOR_BIN` (required): the advisor's `bin` directory. Its helpers supply runner, reviewer and burn readings for Usage, not KPIs.
- `TOKEN_LADDER_STATUS` (required): token-ladder's status JSON file. Claude and Codex use the weekly percentage, reset time, and pace (`used - time_gone`), plus any available week and five-hour readings. Readings older than 30 minutes, or plans reporting an error, show no reading.
- `OPENCODE_API_KEY` / `OPENCODE_AUTH_FILE` (optional): OpenCode Go API key (defaults to `~/.pi/agent/auth.json` or `~/.local/share/opencode/auth.json`, provider `opencode-go`). One authenticated GET to `https://opencode.ai/zen/go/v1/usage` supplies monthly, weekly, and 5h Go subscription percentages and reset times. A second authenticated GET to `https://opencode.ai/console/api/billing/status` supplies the workspace's prepaid credit from `balanceMicroCents` (falling back to `availableMicroCents`, divided by 100,000,000 for dollars), and that live balance wins over history and the estimate. The billing route answers 403 for a key without the Console's Billing Read permission, so an unreadable balance falls back to `OPENCODE_HISTORY` or plan-pick's anchored credit in `lane-credits.json` labeled `estimate`.
- `OPENCODE_HISTORY` (optional): the OpenCode credit history JSONL file. Used for today's spend, and as a credit fallback when neither the console balance nor the Go usage endpoint can be read.
- `TOKEN_LADDER_LAUNCHES` (optional): plan-pick's `launches.jsonl` (defaults next to `TOKEN_LADDER_STATUS`). Unfinished launches whose PID or `plan-pick --run` process is alive supply live runner counts per lane.
- `AGY_BIN` (optional): the Antigravity `agy` binary (defaults to `~/.local/bin/agy`). The exporter runs `agy -p /usage --print-timeout 45s` in an empty temp directory with a 60-second timeout. Each row of its tab-separated output is a limit with the percentage left and the reset time; Gemini's weekly row becomes the Antigravity card's number and reset, and Gemini's five-hour row plus both Claude/GPT rows become its windows. A failed, timed-out or empty read leaves the card on token-ladder's quota note.
- `AI_GATEWAY_API_KEY` (optional): the Vercel AI Gateway key. One authenticated GET to `https://ai-gateway.vercel.sh/v1/credits` supplies `token_pass.remaining` in dollars. Numeric strings are accepted. The request has a 30-second timeout and no retries. The key and response are never logged. The cycle total comes from `limit_usd` on the `vercel` entry in `TOKEN_LADDER_CREDITS`, which plan-pick publishes from token-ladder `config.json`; without it the card has no percentage and its note says `of unknown total`.
- `TOKEN_LADDER_CREDITS` (optional): plan-pick's `lane-credits.json` (defaults next to `TOKEN_LADDER_STATUS`). OpenRouter's card reads the published `openrouter` entry, `usd` with the epoch `at` it was read, exactly as plan-pick publishes it. The balance is shown as-is, so a negative balance reads `-$0.20 left` and turns the number's tone hot; no second account is added. A missing entry leaves the card without a reading.
- `ROSTER_BIN` (optional): the live-session roster, defaulting to `~/.local/share/house-rules/fleet/roster-live`. Its `Name (id, harness, cwd)` lines supply the chat count on the Claude and Codex cards, deduped by the id in brackets. A roster that exits non-zero, times out or cannot be run leaves the chat count out of every card.

```sh
ADVISOR_BIN=<advisor-bin-directory> \
TOKEN_LADDER_STATUS=<token-ladder-status-file> \
OPENCODE_HISTORY=<opencode-history-file> \
python3 tools/export-factory-feed.py --out /tmp/factory-feed.json
```

Inject the Vercel key through your secret manager rather than placing it in a command or file.

It needs Python 3 and nothing else. Run it on the factory host, because the runners line reads live worker processes and the advisor's tmux state. It never reads or recreates pacer state or starts a timer.

Every export includes Claude, Codex, OpenCode, Vercel, OpenRouter, Antigravity and CommandCode with one fixed `1h` burn window. Each card carries a `loadText` line built from the live chat sessions `ROSTER_BIN` lists (Claude harnesses on the Claude card, Codex harnesses on the Codex card) plus the plan's live plan-pick runners: `3 chats · 1 runner`, `2 runners`, `41 chats`, or `idle` when both are zero. A roster that cannot be read leaves the chat count out rather than showing zero, so a partly unreadable card reads `–`. Cards are ordered by that load, heaviest first, ties keep the plan order, and idle cards come last. DeepSeek models launched through OpenCode, Vercel or OpenRouter still count on that plan's card. Missing or unreadable source files and missing or failed responses leave the affected cards without readings; they never become zero usage. Every credit card's age uses the contract's `· as of` prefix, for example ` · as of 28h ago`.

The file is written to a temp path and then renamed, so a crash never leaves half a feed. Each export reads current inputs and, when configured, Vercel's current balance.

Before writing, the script checks the feed against the contract and refuses to write an invalid one. Unset required environment variables exit with a setup message. The script only reads source state; it never runs the advisor's writers.

KPIs read Hypertask, GitHub, token-ladder pools and the fleet watchdog independently. Their source windows, configuration, missing-data behavior, the `FACTORY_CACHE` GitHub call store, and the focused test command are documented in [Factory KPI sources](factory-kpis.md). The old advisor KPI windows and violations chart are no longer exported.

GitHub reads are incremental. Finished Actions runs and their failure classifications are kept per run id, and the PR query stops at the previous export instead of paging the whole window again. If the shared `gh` wrapper refuses a read (exit 75), the script exits non-zero, prints one line and leaves the previous feed file alone, so a refused hour never replaces the numbers with an empty feed.

The field contract is the `FactoryFeed` schema in `apps/web/src/content/feed.ts`. KPIs are named tiles with source, window and measurement details, plus explanations for sources that could not supply a tile.

`~/.local/bin/sf-companion-feed` is a symlink to `tools/sf-companion-feed` in this repo.

# Chat collector

`collect-chats.py` writes the live chat roster the companion site shows at `/chats`. It reads four things and nothing else:

- `~/.local/share/house-rules/fleet/roster-live` (`ROSTER_BIN` overrides it) for the chat name, harness and working folder of every live chat on this server.
- `mp-sessions list` (`MP_SESSIONS_BIN` overrides it) for Multibot's own chat names.
- Each harness's session record for the chat's model and effort: Claude Code's registry under `~/.claude/sessions` plus that session's transcript under `~/.claude/projects`, Codex's rollouts under `~/.codex/sessions` (the one the chat's process holds open), and Pi's records under `~/.pi/agent/sessions` (the one its process holds open). A chat whose record cannot be read shows `unknown`; a config default is never substituted.
- `~/.local/state/roster/announce` (`ROSTER_ANNOUNCE_DIR` overrides it) for the Claude session id each chat announced, which is what maps a chat to its transcript.

The inne server is one read-only `ssh` run as user `inne` through the same host `inne-comms` uses (`INNE_COMMS_HOST` overrides it). It prints the same fields from Claude Code's registry and transcripts there. When the run fails the server is published as `not-connected` and no rows are invented for it.

Every published string passes the allowlist record: a chat is exactly `name`, `server`, `project`, `harness`, `model` and `effort`, and each of those is redacted for emails, IP addresses, host names and token-like runs first. `project` is a folder name, never a path. The file is written to a temp path and renamed, so a crash never leaves half a snapshot.

```sh
python3 tools/collect-chats.py --out apps/web/content/feed/chats.json
```

`tools/sf-companion-chats` runs the collector and publishes the snapshot to `chats/latest.json` in the `yeoux-site-content` bucket, which the Worker already binds as `CONTENT`. `/chats` reads that object on every request, so a refresh needs no build and no deploy. Install it on the host and enable the timer:

```sh
ln -sfn ~/projects/sf-companion/tools/sf-companion-chats ~/.local/bin/sf-companion-chats
install -Dm644 ~/projects/sf-companion/tools/sf-companion-chats.service ~/.config/systemd/user/sf-companion-chats.service
install -Dm644 ~/projects/sf-companion/tools/sf-companion-chats.timer ~/.config/systemd/user/sf-companion-chats.timer
systemctl --user daemon-reload && systemctl --user enable --now sf-companion-chats.timer
```

The timer runs every five minutes, so the page's data age stays under ten. `tools/test_collect_chats.py` holds the collector's redaction and ordering tests; CI runs it.
