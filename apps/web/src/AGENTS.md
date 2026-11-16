# Foldkit site

Rules for browser code under `apps/web/src/client/` and `apps/web/src/features/`. Server and build modules follow the root `AGENTS.md`.

## Keep one direction of data flow

- Define the Model with Effect Schema. The Model owns browser state; the server owns durable facts.
- Define Messages with `defineMessageUnion` and match every variant.
- Name Messages after facts: `ClickedCopyEntryLink`, `CompletedCopyEntryLink`.
- Keep `init`, `update`, and `view` pure. `update` returns the next Model and optional Commands.
- Put I/O in named `Command.define` definitions. A Command returns a result Message, including a typed failure Message.
- Pass the typed HTML builder as the last view argument.

## Folders

| Home | Responsibility |
| --- | --- |
| `src/content/entry.ts` | The `Entry` Schema, the `ContentError` failure, decoding, list and lookup helpers |
| `src/content/entries.ts` | Reads every entry file once and decodes it at load |
| `src/content/feed.ts` | The `FactoryFeed` Schema, the `FeedError` failure, and decoding |
| `src/content/factory.ts` | Reads the one exported feed file and decodes it at load, or yields null |
| `src/features/route.ts` | The page route union and its Routers; URLs come from calling a Router as a printer |
| `src/features/page.ts` | The page view; it composes the template's `reader.stylex.ts` and base sheet |
| `src/features/factory.ts` | The `/factory` view: Usage cards, KPI tiles, the window picker, and the violations chart |
| `src/features/factory.stylex.ts` | StyleX styles for the factory view only |
| `src/client/rat.css` | The template's base sheet: monospace type, 80ch measure, grid, focus ring |
| `src/client/app/` | Model, Messages, named Commands, and `update` |
| `src/client/entry.ts` | Browser runtime boot and hydration |
| `src/entry.server.ts` | Server rendering, `prerenderPaths`, and 404 handling |
| `src/website.ts` | The Cloudflare `Website` resource; never import it into browser code |

The route travels from `entry.server.ts` to the browser as Foldkit Flags, so the hydrating client boots from the same Model.

## Content

One JSON file per entry lives in `apps/web/content/explorations/` or `apps/web/content/reports/`. Each file declares `kind`, `title`, `summary`, `date`, and `body`; the slug is the file name. `kind` must match its folder. A file that fails the Schema fails the build.

The factory numbers are one exported file, `apps/web/content/feed/factory.json`, decoded at load by `content/feed.ts`. It is not committed: when it is missing the site still builds and `/factory` shows the line `No factory numbers yet.` The exporter owns every state and every pre-formatted display string; the view writes numbers as text, dates, and bar heights, and decides nothing.

## Visual rules

StyleX for authored styles, over the template's untouched base sheet in `src/client/rat.css`. The base sheet and `tokens.stylex.ts` own every colour, font, size, spacing, and radius. Hot pink marks the focus ring and nothing else. No Tailwind, UI kits, or chart libraries. The factory chart is plain elements in the view.

A state (`ok`, `bad`, `warm`, `hot`) always carries a word or a count next to its colour, so it reads without colour.

## Tests

`apps/web/test/` holds behaviour tests through Foldkit Scene and `@effect/vitest`. Name files for their subject, such as `pages.test.ts`.
