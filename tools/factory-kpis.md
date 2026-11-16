# Factory KPI sources

The Factory page reports output and waste from read-only source facts. The exporter writes a derived feed, not a second ledger. It does not refresh advisor caches or modify upstream state.

| Metric | Authority | Measurement |
| --- | --- | --- |
| Tickets delivered | Hypertask boards 15, 2060, 11514 | Current Done tickets, using Done-move date, grouped by board and current assignee, rolling day and week |
| Verifier first pass | GitHub issue comments on fleet PRs | First PASS or PASS+NOTES divided by PRs whose first verdict arrived in rolling 7d |
| Merge coverage | Same GitHub comments | Merged PRs in rolling 7d without a verdict present at merge time, divided by merged PRs |
| Plan pace | token-ladder pools | Maximum used percentage divided by elapsed percentage across eligible plan windows; above 1 is over pace |
| Drain-loop health | Fleet solo-wake observations and orchestrator roster | Roster orchestrators with externally observed scheduled turns in the last 45 minutes |

Missing sources drop their tile and produce an explanation. They never produce a measured zero. A source failure does not hide other metrics. Every exported tile includes its source, window, denominator or explanation, and drill-down details. The page renders these strings without recalculating metrics. Usage buttons affect usage only.

## Source boundaries

Hypertask reads only the fields needed for delivery, with pagination and a seven-day update filter. Delivery never substitutes `updatedAt` for `sectionChangedAt`. Tickets count once overall, per board and once for each shared assignee. Unassigned tickets remain visible. This is a current-Done cohort, not an audit of all historical moves: reopened tickets are excluded and historical assignees are not available.

GitHub queries PRs updated within seven days, paging until older results. Comment pagination is completed before selecting the earliest verdict. Prose mentioning verdict names, quoted verdicts and fenced examples do not count. The tile lists its repository scope. `REPOS` follows the runner-pool repository list plus the companion and solo apps; `FACTORY_REPOS` can override that scope explicitly. Retrospective verdicts cannot repair the merge-coverage number.

Token-ladder's `pace_ratio` is the maximum eligible window ratio. Its `used_pct` and reset describe the limiting-usage window, which can be different. The page names that distinction and never invents a matching elapsed percentage. Plans with no pace ratio are explained and excluded from the pace denominator.

Drain health includes chief, lead and solo-dev roster rows, including missing sessions. The newest observation per roster name wins. An `ok` observation must also report the fire's age; an observation's timestamp alone is not a fire timestamp. Ages are rounded down by the watchdog, so the exporter adds one minute conservatively. Ordinary wakes, future observations and stale fires cannot establish health. No recent observations means unavailable, not zero healthy orchestrators.

`command_json` uses a 90-second per-call timeout and logs no raw CLI errors. The first complete live GitHub read took 45 seconds across 1,088 recently updated PRs; the first full exporter run took 67 seconds. These timings describe this host's observed source reads, not a benchmark claim.

## Configuration and tests

The hourly wrapper's existing `ADVISOR_BIN` and `TOKEN_LADDER_STATUS` variables still supply Usage. KPIs additionally require the `hypertask`, `gh` and `token-ladder` executables on PATH, with read access to all scoped boards and repositories. No new key is needed.

Optional `FACTORY_ROSTER` and `FACTORY_LOOP_LOG` select the roster JSON and watchdog text log. Their defaults are the installed fleet files. These paths are never copied into the page. `FACTORY_REPOS` is a comma-separated `owner/repo` list.

Run the focused exporter test with `python3 -m unittest discover -s tools -p 'test_factory_kpis.py' -v`. It seeds ticket, PR, pool and loop facts, changes each source independently and checks only the corresponding tile changes. GitHub-hosted CI runs it alongside the existing full checks, tests and build.

## Current source gaps

The inspected advisor metric and violations caches were last written on 14 November. Their fixed windows, missing run attribution and missing runner-hours explain the old empty tiles. They are no longer KPI inputs.

At task start the live Hypertask API selected `sectionChangedAt` internally but omitted it from both task list and detail responses, even with an explicit field projection. The host's current CLI login also cannot read board 11514. Delivery stays omitted until both read access and Done-move dates are available. No upstream access or API changes are part of this PR.

Drain observations were absent initially while house-rules PR 576 was open. They appeared during this session, and the live exporter then produced a real drain-health tile. The collector remains honest when that log is absent or stale.

## Work checklist

- [x] Trace the affected subsystem.
- [x] Compare a new KPI contract with reuse of advisor windows. Keep a small four-ID tile contract; remove obsolete windows and chart fields.
- [x] Blocking first steps. Read source shapes and identify missing upstream facts.
- [x] Independent workstreams. No fan-out; this session owns the coupled exporter, schema and view.
- [x] Shared mutable state. Only this worktree changes; no production feed or checkout writes.
- [x] Smallest safe decomposition. One writer keeps fixture, exporter and page contracts together.
- [x] Implement source collectors and fixture tests.
- [x] Verify the exporter and page with seeded source facts.
- [x] Open draft PR early; leave deployment and merge to the owner.

Subagent design exploration and delegated implementation are skipped because this session has no delegation request. Full-suite testing belongs on GitHub-hosted runners.
