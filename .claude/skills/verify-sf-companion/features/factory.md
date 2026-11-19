# Factory readings and empty state

Factory shows plan usage and factory output readings with their source windows. A missing feed shows an explicit empty state.

## Sub-features

- `factory-entry` supports direct `/factory` loading and primary navigation.
- `factory-readings` shows seeded usage, output, and export time.
- `factory-empty` shows missing numbers without invented zeroes.
- `factory-shipping` shows daily shipped PRs against plan burn with a source per day.
- `factory-layout` fits desktop and mobile in both system color schemes.

Code paths: apps/web/src/features/factory.ts, apps/web/src/features/factory.stylex.ts, apps/web/src/content/factory.ts, apps/web/src/content/feed.ts, apps/web/src/features/page.ts

## How to get to it (user POV)

- Open `/factory` directly.
- Choose Factory in Primary navigation.
- Choose Factory from the home page's list.

## Driving it with Playwright

Preconditions:

- Run `../run.sh` with no live credentials. The helper seeds and removes the bundled feed in separate launches.

- Direct entry. `page.goto('/factory')` must return 200 and show `getByRole('heading', {name: 'Factory', exact: true})`.
- Primary navigation. Click `getByRole('link', {name: 'Software Factory Companion', exact: true})`, then `getByRole('navigation', {name: 'Primary navigation'}).getByRole('link', {name: 'Factory', exact: true})`. The Factory heading returns.
- Home list entry. From Home, use `page.getByRole('main').getByRole('link', {name: 'Factory', exact: true}).click()`. This is a manual extension, not part of the automated baseline.
- Seeded readings. Require the Fixture Plan heading, `Numbers from 2026-11-15 00:41 UTC`, and `29 / day · 87 / week`. The snapshot also records each KPI's source and measurement window.
- Missing feed. Require `No factory numbers yet.` and no Usage window group or Output and waste heading.
- Shipping chart. Require the `PRs shipped vs plan burn` heading, both seeded days, and `GitHub search · fleet mergedAt` after expanding the newest day.
- Proof. Read `seeded-1280-light.png`, `seeded-390-dark.png`, and the corresponding `empty-*` images and ARIA snapshots. All eight combinations must pass.

## Gotchas

- Feed input is bundled. Restart and rebuild after changing it; do not mock a nonexistent HTTP feed endpoint.
- Local access has no Cloudflare login. It does not prove production authentication.
- Synthetic readings are not current factory measurements.
