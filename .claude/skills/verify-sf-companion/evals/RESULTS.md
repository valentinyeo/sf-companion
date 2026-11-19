# Verify-skill evaluation results

Newest run first. Each table comes from the `tabulate` job, which fails the run when a planted case is not `FAIL` or the clean case is `FAIL`.

## 2026-11-19 · run 44571190591

Run: https://github.com/valentinyeo/sf-companion/actions/runs/44571190591

| Family   | Case            | Expected | Actual | Result |
| -------- | --------------- | -------- | ------ | ------ |
| deepseek | clean           | PASS     | PASS   | ok     |
| deepseek | kpi-zero        | FAIL     | FAIL   | ok     |
| deepseek | report-link-404 | FAIL     | FAIL   | ok     |
| deepseek | mobile-overflow | FAIL     | FAIL   | ok     |
| openai   | clean           | PASS     | PASS   | ok     |
| openai   | kpi-zero        | FAIL     | FAIL   | ok     |
| openai   | report-link-404 | FAIL     | FAIL   | ok     |
| openai   | mobile-overflow | FAIL     | FAIL   | ok     |

8 cells, 0 mismatches. Both families passed the clean build and failed every planted bug.

## 2026-11-19 · run 44567344710

Both clean cells returned `PASS+NOTES`, with notes on the `1 items.` copy and the skipped live gate. Every planted case returned `FAIL`. This run predates the feature-map split in #15.

## 2026-11-19 · run 44566324998

Every planted case returned `FAIL`. Both clean cells returned `FAIL` because the per-case screenshot was saved after the hub journeys, so `seeded-*.png` showed a stored item page instead of Factory. #15 fixed that ordering on `main`, and the runs above passed on the new map.
