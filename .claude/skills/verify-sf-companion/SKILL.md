---
name: verify-sf-companion
description: Drive the Software Factory Companion web UI with Playwright, verify the seeded and missing factory feeds plus the hub, share endpoint, and stored items, and save browser proof. Use after changing the companion site or before reviewing it.
---

# Verify Software Factory Companion

pstack: 0.15.46

## Launch

From the repository root, run:

```sh
.claude/skills/verify-sf-companion/run.sh
```

The helper copies this checkout into a disposable directory, excluding Git state, dependencies, generated output, the host feed, and any host copy of the hub content store. It installs with `pnpm install --frozen-lockfile --ignore-scripts`, builds each feed state (seeded, empty, and sparse) with `pnpm --filter @sf-companion/web build`, then starts Vite with `PORTLESS=0` on an unused loopback port. A disposable Vite config names `src/client/entry.ts` as the dependency-scan entry. This lets Vite find dependencies before browser requests, avoiding cold-cache 504 errors on this SSR-only app. The production Vite config is unchanged. No certificates, proxy changes, credentials, deployment, or board writes are needed. Node and pnpm versions are pinned in `package.json`; older versions can warn. Ignoring install scripts avoids lefthook's global `core.hooksPath` conflict.

The seeded launch sets `SF_SHARE_TOKEN=verify-share-token`, the local stand-in for the Worker's `SHARE_TOKEN` binding, so the share journeys can write to the disposable content store. It never runs against the deploy checkout or a real token.

The empty launch removes the feed file and the hub store. The sparse launch keeps a real feed and drops one block from it: `usage.cards` is emptied and `kpis.shipping` is removed, while the KPI unavailability notes stay. That is how the unavailability states get driven without inventing a zeroed feed.

Playwright is pinned and installed in disposable tooling, outside the workspace dependency graph. Chromium must be available; the helper installs its matching browser without system dependencies. If host libraries are missing, report the launch error rather than changing the system.

Set `PROOF_DIR` to a new absolute directory to choose the evidence location. Otherwise the helper creates `/tmp/sf-companion-proof.XXXXXX`. It prints that path before doing work. Never use the deploy checkout. Concurrent runs have separate source copies, ports, browsers, and proof directories.

A full run drives every journey. To drive only the journeys a change touches, pass their ids from the feature map's sub-features:

```sh
.claude/skills/verify-sf-companion/run.sh --journeys=factory-entry,shipping-chart
```

Unknown ids fail before any install. The selected ids are recorded in `result.json`. A checkout that predates a page declares no route for it; those journeys are listed under `skipped` in `result.json` with the missing route as the reason, and every other journey still runs. The revision that adds the page always drives them.

## Doctor

The helper waits for its own Vite readiness log, then loads `/factory` and requires HTTP 200, the `Factory` heading, and the `Software Factory Companion` navigation link. A responding socket alone is not readiness. Check `seeded-dev.log` or `empty-dev.log` in the proof directory when this fails. Do not attach to another process or bypass Cloudflare Access.

## Drive

Read [the feature map](features/README.md). The helper uses Chromium and real browser actions against the local app. It checks the seeded, empty, and sparse states at 1280×900 and 390×844, with `prefers-color-scheme` set to `light` and `dark`. It reads Home, both hub indexes, one stored report, one stored exploration, the factory readings and the 30-date shipping chart at `/factory`, all seven usage cards and every usage window at `/usage`, all seven KPI tiles, and native disclosure controls. It drives item serving and the share endpoint over the same server's HTTP contract. Data enters through the files production reads: the factory feed JSON and the hub content store, never internal model setters or intercepted responses.

Each journey records its own actions, tagged with its id. Before the run starts, `verify.mjs` fails if a feature file lists a sub-feature id that no `wants("<id>")` gate covers. At the end it fails if a requested journey recorded no action, so a journey that is listed but never driven cannot pass.

## Evidence

Each case saves a full-page PNG of the page its drives ended on, a final-page PNG, an ARIA snapshot of each, a Playwright trace (`.trace.zip`), and a JSON action/result log. Open a trace with `pnpm exec playwright show-trace <file>`; it replays every action with its DOM snapshot. `traces.json` names the trace files that cover each journey and lists the journeys a browser cannot trace; `untraced.json` is the only place that list lives, so the gate reads it from the skill rather than from the artifact. Browser console errors, uncaught page errors, failed local responses, or horizontal document overflow fail the run. `result.json` records the revision, matrix results, and overall status. The seeded share case drives the HTTP share API, so it logs its own `seeded-share.json` and records no browser trace. Build and development logs survive failures too. Read the images before claiming visual quality; automated layout checks do not judge appearance.

A deploy needs this evidence: `scripts/release_gate.py` fails when a journey a pulled-in feature changed has no trace or video. A trace counts only when its case log names that journey and its `trace.trace` holds a recorded browser action or frame; a video counts only when its EBML header reads as webm or matroska.

For the optional anonymous live boundary check:

```sh
.claude/skills/verify-sf-companion/run.sh --live --journeys=access-anonymous
```

This also requests `https://yeoux.net/factory/` without cookies and without following redirects. Require a redirect to a Cloudflare Access login URL. Save only status and destination origin/path, not signed query parameters. This proves the anonymous gate, not authenticated production behavior.

## Cleanup

The helper stops only process groups it started and removes its disposable checkout and tooling on success or failure. Proof is outside scratch storage and survives cleanup. Never kill processes by name. An interrupted run is not a pass; inspect `result.json` and the logs.

## Helpers

- `run.sh` launches the verification from any working directory, in full or for the journeys named by `--journeys`.
- `verify.mjs` builds and drives the disposable copy. Invoke it through `run.sh`, which supplies its isolated dependencies and paths.
- `fixture.json` is synthetic build input, not live factory data. It holds 30 days of shipping rows, all seven KPI tiles, eight KPI notes, seven usage cards, every usage window, and five shipping notes, which is the production scale recorded in the [feature map](features/README.md#scale). The sparse launch writes a copy of it with `usage.cards` emptied and `kpis.shipping` dropped, so it stays the one feed fixture to keep current.
- `fixture-hub/` is a synthetic hub content store laid out like the R2 bucket: `index.json` lists object keys with their metadata, and each object file sits under its `x/` or `r/` prefix. It holds ten items per section.
- [CAUGHT.md](CAUGHT.md) logs the recent bugs a check caught before the owner saw them, one row per bug: the date, the pull request, what was wrong, which check caught it, and whether the owner saw it. It is evidence for the audit, not a gate, so add a row only after you have read the pull request's `pstack-verifier` comments or, for a live defect, the revert body.
- `scripts/feature_coverage.py` derives the real feature list from source and fails when a feature lacks a file here or the coverage line in `features/README.md` goes stale. Run `scripts/feature_coverage.py --write` after adding or removing a feature.

Keep this skill and its feature map aligned with the app using `/maintain-verification-skill`.
