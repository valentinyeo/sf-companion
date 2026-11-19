# Verify-skill evaluation results

Newest run first. Each table comes from the `tabulate` job, which fails the run when a planted case is not `FAIL` or the clean case is `FAIL`.

## 2026-11-19 · run 44567344710

Run: https://github.com/valentinyeo/sf-companion/actions/runs/44567344710

| Family   | Case            | Expected | Actual     | Result |
| -------- | --------------- | -------- | ---------- | ------ |
| deepseek | clean           | PASS     | PASS+NOTES | ok     |
| deepseek | kpi-zero        | FAIL     | FAIL       | ok     |
| deepseek | report-link-404 | FAIL     | FAIL       | ok     |
| deepseek | mobile-overflow | FAIL     | FAIL       | ok     |
| openai   | clean           | PASS     | PASS+NOTES | ok     |
| openai   | kpi-zero        | FAIL     | FAIL       | ok     |
| openai   | report-link-404 | FAIL     | FAIL       | ok     |
| openai   | mobile-overflow | FAIL     | FAIL       | ok     |

8 cells, 0 mismatches. Both families passed the clean build and failed every planted bug. Their notes on the clean build name the `1 items.` copy and the skipped live gate.

## 2026-11-19 · run 44566324998

Run: https://github.com/valentinyeo/sf-companion/actions/runs/44566324998

Every planted case failed in both families. Both clean cells returned `FAIL` for one reason: the per-case screenshots were saved after the hub journeys, so `seeded-*.png` showed a stored item page instead of Factory. `verify.mjs` now saves the case screenshot and ARIA snapshot before driving the hub, and the next run above passed.
