# KPI tiles

Output and waste shows one tile per metric. Each tile carries its own display, source, measurement window, state cue, and — when the feed holds more than two details — a Measurement details disclosure.

Covers: factory:output-and-waste

Code paths: apps/web/src/features/factory.ts, apps/web/src/content/feed.ts, apps/web/src/client/app/model.ts

## Sub-features

- `kpi-tiles` shows all seven tiles with their displays, sources, and state cues.
- `kpi-windows` keeps every tile's own measurement window; on a revision with `/usage`, Factory holds no usage window buttons.
- `kpi-details` expands a tile's Measurement details disclosure.

## How to get to it (user POV)

- Open Factory with a feed present, then read the Output and waste section.
- Open Measurement details on Tickets delivered.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The fixture carries one tile per schema id: delivered, verifier, pace, loops, merges, identity, ci.

- Tiles. Require the headings `Tickets delivered`, `Verifier first-pass rate`, `Plan usage pace`, `Drain-loop health`, `PR throughput and merge time`, `Chat identity sync`, `CI health`. Inside each tile require its display: `29 / day · 87 / week`, `75%`, `2/3 over pace`, `3 loops fired in 45m`, `1 / day · 3 / week · 20.0 min median`, `50%`, and `– to live · 0% confirmed infra · 0% confirmed code · 50% unclassified`.
- Sources. Inside Tickets delivered require `Hypertask boards 15, 2060, 11514 · sectionChangedAt` and `Rolling 24h and 7d`.
- Cues. Inside Plan usage pace and Chat identity sync require `off target`. Inside Drain-loop health require `on target`.
- Windows. After driving every usage window on `/usage`, open `/factory` and require Tickets delivered to still show `Rolling 24h and 7d`, Drain-loop health to still show `Rolling 45m`, and no `Usage window` group.
- Details. Before expanding, require `Synthetic third measurement detail` to be hidden inside Tickets delivered. Click that tile's `Measurement details` and require the text visible. The same Journey for Plan usage pace proves a second tile keeps its own disclosure.
- Proof. The per-case ARIA snapshot records every tile and cue.

## Gotchas

- A tile's window is its own; the usage buttons on `/usage` change burn only.
- `state: null` renders no cue. A missing cue is not a failed tile.
- Details past the second are hidden until the disclosure opens; `getByText` alone matches hidden text, so require visibility.
