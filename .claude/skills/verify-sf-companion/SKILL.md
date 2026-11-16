---
name: verify-sf-companion
description: Drive the Software Factory Companion web UI with Playwright, verify seeded and missing factory feeds, and save browser proof. Use after changing the companion site or before reviewing it.
---

# Verify Software Factory Companion

## Launch

From the repository root, run:

```sh
.claude/skills/verify-sf-companion/run.sh
```

The helper copies this checkout into a disposable directory, excluding Git state, dependencies, generated output, and the host feed. It installs with `pnpm install --frozen-lockfile --ignore-scripts`, builds each feed state with `pnpm --filter @sf-companion/web build`, then starts Vite with `PORTLESS=0` on an unused loopback port. A disposable Vite config names `src/client/entry.ts` as the dependency-scan entry. This lets Vite find dependencies before browser requests, avoiding cold-cache 504 errors on this SSR-only app. The production Vite config is unchanged. No certificates, proxy changes, credentials, deployment, or board writes are needed. Node and pnpm versions are pinned in `package.json`; older versions can warn. Ignoring install scripts avoids lefthook's global `core.hooksPath` conflict.

Playwright is pinned and installed in disposable tooling, outside the workspace dependency graph. Chromium must be available; the helper installs its matching browser without system dependencies. If host libraries are missing, report the launch error rather than changing the system.

Set `PROOF_DIR` to a new absolute directory to choose the evidence location. Otherwise the helper creates `/tmp/sf-companion-proof.XXXXXX`. It prints that path before doing work. Never use the deploy checkout. Concurrent runs have separate source copies, ports, browsers, and proof directories.

## Doctor

The helper waits for its own Vite readiness log, then loads `/factory` and requires HTTP 200, the `Factory` heading, and the `Software Factory Companion` navigation link. A responding socket alone is not readiness. Check `seeded-dev.log` or `empty-dev.log` in the proof directory when this fails. Do not attach to another process or bypass Cloudflare Access.

## Drive

Read [the feature map](features/README.md). The helper uses Chromium and real browser actions against the local app. It checks both feed states at 1280×900 and 390×844, with `prefers-color-scheme` set to `light` and `dark`. It navigates through the primary `Factory` link, changes usage windows, and opens native disclosure controls. Feed data enters through the existing build-time JSON file, never internal model setters or intercepted responses.

## Evidence

Each case saves a full-page PNG, an ARIA snapshot, and a JSON action/result log. Browser console errors, uncaught page errors, failed local responses, or horizontal document overflow fail the run. `result.json` records the revision, matrix results, and overall status. Build and development logs survive failures too. Read the images before claiming visual quality; automated layout checks do not judge appearance.

For the optional anonymous live boundary check:

```sh
.claude/skills/verify-sf-companion/run.sh --live
```

This also requests `https://yeoux.net/factory/` without cookies and without following redirects. Require a redirect to a Cloudflare Access login URL. Save only status and destination origin/path, not signed query parameters. This proves the anonymous gate, not authenticated production behavior.

## Cleanup

The helper stops only process groups it started and removes its disposable checkout and tooling on success or failure. Proof is outside scratch storage and survives cleanup. Never kill processes by name. An interrupted run is not a pass; inspect `result.json` and the logs.

## Helpers

- `run.sh` launches the complete verification from any working directory.
- `verify.mjs` builds and drives the disposable copy. Invoke it through `run.sh`, which supplies its isolated dependencies and paths.
- `fixture.json` is synthetic build input, not live factory data.

Keep this skill and its feature map aligned with the app using `/maintain-verification-skill`.
