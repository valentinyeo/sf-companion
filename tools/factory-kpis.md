# Factory KPI sources

The Factory page reports output and waste from read-only source facts. The exporter writes a derived feed, not a second ledger. It does not refresh advisor caches or modify upstream state.

| Metric | Authority | Measurement |
| --- | --- | --- |
| Tickets delivered | Hypertask boards 15, 2060, 11514 | Current Done tickets, using Done-move date, grouped by board and current assignee, rolling day and week |
| Verifier first pass | GitHub issue comments on fleet PRs | First PASS or PASS+NOTES divided by PRs whose first verdict arrived in rolling 7d |
| Merge coverage | Same GitHub comments | Merged PRs in rolling 7d without a verdict present at merge time, divided by merged PRs |
| Plan pace | token-ladder pools | Maximum used percentage divided by elapsed percentage across eligible plan windows; above 1 is over pace |
| Drain-loop health | Fleet solo-wake observations and orchestrator roster | Roster orchestrators with externally observed scheduled turns in the last 45 minutes |
| PR throughput and merge time (3) | GitHub fleet PR timestamps | Rolling 24h and 7d merge counts, seven-day daily average, median open-to-merge minutes for seven-day merges |
| Identity sync (11) | Fleet live Multibot chats and solo-wake identity-gap rule | Named agent-token file exists for the chat name, divided by all reachable live chats, including idle-stopped chats |
| CI health (12) | GitHub Actions runs, failed-job annotations, and Production deployment statuses | Confirmed infra, confirmed code, and unclassified failure shares; median merge-to-successful-Production-receipt minutes with exact SHA coverage |

Missing sources drop their tile and produce an explanation. They never produce a measured zero. A source failure does not hide other metrics. Every exported tile includes its source, window, denominator or explanation, and drill-down details. The page renders these strings without recalculating metrics. Usage buttons affect usage only.

## Source boundaries

Hypertask reads only the fields needed for delivery, with pagination and a seven-day update filter. Delivery never substitutes `updatedAt` for `sectionChangedAt`. Tickets count once overall, per board and once for each shared assignee. Unassigned tickets remain visible. This is a current-Done cohort, not an audit of all historical moves: reopened tickets are excluded and historical assignees are not available.

GitHub queries PRs updated within seven days, paging until older results. Comment pagination is completed before selecting the earliest verdict. Prose mentioning verdict names, quoted verdicts and fenced examples do not count. The tile lists its repository scope. `REPOS` follows the runner-pool repository list plus the companion and solo apps; `FACTORY_REPOS` can override that scope explicitly. Retrospective verdicts cannot repair the merge-coverage number.

Token-ladder's `pace_ratio` is the maximum eligible window ratio. Its `used_pct` and reset describe the limiting-usage window, which can be different. The page names that distinction and never invents a matching elapsed percentage. Plans with no pace ratio are explained and excluded from the pace denominator.

Drain health includes chief, lead and solo-dev roster rows, including missing sessions. The newest observation per roster name wins. An `ok` observation must also report the fire's age; an observation's timestamp alone is not a fire timestamp. Ages are rounded down by the watchdog, so the exporter adds one minute conservatively. Ordinary wakes, future observations and stale fires cannot establish health. No recent observations means unavailable, not zero healthy orchestrators.

`command_json` uses a 90-second per-call timeout and logs no raw CLI errors. The first complete live GitHub read took 45 seconds across 1,088 recently updated PRs; the first full exporter run took 67 seconds. These timings describe this host's observed source reads, not a benchmark claim.

## Remaining metric boundaries

The merge and verifier tiles share one PR snapshot per export. Merge duration includes draft time. Missing or backwards creation dates omit the merge tile rather than shrink its duration sample silently.

Identity uses `roster.hosted_chats()` to deduplicate reachable Multibot chats, then the same name-to-agent-token-file rule as `solo-wake.identity_gap`. No credential contents are read or exported. This measures identity provisioning, not which login a running CLI actually uses. Unnamed chats count as gaps; an empty inventory has no denominator and omits the tile. This source has no historical window.

Actions reads cover runs created in the rolling 24-hour window and completed by export time. Each run contributes its latest attempt. Cancelled, skipped, and neutral completed runs remain in the denominator. Explicit failed-job annotations classify infrastructure failures such as billing or runner loss, or code diagnostics such as TypeScript errors and failed assertions. Missing annotations and generic exit codes remain unclassified. The display includes that share so zero confirmed failures cannot imply zero actual failures. Search windows split recursively around GitHub's 1,000-run search limit. Failed suites are read in GraphQL batches of 20, keeping the maximum nested node count below GitHub's 500,000-node limit. Only latest check runs and failure-level annotations classify failures. Overflowing check or annotation connections fall back to complete REST pagination. Runs, jobs, annotations, deployment records, and statuses are paged explicitly without requiring a newer `gh --slurp` flag.

Merge-to-live uses the earliest successful deployment status for an exact merge SHA in an environment named `Production`, case-insensitively. The window is rolling 24 hours, and the budget is 15 minutes. Preview and `live-qa` deployments, mismatched SHAs, and pre-merge or future statuses do not count. A deployment receipt is not an HTTP probe. Repositories that deploy without GitHub Production receipts have no latency sample. The tile reports matched PRs over all 24-hour merges; its median covers only that observed subset. Missing deployment receipts never become zero minutes.

## Configuration and tests

The hourly wrapper's existing `ADVISOR_BIN` and `TOKEN_LADDER_STATUS` variables still supply Usage. KPIs additionally require the `hypertask`, `gh` and `token-ladder` executables on PATH, with read access to all scoped boards and repositories. No new key is needed.

Optional `FACTORY_ROSTER` and `FACTORY_LOOP_LOG` select the roster JSON and watchdog text log. Their defaults are the installed fleet files. These paths are never copied into the page. `FACTORY_REPOS` is a comma-separated `owner/repo` list.

Run the focused exporter test with `python3 -m unittest discover -s tools -p 'test_factory_kpis.py' -v`. It seeds ticket, PR, pool and loop facts, changes each source independently and checks only the corresponding tile changes. GitHub-hosted CI runs it alongside the existing full checks, tests and build.

## Current source gaps

The inspected advisor metric and violations caches were last written on 14 November. Their fixed windows, missing run attribution and missing runner-hours explain the old empty tiles. They are no longer KPI inputs.

At task start the live Hypertask API selected `sectionChangedAt` internally but omitted it from both task list and detail responses, even with an explicit field projection. The host's current CLI login also cannot read board 11514. Delivery stays omitted until both read access and Done-move dates are available. No upstream access or API changes are part of this PR.

Drain observations were absent initially while house-rules PR 576 was open. They appeared during this session, and the live exporter then produced a real drain-health tile. The collector remains honest when that log is absent or stale.

SOFT-2546 keeps the remaining omissions visible in the same `kpis.notes` path:

- Lead time (2), Done-cohort rework and reopen percentage (6), and cost per delivered ticket (8) need transition dates or history blocked by [HYCI-9390](https://app.hypertask.ai/detail/project-15/9390). Creation and update dates are not substitutes for first exit from Todo or entry into Done. Run counts without a dated delivered cohort do not establish rework. Plan subscriptions are not zero total cost.
- Escapes (5) needs both reverts and bug or incident tickets linking merged PRs. The exporter login still cannot read board 11514. A revert-only numerator would understate escapes, so no partial rate is published.
- Workers in flight versus slots (10) needs each coordinator's running count, cap, and actual shortfall reason. Installed `fleet/slots` is a pure decision command, not a saved observation. No per-coordinator tick receipts were found. Counting every busy chat against its default cap of ten would mix coordinators and non-workers.

## Work checklist

- [x] Trace the affected subsystem.
- [x] Compare a new KPI contract with reuse of advisor windows. Keep the existing tile contract and extend its allowed IDs; remove obsolete windows and chart fields.
- [x] Blocking first steps. Read source shapes and identify missing upstream facts.
- [x] Independent workstreams. No fan-out; this session owns the coupled exporter, schema and view.
- [x] Shared mutable state. Only this worktree changes; no production feed or checkout writes.
- [x] Smallest safe decomposition. One writer keeps fixture, exporter and page contracts together.
- [x] Implement source collectors and fixture tests.
- [x] Verify the exporter and page with seeded source facts.
- [x] Open draft PR early; leave deployment and merge to the owner.

Subagent design exploration and delegated implementation are skipped because this session has no delegation request. Full-suite testing belongs on GitHub-hosted runners.
