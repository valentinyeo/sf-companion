# Remaining factory numbers (SOFT-2546)

## Goal

Show real factory output and waste on `/factory/`, using the existing tile contract and read-only sources. Missing facts stay explained omissions, never estimated zeros.

## Work plan

- [x] Read the Rat Stack principles index and trace the exporter, tile schema, and source adapters.
- [x] Blocking first steps. Inspect source shapes before selecting metrics.
- [x] Independent workstreams. No delegation requested; keep the coupled exporter and contract in one session.
- [x] Shared mutable state. Work only in `/tmp/sf-2546`; do not write to Hypertask, production feeds, or the hourly checkout.
- [x] Smallest safe decomposition. Reuse the tile registry and omission path instead of introducing a new reporting store.
- [ ] Open the draft PR before implementing collectors.
- [ ] Add available sources and seeded tile-isolation tests.
- [ ] Run Python tests and `pnpm run check` before each push. Full CI stays on GitHub-hosted runners.
- [ ] Record measured source coverage and omissions here and in the PR body.

## Data ownership

GitHub owns PR timestamps and Actions results. Fleet owns live chat observations, identity-gap rules, and slot decisions. Hypertask owns ticket transitions. The exporter is the only writer of the derived feed; this change does not add a ledger or replace upstream facts with update dates.
