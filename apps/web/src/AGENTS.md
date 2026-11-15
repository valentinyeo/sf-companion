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
| `src/features/route.ts` | The page route union and its Routers; URLs come from calling a Router as a printer |
| `src/features/page.ts` and `page.stylex.ts` | The page view and its StyleX styles |
| `src/client/app/` | Model, Messages, named Commands, and `update` |
| `src/client/entry.ts` | Browser runtime boot and hydration |
| `src/entry.server.ts` | Server rendering, `prerenderPaths`, and 404 handling |
| `src/website.ts` | The Cloudflare `Website` resource; never import it into browser code |

The route travels from `entry.server.ts` to the browser as Foldkit Flags, so the hydrating client boots from the same Model.

## Content

One JSON file per entry lives in `apps/web/content/explorations/` or `apps/web/content/reports/`. Each file declares `kind`, `title`, `summary`, `date`, and `body`; the slug is the file name. `kind` must match its folder. A file that fails the Schema fails the build.

## Visual rules

StyleX only. Corners are 2px or 4px. Hot pink marks the focus ring and nothing else. No Tailwind, UI kits, or chart libraries.

## Tests

`apps/web/test/` holds behaviour tests through Foldkit Scene and `@effect/vitest`. Name files for their subject, such as `pages.test.ts`.
