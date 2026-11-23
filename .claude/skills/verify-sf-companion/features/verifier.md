# Verifier selection

The PR verifier reads every `Author model:` line and picks a different model family. DeepSeek-authored changes use GLM Flash through the Vercel AI Gateway, not Kimi. If GLM also authored the change, the picker uses OpenAI; if every candidate authored it, selection fails closed.

Covers: ci:verifier-selection

Code paths: scripts/pick_verifier.py, scripts/test_pick_verifier.py, .github/workflows/pstack-verifier.yml

## Sub-features

- `verifier-selection` drives the picker CLI with DeepSeek, DeepSeek plus GLM, all candidate families, a Kimi author, and an unknown author.

## How to get to it (operator POV)

Add `Author model: deepseek/deepseek-v4.1-flash` to a pull request body. The workflow's selection step must emit `family: zai`, `model: zai/glm-5.3-flash`, `provider: vercel-ai-gateway`, and the `AI_GATEWAY_API_KEY` secret name.

## Driving it

Run `../run.sh --journeys=verifier-selection`, or run the same CLI journey directly from the repo root with `python3 .claude/skills/verify-sf-companion/verifier_selection.py .`. It needs no credentials and makes no provider requests.

The helper executes the checkout's `scripts/pick_verifier.py` through stdin, just as a PR body reaches the picker. It records the input, expected fields, and actual JSON for every case. `verifier-selection.json` and `result.json` retain the actions even when selection is wrong. This is a CLI case, so it has no browser trace.

## Reproduction

Drive the head helper against both checkouts. Base `dda22845e15545b166f9efb04b3011a3be0fb68b` selects `moonshotai/kimi-k3` for a DeepSeek author and fails this journey. The fixed checkout selects `zai/glm-5.3-flash` and passes, while preserving author-family exclusion and fail-closed handling. This proves selection, not model availability, billing, or gateway inference.
