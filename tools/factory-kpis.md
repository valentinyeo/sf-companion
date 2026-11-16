# Factory KPI sources

The Factory page reports output and waste from read-only source facts. The exporter writes a derived feed, not a second ledger.

| Metric | Authority | Measurement |
| --- | --- | --- |
| Tickets delivered | Hypertask boards 15, 2060, 11514 | Done-move date, grouped by board and assignee, rolling day and week |
| Verifier first pass | GitHub PR comments on fleet repos | First PASS or PASS+NOTES divided by PRs with a verdict; merged PRs without verdict shown separately |
| Plan pace | token-ladder pools | Used percentage divided by elapsed window percentage; above 1 is over pace |
| Drain-loop health | Fleet solo-wake observations and orchestrator roster | Orchestrators with externally observed scheduled turns in the last 45 minutes |

Missing Done-move dates must never fall back to ticket update dates. Ordinary wake messages are not scheduled loop fires. An unavailable source must not produce a measured zero.

## Work checklist

- [x] Trace the affected subsystem.
- [x] Compare a new KPI contract with reuse of the existing tile contract. Reuse the existing tile contract and remove unused advisor fields.
- [x] Blocking first steps. Read source shapes and identify missing upstream facts.
- [x] Independent workstreams. No fan-out; this session owns the coupled exporter, schema and view.
- [x] Shared mutable state. Only this worktree changes; no production feed or checkout writes.
- [x] Smallest safe decomposition. One writer keeps fixture, exporter and page contracts together.
- [ ] Implement source collectors and fixture tests.
- [ ] Verify the exporter and page with seeded source facts.
- [ ] Run checks, open draft PR and leave deployment to the owner.

Subagent design exploration and delegated implementation are skipped because this session has no delegation request. Full-suite testing belongs on GitHub-hosted runners.
