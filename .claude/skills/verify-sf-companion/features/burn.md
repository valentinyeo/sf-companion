# Burn report

Covers: route:Burn

Code paths: apps/web/src/features/burn.ts, apps/web/src/content/burn.ts, tools/factory_burn.py, tools/export-factory-feed.py

The hourly feed carries UTC hourly usage totals with plan/account labels, distinct chats, models, recorded or inferred tickets, token counts and nullable list-equivalent cost. Transcripts stay on their source host. A partial or absent source never becomes a measured zero. No prompts, message text, credential values or raw account IDs reach the feed.

## Sub-features

- `burn-drilldown` follows the Usage link, selects a plan/account, selects a chat, reads its recorded and inferred tickets, and clears the chat filter without leaving the plan.
- `burn-ranges` compares 24h, 7d, each plan's reset-anchored week, and custom inclusive UTC dates. Unknown resets are excluded and named. Custom ranges can reach historical data older than seven days. A backwards range shows a recovery instruction.
- `burn-missing` reads coverage and server limits, Pi chat usage, separate paid-key API totals and reporting permission failures. Request-only usage has unknown tokens, shares and cost rather than fabricated zero spend.

## Driving it with Playwright

Run `../run.sh --journeys=burn-drilldown,burn-ranges,burn-missing` on a GitHub-hosted runner. The seeded cases drive these journeys at both viewport widths and in both themes. The fixture contains the heavy and small Claude chats, a Claude chat on a model with no price, a Codex chat outside the current plan week, an older historical chat, and Antigravity requests without tokens.

1. From `/usage`, follow `Where did the tokens go?`. Select `Show chats for claude / claude fixture account`, then `Show tickets for Burn heavy chat`. The Tickets table contains `VSTA-329 (recorded)` and `VSTA-328 (inferred)`, but not the small chat's `MUBO-45` or Codex's `HTPR-9`. Choose All chats and see `MUBO-45 (inferred)` reappear.
2. Directly open `/usage/burn`. Compare 24h and 7d to see `Codex older chat` disappear and reappear. This plan week excludes it using the fixture's reset anchor. Read the unavailable Antigravity reset. Select Custom and enter `2000-01-01` through `2099-01-01`; `Historical chat` appears. Change the start to `2099-02-01` and read the invalid-range status.
3. Open Coverage and limits and read `This server only.`, the request-only note and the OpenRouter HTTP 403 limitation. Read the separate OpenCode API row's `$0.12` reported charge and confirm it creates no chat drill-down button. Confirm `Pi fixture chat` is present. The `claude fixture account` plan row reads `$3.75` with `4 of 34 requests unpriced` beside it. Select Request-only chat and confirm its ticket row has unknown share and list-equivalent cost and explicitly incomplete token counts.

Each action is recorded against its journey in the browser case log and trace. Require no page-level horizontal overflow at 390px; the token tables scroll inside their own containers.

## Exporter checks

`tools/test_factory_burn.py` seeds private fixture transcripts and worker receipts in a temporary home. It covers deduplication, Codex cumulative counters and cache semantics, hour-local assistant-only inference, worker start/finish joins, parent versus child sessions, matching receipt suppression, reset anchors, request-only usage, redaction, cache replay and generated aggregation invariants. `apps/web/test/burn.test.ts` covers ranges, ranking, filters, incomplete numbers and the missing-feed page through Foldkit Scene.

Rankings use model-specific list prices, including cache prices, rather than raw or fixed-weight tokens. Prices come from the official Anthropic prices pinned in `tools/factory_burn.py` for models the installed catalog lacks, the installed Pi catalog, token-ladder overrides or Pi's recorded list-price costs. A group with at least one priced row shows the sum of its known costs and a note naming the requests it could not price; a group with nothing priced stays unknown.

Paid-key API totals stay separate from transcript/worker totals so overlapping requests are not added twice. OpenCode uses `OpenCode Check usage` through token-ladder's existing credential-safe exporter. OpenRouter reads `/api/v1/activity` with `openrouter-credit`. Vercel reads daily `/v1/report` groups with the Token Pass provider key. Daily provider rows are not divided into invented hours. A range includes intersecting UTC days. Successful sanitized readings are retained; a failed API read keeps its last reading and names its age. Provider account IDs are hashed, and names and key values are discarded. Vercel history starts with collection; OpenCode and OpenRouter backfill their available window.

Unknown transcript key identities remain labelled unrecorded. Worker totals belong to their finish hour; boundary hours are included in full. The report does not claim to reconstruct provider quota percentages or use outside reachable logs and APIs.
