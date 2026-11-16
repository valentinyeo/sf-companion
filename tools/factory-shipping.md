# PRs shipped vs plan burn (SOFT-2552)

Compare daily fleet merges with plan burn over 30 UTC dates, including today to export time. GitHub `mergedAt` is the delivery date. Reuse the paginated PR collector with a 30-day lookback; do not query Hypertask for this chart.

The exporter owns a `shipping` read model. Each day has measured or unavailable cells with display text, source and window. Daily plan points come from advisor `daily_burn.readings` and `rises`, not differences between rolling feed windows. Points are separate per plan, never added across plans. These are observed quota points, not token counts or complete daily consumption. Gaps and absent history remain visible.

GBP comes from advisor metric `days[date].spent`, the attributed priced subset, not the total subscription bill or API list-price tokens. Cost per merged PR divides that day's attributed pounds by that day's fleet merges. It is a fleet efficiency comparison, not causal attribution to individual PRs. No merges means no denominator. Missing prices or dates mean unavailable, not free.

The page renders one semantic table chart with independent bar scales for merges and each plan. Exact values and provenance remain readable without color, hover or scripting. The table scrolls within a focusable labelled region on narrow screens and uses the existing light/dark tokens.

Work is serialized in the dedicated worktree. The blocking step is tracing daily source semantics. Exporter, schema and view form one coupled change, so there is one writer. Seeded Python fixtures prove date boundaries, missing sources and division; Foldkit Scene tests prove the reader sees values and gaps. Run the repository check, Python tests and web Vitest before each push. No deployment, merge or Hypertask writes.
