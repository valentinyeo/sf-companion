# Usage windows and details

Usage buttons change the burn window without changing factory output readings. Disclosure controls reveal additional plan and measurement details.

## Sub-features

- `usage-window` selects 1h, 3h, 6h, 12h, 24h, 7d, and 30d.
- `usage-burn` changes the displayed burn to match the selected window.
- `usage-kpi-fixed` preserves each KPI's own measurement window.
- `usage-details` expands Windows and Measurement details.

Code paths: apps/web/src/features/factory.ts, apps/web/src/client/app/model.ts, apps/web/src/client/app/message.ts, apps/web/src/client/app/update.ts

## How to get to it (user POV)

- Open Factory with a feed present.
- Use the buttons below Usage.
- Open Windows on Fixture Plan or Measurement details on Tickets delivered.

## Driving it with Playwright

Preconditions:

- Run `../run.sh`. These actions run for each seeded viewport and color scheme.

- Baseline. Require `+2% · £0.00 in 1h on runners`. Capture `seeded-<width>-<theme>-before.png`.
- Select. For each window, click `page.getByRole('group', {name: 'Usage window'}).getByRole('button', {name: window, exact: true})`. Require that button's `aria-pressed` to become `true`.
- Read burn. On 7d, require `+14% · £7.00 in 7d on runners`. The helper returns to 1h after exercising every button.
- Read output. Require `29 / day · 87 / week` after every selection.
- Expand plan. Click `getByText('Windows', {exact: true})`; require `Weekly 67%` to be visible.
- Expand measurement. Click `getByText('Measurement details', {exact: true})`; require `Synthetic third measurement detail` to be visible.
- Proof. Save the final full-page screenshot, ARIA snapshot, and action log under `seeded-<width>-<theme>.*`. Compare the before image with the expanded final image.

## Gotchas

- Buttons affect usage burn only. KPI numbers must not follow them.
- A selected button alone does not prove client hydration. The changed 7d reading must appear.
- Hidden disclosure text is not proof of expansion. Require visibility.
