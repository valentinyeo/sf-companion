# VSTA-329 burn report

Goal: trace observed plan and API usage to chats and tickets over any recorded range, refreshed by the hourly feed.

Ticket: https://app.hypertask.ai/detail/project-13556/329

## Scope audit

- Claude Code and Codex transcripts retain hourly input, output, cache and request counters. Streaming Claude updates and repeated Codex cumulative counters are deduplicated.
- Pi assistant-message usage is included by its provider plan, with recorded list-price costs where available. Antigravity logs without counters remain request-only.
- Worker start/finish records join by launch ID. Recorded worker tickets take precedence over inferred tickets. Only an exact, unique token/model/time match suppresses a duplicate worker receipt.
- Assistant-authored ticket mentions determine the most-mentioned ticket in each chat/hour. No prompt, message body or topic text is exported.
- Chat names use `MULTIBOT_SESSION`, roster announcements, Claude's registry and Multibot agent-host state. Published tmux names join both host session IDs and native transcript IDs.
- Hetzner collection runs as `inne` over the existing SSH export route. Only the aggregated numeric report crosses the host boundary. An unavailable remote is labelled “this server only”.
- OpenCode reads its daily usage export through token-ladder's existing `yeo-key --env 'OpenCode Check usage'` reader. Raw account IDs are hashed and user names are discarded.
- OpenRouter reads `/api/v1/activity` with `openrouter-credit`. Vercel reads `/v1/report` with the Token Pass provider key. Unavailable API readings stay unknown, and failed refreshes retain dated, sanitized history.
- Paid-key API totals have their own rows, separate from transcript/worker totals so overlapping requests are never added together. Daily provider totals stay daily. Reported charges are separate from list-equivalent prices.
- Rankings use model-specific prices for input, output, cache reads and cache writes. Token-ladder overrides the installed Pi catalog. Missing prices remain unknown; fixed token weights are not used.
- `/usage/burn` has plan/account, chat and ticket rankings, a Usage link, 24h/7d/reset-anchored plan week/custom ranges and explicit incomplete-coverage states.
- Transcript fixtures, price/range/Scene checks and the `burn-drilldown`, `burn-ranges` and `burn-missing` verifier journeys cover the additions. Their suites and browser execution remain pending on GitHub.

## Data ownership and limits

Transcripts and worker receipts are authoritative. The existing hourly feed is the sole report writer. Deleting the sanitized per-file cache rebuilds it from source. All recorded transcript history is retained. The installed Pi model catalog and token-ladder list prices supply pricing; Pi message costs marked provider-billed are not relabelled list-equivalent.

Provider APIs supply daily snapshots, not chat attribution. OpenCode and OpenRouter backfill their available rolling windows; Vercel collects today and yesterday. Older API snapshots accumulate after collection starts. Ranges include intersecting UTC days for provider totals and boundary hours for transcripts. The provider section does not follow the transcript plan/chat drill-down filters.

Workers' completion totals belong to the finish hour. Missing plan reset times exclude that plan from “this plan week”. Unknown account/key identities remain unrecorded. Receipt/transcript source links and chat tickets can be inferred, not authoritative.

`name-the-system-of-record` keeps the feed rebuildable. `scope-private-data` limits exported identities and inference to sanitized labels and ticket IDs. `store-source-facts` preserves missing counters, reset times and prices. Type System Discipline derives browser types from Effect Schema.

A cold export must parse the source logs. The previous worker inventoried approximately 30 GB of JSONL on Contabo. Full-export duration, feed size and browser behavior on production-scale burn history remain unmeasured.

## Evidence

- The live OpenCode reader returned 41 daily model/account rows. The new parser accepted them and the report validator found no problems. No key value or raw user/account data was printed.
- One real Pi transcript produced 52 usage rows, all priced, with no parser issues. Only counts were printed.
- Both configured OpenRouter and Vercel reporting requests returned HTTP 403. The exporter reports that limitation rather than zero usage. No credentials were changed.
- The existing Hetzner SSH route worked as `inne`; a numbers-only inventory found 1,576 Claude transcript files and no Codex/Pi files or worker receipt file. The full remote export was not run.
- Focused type-aware lint and formatting pass on the changed TypeScript files. Lint used temporary dependency links to the main checkout, whose lockfile is identical. Those links were removed after checking.
- Python exporter and fixture-test syntax, verifier JavaScript syntax and the numeric burn fixture validate.
- Feature coverage: 18/18 across 14 files. Journey launch: 52 journeys. All 10 fixture-scale measures pass. CI-scope validation passes.
- No-comments pass inspected in-thread. No code comments added, deleted or restored; no suppressions, constraint comments or encoding offers. No review subagent was started.
- No test suite, build or browser journey ran on this host. GitHub-hosted execution remains required before any readiness claim.

## Faults and handoff

This worker has no board login. The orchestrator must file repository/setup faults on the worker repo's board and view. No Hypertask command failed, so no Hypertask feedback is needed.

The requested `LEFTHOOK=0` conflicts with the repository hook policy and was not used. This continuation retried a normal commit after staging the completed scope. `pnpm check` failed with exit 127 (`heavy-local-guard: pnpm is not installed on this host`), and `pnpm test` failed with exit 2 because the heavy-local guard requires GitHub runners. No commit was created, no branch was pushed and no PR exists. A GitHub-hosted commit environment with working dependencies and hooks is required; the fence must not be bypassed.

The staged branch is `vsta-329-burn-report`. Both `HEAD` and freshly fetched `origin/main` are `c91f89264cceeb68f8dea63b2ebff7df58cbe2ff`, so no rebase is needed at this snapshot. There is no code-ready commit yet. The prepared PR body is `/tmp/vsta-329-pr-body.md`, with the required author line and plugin limitation.

`deslop unavailable`. The requested slop-strip plugin is not installed. Include that limitation and `Author model: openai/gpt-6.1-sol` in the PR body.
