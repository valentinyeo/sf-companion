# Verify-skill evaluation results

Newest run first. Each table comes from the `tabulate` job, which fails the run when a planted case is not `FAIL` or the clean case is `FAIL`.

## Current · 2026-11-19 · run 44640648906

- Run: https://github.com/valentinyeo/sf-companion/actions/runs/44640648906
- Commit: `a1f5637` (`eval(verify): drive the feature map's full journey set (SOFT-2866)`, PR [#30](https://github.com/valentinyeo/sf-companion/pull/30), merged to `main`)
- Journeys: all 43 non-live journeys the feature map lists, read by `eval.py journeys` instead of a hardcoded list

| Family   | Case            | Expected | Actual     | Result |
| -------- | --------------- | -------- | ---------- | ------ |
| deepseek | clean           | PASS     | PASS+NOTES | ok     |
| deepseek | kpi-zero        | FAIL     | FAIL       | ok     |
| deepseek | report-link-404 | FAIL     | FAIL       | ok     |
| deepseek | mobile-overflow | FAIL     | FAIL       | ok     |
| moonshot | clean           | PASS     | PASS+NOTES | ok     |
| moonshot | kpi-zero        | FAIL     | FAIL       | ok     |
| moonshot | report-link-404 | FAIL     | FAIL       | ok     |
| moonshot | mobile-overflow | FAIL     | FAIL       | ok     |

8 cells, 0 mismatches. Both families passed the clean build and failed every planted bug.

Clean notes, one line per family:

- DeepSeek (`opencode-go`, `deepseek-v4.1-flash`): all 43 journeys covered with no skipped journey and no case error, no horizontal overflow, only the expected `/no-such-page` 404 in the console; it flagged that sparse `/usage` still shows the `1h … 30d` selector above "No plans yet.", that stored report and exploration pages are raw unstyled bytes even in dark mode, and that some states exist only in trace frames, not in the saved PNGs.
- Moonshot (`vercel-ai-gateway`, `moonshotai/kimi-k3`): confirmed 43 journeys driven out of 43 listed, all 12 traces intact, assertions real, fixture scale matching the README's table; it flagged that empty and sparse Factory have no standalone PNG or ARIA, that the KPI disclosures are closed again in the final seeded snapshot, that the live Cloudflare check was skipped as the skill permits, and that the data is the synthetic fixture.

Evidence kept in the run's `eval-results` artifact and each cell's `drive.log`, `prompt.txt`, and `verdict.jsonl`.

## History

### 2026-11-19 · run 44623659426 · superseded

- Run: https://github.com/valentinyeo/sf-companion/actions/runs/44623659426
- Commit: `d004e90`, on `main` before PR [#30](https://github.com/valentinyeo/sf-companion/pull/30)

Drove 37 journeys from a hardcoded list in `cases.json`, while the feature map listed 43. The 1 mismatch was `deepseek clean: expected PASS, got FAIL`: DeepSeek read the proof and refused it because the sparse states, `items-invalid-slug`, and the trailing-slash index journeys were missing, leaving nine recorded cases where the map requires thirteen. Moonshot missed the same gaps and returned `PASS+NOTES`. Every planted case failed for both families. PR #30 made the eval read the map, and the run above is the proof.

| Family   | Case            | Expected | Actual     | Result   |
| -------- | --------------- | -------- | ---------- | -------- |
| deepseek | clean           | PASS     | FAIL       | mismatch |
| deepseek | kpi-zero        | FAIL     | FAIL       | ok       |
| deepseek | report-link-404 | FAIL     | FAIL       | ok       |
| deepseek | mobile-overflow | FAIL     | FAIL       | ok       |
| moonshot | clean           | PASS     | PASS+NOTES | ok       |
| moonshot | kpi-zero        | FAIL     | FAIL       | ok       |
| moonshot | report-link-404 | FAIL     | FAIL       | ok       |
| moonshot | mobile-overflow | FAIL     | FAIL       | ok       |

8 cells, 1 mismatch.

### 2026-11-19 · run 44571190591 · superseded

- Run: https://github.com/valentinyeo/sf-companion/actions/runs/44571190591

Ran the `openai` family before the token pass moved the second family to Moonshot. 8 cells, 0 mismatches: both families passed the clean build and failed every planted bug.

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

### 2026-11-19 · run 44567344710 · superseded

Both clean cells returned `PASS+NOTES`, with notes on the `1 items.` copy and the skipped live gate. Every planted case returned `FAIL`. This run predates the feature-map split in #15.

### 2026-11-19 · run 44566324998 · superseded

Every planted case returned `FAIL`. Both clean cells returned `FAIL` because the per-case screenshot was saved after the hub journeys, so `seeded-*.png` showed a stored item page instead of Factory. #15 fixed that ordering on `main`, and the runs above passed on the new map.
