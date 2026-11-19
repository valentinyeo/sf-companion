# Factory page

The Factory page is reachable at a stable URL, carries the site navigation, and stamps the moment its numbers were exported. It is server-rendered at `/factory` and hydrates in the browser.

Covers: route:Factory

Code paths: apps/web/src/features/factory.ts, apps/web/src/features/page.ts, apps/web/src/features/route.ts, apps/web/src/content/feed.ts, apps/web/src/entry.server.ts

## Sub-features

- `factory-entry` loads `/factory` directly and reaches it from primary navigation.
- `factory-layout` fits desktop and mobile in both system color schemes.
- `factory-timestamp` prints the feed's export time in UTC.

## How to get to it (user POV)

- Open `/factory` directly.
- Choose Factory in Primary navigation.
- Choose `Open` in the Factory section on Home.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. The helper seeds `fixture.json` as the bundled feed and starts the site on an unused loopback port.

- Direct entry. `page.goto('/factory')` must return 200 and show `getByRole('heading', {name: 'Factory', exact: true})`.
- Identity. Require the `Software Factory Companion` link in Primary navigation and the color scheme the context asked for.
- Navigation. Choose the site name, then `Factory` in `getByRole('navigation', {name: 'Primary navigation'})`. The Factory heading returns.
- Export time. Require `Numbers from 2026-11-15 00:41 UTC`, exact.
- Layout. Each case records the document width against the viewport; a horizontal overflow fails the case. Cases run at 1280×900 and 390×844, light and dark.
- Proof. Read `seeded-1280-light.png`, `seeded-390-dark.png`, and the corresponding `empty-*` images and ARIA snapshots.

## Gotchas

- Feed input is bundled. Restart and rebuild after changing it; do not mock a nonexistent HTTP feed endpoint.
- Local access has no Cloudflare login. It does not prove production authentication.
- The export time is synthetic and fixed. A stale timestamp means the fixture did not reach the build.
