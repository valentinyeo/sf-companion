# Verify-skill evaluation

This folder proves that `verify-sf-companion` catches real regressions and does not cry wolf. A clean checkout must earn a pass, and every planted bug must earn a fail, judged by two model families that did not write the change.

`.github/workflows/verify-skill-eval.yml` runs on demand and weekly on `main`. It builds one job per case and family, under 20 jobs in total.

## Cases

`cases.json` holds families, cases, patches, and expected verdicts. `eval.py journeys` lists every feature-map journey except `access-anonymous`, which needs `run.sh --live`.

| Case | Patch | What a user would see | Expected |
| --- | --- | --- | --- |
| `clean` | none | nothing wrong | PASS or PASS+NOTES |
| `kpi-zero` | `patches/kpi-zero.patch` | every KPI without a state headline reads `0`, so a missing reading looks measured | FAIL |
| `report-link-404` | `patches/report-link-404.patch` | a report row on the home page opens a missing object and answers 404 | FAIL |
| `mobile-overflow` | `patches/chart-scroll-overflow.patch` | the shipping chart loses its scroll container and pushes the 390 wide page sideways | FAIL |

Families come from `scripts/pick_verifier.py` and the PR verifier: DeepSeek Flash on `opencode-go`, and Moonshot `moonshotai/kimi-k3` on `vercel-ai-gateway` (the Vercel Token Pass key covers no OpenAI or Google model). Each family judges every case, so one family's blind spot does not pass for proof.

## One cell

1. Check out the triggering ref.
2. Apply the case patch with `git apply` and commit it, so the run records no working-tree diff.
3. Drive the app with `.claude/skills/verify-sf-companion/run.sh --journeys=<all non-live journeys>`.
4. Delete the checkout and this folder from the runner before the model reads anything.
5. Install pi and ask the family for `PASS`, `PASS+NOTES`, or `FAIL` from the proof alone.

The model is blind. It sees the proof directory, at a neutral path, and a prompt that a reviewer could write about any run. The prompt does not name the case, the patch, this folder, the expectations, or the other family. The verdict parser is the one in `.github/workflows/pstack-verifier.yml`: the last assistant message, matched line by line.

## Pass rule

The `tabulate` job fails the run when a planted case gets anything other than `FAIL`, or when the clean case gets `FAIL`. `PASS+NOTES` on a planted case is a miss: the skill let a broken build through. A missing verdict is a miss too.

The job writes the expected and actual table to the run summary, uploads `eval-results`, and its conclusion is the record. `RESULTS.md` keeps the table of each real run, newest first.

## Run it

```sh
gh workflow run verify-skill-eval.yml --ref <branch>
gh run watch
```

Locally, the verdict parser can be exercised without models:

```sh
python3 .claude/skills/verify-sf-companion/evals/eval.py matrix --cases .claude/skills/verify-sf-companion/evals/cases.json
```

## Add a case

Write a patch against the app that a user would notice and `run.sh` would catch, save it under `patches/`, and add the case to `cases.json` with `"expect": "FAIL"`. Keep the matrix under 20 jobs: each case costs one job per family. `scripts/rules.test.ts` fails when a patch is not a case, a case has no patch, a family goes missing, or the workflow starts running on pull requests.
