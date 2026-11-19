# Caught bugs

Recent bugs an agent caught, and whether the owner saw them first. This is the evidence for audit item 2, "Human is not the verifier": the verifier and the orchestrator's live check found these, and the owner read about them after the fix rather than while the defect was live.

One row per bug: the date, the pull request, what was wrong, which check caught it, whether the owner saw it, and a link to the check's own words.

Verify a row against GitHub before adding it. Read the `pstack-verifier` comments with `gh pr view <n> --json comments`, and for a live defect read the revert pull request body. Do not write a row from memory or from a summary.

| Date | PR | What was wrong | Caught by | Owner saw it | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-11-19 | [#10](https://github.com/valentinyeo/sf-companion/pull/10) | The `explorations-item` journey was requested but never driven: `driveHub` stopped at the explorations index, so no screenshot or ARIA snapshot covered a stored exploration. | pstack verifier, `openai/gpt-6.1-sol` | No. Fixed before merge. | [verifier FAIL](https://github.com/valentinyeo/sf-companion/pull/10#issuecomment-7013529023) |
| 2026-11-19 | [#14](https://github.com/valentinyeo/sf-companion/pull/14) | The release gate accepted a one-byte file renamed `.trace.zip` as a journey's trace, and excused any journey listed in `untraced` with no reason and no trace, so a deploy could pass with no browser evidence. | pstack verifier, `openai/gpt-6.1-sol` | No. Fixed before merge. | [verifier FAIL](https://github.com/valentinyeo/sf-companion/pull/14#issuecomment-7014943700) |
| 2026-11-19 | [#18](https://github.com/valentinyeo/sf-companion/pull/18) | The weekly maintain job checked the pstack, model verdict and checkout outcomes but not `JOURNEYS_OUTCOME`, so a `CLEAN` verdict could report the map clean and close the drift issue after a failed journey run. | pstack verifier, `openai/gpt-6.1-sol` | No. Fixed before merge. | [verifier FAIL](https://github.com/valentinyeo/sf-companion/pull/18#issuecomment-7016430455) |
| 2026-11-19 | [#19](https://github.com/valentinyeo/sf-companion/pull/19) | After the merge went live, `/reports/` and `/explorations/` answered 400 instead of the index, because no journey drove an index with a trailing slash. Reverted in #21 thirty-one minutes after #19 merged. | Orchestrator post-deploy live check | No. The owner never reported it. | [revert body](https://github.com/valentinyeo/sf-companion/pull/21) |
| 2026-11-19 | [#21](https://github.com/valentinyeo/sf-companion/pull/21) | The revert called `decodeURIComponent` without the earlier exception handling, so `/reports/%FF` threw `URIError` and answered 500 where the base answered 400. | pstack verifier, `openai/gpt-6.1-sol` | No. Fixed in the same pull request before merge. | [verifier FAIL](https://github.com/valentinyeo/sf-companion/pull/21#issuecomment-7018651922) |
| 2026-11-19 | [#24](https://github.com/valentinyeo/sf-companion/pull/24) | The verifier returned no verdict line at all: the response was an empty trace, because the OpenRouter account was out of credit. The pull request sat unverified rather than verified. | Orchestrator, from the run record | No. Verifier moved to the Vercel AI Gateway (#25) and Kimi K3 for DeepSeek-authored pull requests (#26). | [verifier FAIL](https://github.com/valentinyeo/sf-companion/pull/24#issuecomment-7021377689) |

## What the rows show

Every row was caught by a check, not by the owner reading the site. Five were caught before a merge and fixed there. One reached production and was reverted inside the hour by the same live check that found it. One showed that a verifier that cannot answer is a defect of its own, and the fix moved the verifier rather than the pull request.
