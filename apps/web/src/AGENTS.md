# Foldkit site

Rules for browser code under `apps/web/src/client/` and `apps/web/src/features/`. Server and build modules follow the root `AGENTS.md`.

## Keep one direction of data flow

- Define the Model with Effect Schema. The Model owns browser state; the server owns durable facts.
- Define Messages with `defineMessageUnion` and match every variant.
- Name Messages after facts: `SelectedKpiWindow`.
- Keep `init`, `update`, and `view` pure. `update` returns the next Model and optional Commands.
- Put I/O in named `Command.define` definitions. A Command returns a result Message, including a typed failure Message.
- Pass the typed HTML builder as the last view argument.

## Folders

| Home | Responsibility |
| --- | --- |
| `src/content/item.ts` | The `Item` Schema, section prefixes, slug titles, and listing helpers |
| `src/content/bucket.ts` | The structural type of the R2 bucket binding, so no Workers types package is needed |
| `src/content/hub.ts` | The hub store: the R2 bucket adapter and the local file adapter that stands in for it |
| `src/content/share.ts` | The item surface: GET bytes, PUT upload, DELETE, slug and header rules |
| `src/content/feed.ts` | The `FactoryFeed` Schema, the `FeedError` failure, and decoding |
| `src/content/factory.ts` | Reads the one exported feed file and decodes it at load, or yields null |
| `src/features/route.ts` | The page route union and its Routers; URLs come from calling a Router as a printer |
| `src/features/page.ts` | The page view; it composes the template's `reader.stylex.ts` and base sheet |
| `src/features/hub.stylex.ts` | StyleX styles for the home and index rows only |
| `src/features/factory.ts` | The `/factory` view: the PRs shipped versus plan burn chart, the KPI tiles, and the link to Usage |
| `src/features/usage.ts` | The `/usage` view: plan cards, fixed 1h burn, and the Windows disclosure |
| `src/features/cue.ts` | The state cue and the class helper shared by the factory and usage views |
| `src/features/factory.stylex.ts` | StyleX styles for the factory and usage views |
| `src/client/rat.css` | The template's base sheet: monospace type, 80ch measure, grid, focus ring |
| `src/client/app/` | Model, Messages, named Commands, and `update` |
| `src/client/entry.ts` | Browser runtime boot and hydration |
| `src/entry.server.ts` | Route dispatch: item bytes and share endpoints first, then server rendering, `prerenderPaths`, and 404 handling |
| `src/platform.d.ts` | The `cloudflare:workers` module and the `CONTENT` and `SHARE_TOKEN` bindings it carries |
| `src/website.ts` | The Cloudflare `Website` resource; never import it into browser code |

The route travels from `entry.server.ts` to the browser as Foldkit Flags, so the hydrating client boots from the same Model.

## Content

Home, Explorations, and Reports read the `yeoux-site-content` R2 bucket: `x/` holds explorations, `r/` holds reports, and `d/` belongs to the dash app and is never read here. Each object's custom metadata carries `date`, `project`, and `title`, and `content/item.ts` falls back to the slug and the upload date when a field is missing. The same bucket also opens the same Access service token, so the hub and `yeoshare` read one list.

The bucket is the only durable fact. Indexes are derived from a listing on every request, so an upload appears on the next page load and never needs an index write.

An item URL serves the stored object's bytes with its own content type, `private, no-store`, and no site chrome. Upload and delete are the same contract `yeoshare` already sends: `PUT` and `DELETE` on `/<section>/<slug>` with `Authorization: Bearer <SHARE_TOKEN>` and the `X-Title`, `X-Project`, and `X-Date` headers.

When no `CONTENT` binding exists (a local dev server or a test), `content/hub.ts` reads `apps/web/content/hub/`: an `index.json` listing object keys with their metadata, plus one file per object under its prefix. That folder is gitignored and only ever holds fixtures.

The factory numbers are one exported file, `apps/web/content/feed/factory.json`, decoded at load by `content/feed.ts`. It is not committed: when it is missing the site still builds and `/factory` shows the line `No factory numbers yet.` The exporter owns every state and every pre-formatted display string; the view writes numbers as text, dates, and bar heights, and decides nothing.

## Visual rules

StyleX for authored styles, over the template's untouched base sheet in `src/client/rat.css`. The base sheet and `tokens.stylex.ts` own every colour, font, size, spacing, and radius. Hot pink marks the focus ring and nothing else. No Tailwind, UI kits, or chart libraries. The factory chart is plain elements in the view.

A state (`ok`, `bad`, `warm`, `hot`) always carries a word or a count next to its colour, so it reads without colour.

## Tests

`apps/web/test/` holds behaviour tests through Foldkit Scene and `@effect/vitest`. Name files for their subject, such as `pages.test.ts`.
