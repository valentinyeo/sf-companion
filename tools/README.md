# Factory feed exporter

`export-factory-feed.py` writes the single JSON file the companion site reads for its Usage and KPIs modules.

Set these environment variables before running it:

- `ADVISOR_BIN` (required): the advisor's `bin` directory. Its helpers supply runner, reviewer, burn, and KPI readings.
- `TOKEN_LADDER_STATUS` (required): token-ladder's status JSON file. Claude and Codex use the weekly percentage, reset time, and pace (`used - time_gone`), plus any available week and five-hour readings. Readings older than 30 minutes, or plans reporting an error, show no reading.
- `OPENCODE_HISTORY` (optional): the OpenCode credit history JSONL file. The last nonblank line supplies `credits_usd`, `today_usd`, and the epoch timestamp `at`. The card shows the balance and reading age; the burn line includes today's dollars.
- `AI_GATEWAY_API_KEY` (optional): the Vercel AI Gateway key. One authenticated GET to `https://ai-gateway.vercel.sh/v1/credits` supplies `token_pass.remaining` in dollars. Numeric strings are accepted. The request has a 30-second timeout and no retries. The key and response are never logged.
- `DEEPSEEK_API_KEY` (optional): a DeepSeek platform key. One GET to `https://api.deepseek.com/user/balance` supplies the USD `total_balance`.
- `OPENROUTER_MANAGEMENT_KEY` and `OPENROUTER_MANAGEMENT_KEY_AGENTS` (optional): OpenRouter keys, one per account. Each GET to `https://openrouter.ai/api/v1/credits` supplies `total_credits - total_usage`; the card shows the sum. If any account fails to read, the card shows no reading.

```sh
ADVISOR_BIN=<advisor-bin-directory> \
TOKEN_LADDER_STATUS=<token-ladder-status-file> \
OPENCODE_HISTORY=<opencode-history-file> \
python3 tools/export-factory-feed.py --out /tmp/factory-feed.json
```

Inject the Vercel key through your secret manager rather than placing it in a command or file.

It needs Python 3 and nothing else. Run it on the factory host, because the runners line reads live tmux state. It never reads or recreates pacer state or starts a timer.

Every export includes Claude, Codex, Grok, OpenCode, and Vercel, in that order. Grok has no live source and always shows no reading. Missing or unreadable source files and missing or failed Vercel responses leave the affected cards without readings; they never become zero usage. OpenCode's age uses the contract's existing `· as of` prefix, for example ` · as of 28h ago`.

The file is written to a temp path and then renamed, so a crash never leaves half a feed. Each export reads current inputs and, when configured, Vercel's current balance.

Before writing, the script checks the feed against the contract and refuses to write an invalid one. Unset required environment variables exit with a setup message. The script only reads source state; it never runs the advisor's writers. Run verdicts come from its cached `violations.json`.

The field contract is the `FactoryFeed` schema in `apps/web/src/content/feed.ts`. The validator accepts Claude and Codex window readings using the existing window fields; no web schema change is needed.
