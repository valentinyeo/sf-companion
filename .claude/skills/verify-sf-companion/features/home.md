# Home

Home is the hub's front page: the title, an Explorations section, a Reports section, and a Factory section. Each section shows its newest rows and a link to its full list.

## Sub-features

- `home-sections` shows both hub sections with their rows.
- `home-links` sends each row to its item and each section heading to its index.
- `home-empty` says a section holds nothing instead of rendering a blank list.

## How to get to it (user POV)

- Open `/`.
- Choose the site name in Primary navigation from any page.

## Driving it with Playwright

Preconditions:

- Run `../run.sh` with no live credentials. The helper seeds `fixture-hub/` as `apps/web/content/hub/` for the seeded launch and removes it for the empty launch.

- Seeded. Require the `Software Factory Companion` heading, the `Explorations` and `Reports` headings, the links `Client pricing review`, `Retainer summary`, and `Motion study`, and the `All 2` link under Reports.
- Section link. Choose Reports in Primary navigation and require the Reports index.
- Empty. Require `No explorations yet.` and `No reports yet.` and no item links.
- Proof. Read `hub-seeded-1280-light.png` and `hub-seeded-390-dark.png` for the hub look.

## Gotchas

- Rows come from the hub content store. Local launches read `apps/web/content/hub/`, which stands in for the R2 bucket; a deployed Worker reads R2 through its `CONTENT` binding.
- The seeded titles are synthetic. They are not client work.
