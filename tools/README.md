# Factory feed exporter

`export-factory-feed.py` writes the single JSON file the companion site reads for its Usage and KPIs modules.

Set these environment variables before running it:

- `ADVISOR_BIN` (required): the advisor's `bin` directory. Its helpers supply runner, reviewer and burn readings for Usage, not KPIs.
- `TOKEN_LADDER_STATUS` (required): token-ladder's status JSON file. Claude and Codex use the weekly percentage, reset time, and pace (`used - time_gone`), plus any available week and five-hour readings. Readings older than 30 minutes, or plans reporting an error, show no reading.
- `OPENCODE_API_KEY` / `OPENCODE_AUTH_FILE` (optional): OpenCode Go API key (defaults to `~/.pi/agent/auth.json` or `~/.local/share/opencode/auth.json`, provider `opencode-go`). One authenticated GET to `https://opencode.ai/zen/go/v1/usage` supplies monthly, weekly, and 5h Go subscription percentages and reset times. If that read fails, the card falls back to `OPENCODE_HISTORY` or plan-pick's anchored credit in `lane-credits.json` labeled `estimate`.
- `OPENCODE_HISTORY` (optional): the OpenCode credit history JSONL file. Used for today's spend and as a credit fallback when the Go usage endpoint cannot be read.
- `TOKEN_LADDER_LAUNCHES` (optional): plan-pick's `launches.jsonl` (defaults next to `TOKEN_LADDER_STATUS`). Unfinished launches whose PID or `plan-pick --run` process is alive supply live runner counts per lane.
- `AI_GATEWAY_API_KEY` (optional): the Vercel AI Gateway key. One authenticated GET to `https://ai-gateway.vercel.sh/v1/credits` supplies `token_pass.remaining` in dollars. Numeric strings are accepted. The request has a 30-second timeout and no retries. The key and response are never logged.
- `OPENROUTER_MANAGEMENT_KEY` and `OPENROUTER_MANAGEMENT_KEY_AGENTS` (optional): OpenRouter keys, one per account. Each GET to `https://openrouter.ai/api/v1/credits` supplies `total_credits - total_usage`; the card shows the sum. If any account fails to read, the card shows no reading.

```sh
ADVISOR_BIN=<advisor-bin-directory> \
TOKEN_LADDER_STATUS=<token-ladder-status-file> \
OPENCODE_HISTORY=<opencode-history-file> \
python3 tools/export-factory-feed.py --out /tmp/factory-feed.json
```

Inject the Vercel key through your secret manager rather than placing it in a command or file.

It needs Python 3 and nothing else. Run it on the factory host, because the runners line reads live worker processes and the advisor's tmux state. It never reads or recreates pacer state or starts a timer.

Every export includes Claude, Codex, OpenCode, Vercel, OpenRouter, Antigravity, CommandCode, Grok, DeepSeek and Cursor, in that order, with one fixed `1h` burn window. The retired plans (`INACTIVE_PLANS`: Grok, Cursor and DeepSeek's own API) come last, carry `inactive: true`, and are read from no API. DeepSeek models launched through OpenCode, Vercel or OpenRouter still count as active. Missing or unreadable source files and missing or failed responses leave the affected cards without readings; they never become zero usage. Every credit card's age uses the contract's `· as of` prefix, for example ` · as of 28h ago`.

The file is written to a temp path and then renamed, so a crash never leaves half a feed. Each export reads current inputs and, when configured, Vercel's current balance.

Before writing, the script checks the feed against the contract and refuses to write an invalid one. Unset required environment variables exit with a setup message. The script only reads source state; it never runs the advisor's writers.

KPIs read Hypertask, GitHub, token-ladder pools and the fleet watchdog independently. Their source windows, configuration, missing-data behavior, the `FACTORY_CACHE` GitHub call store, and the focused test command are documented in [Factory KPI sources](factory-kpis.md). The old advisor KPI windows and violations chart are no longer exported.

GitHub reads are incremental. Finished Actions runs and their failure classifications are kept per run id, and the PR query stops at the previous export instead of paging the whole window again. If the shared `gh` wrapper refuses a read (exit 75), the script exits non-zero, prints one line and leaves the previous feed file alone, so a refused hour never replaces the numbers with an empty feed.

The field contract is the `FactoryFeed` schema in `apps/web/src/content/feed.ts`. KPIs are named tiles with source, window and measurement details, plus explanations for sources that could not supply a tile.

`~/.local/bin/sf-companion-feed` is a symlink to `tools/sf-companion-feed` in this repo.
