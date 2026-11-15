import { Effect } from "effect";
import {
  Rendered,
  Responded,
  renderToString,
} from "foldkit/experimental/server";

import { Flags, initialModel } from "./client/app/model.js";
import type { PageFlags } from "./client/app/model.js";
import { entries } from "./content/entries.js";
import { view } from "./features/page.js";
import {
  entryPath,
  listPath,
  normalizePath,
  parsePath,
  Route,
} from "./features/route.js";

export { renderDocument } from "foldkit/experimental/server";

export const prerenderPaths = [
  "/",
  listPath("exploration"),
  listPath("report"),
  ...entries.map((entry) => entryPath(entry.kind, entry.slug)),
];

const renderRoute = Effect.fn("site.renderRoute")(function* renderRoute(
  request: Request
) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return Responded(
      new Response("This site accepts GET or HEAD", {
        headers: { Allow: "GET, HEAD" },
        status: 405,
      })
    );
  }

  const path = normalizePath(new URL(request.url).pathname);

  const application = yield* renderToString(
    {
      Flags,
      init: (flags: PageFlags) => ({ model: initialModel(flags, entries) }),
      view,
    },
    { flags: { path } }
  );

  return Route.guards.Missing(parsePath(path))
    ? Rendered(application, { status: 404 })
    : Rendered(application);
});

export const renderPage = (request: Request) =>
  Effect.runPromise(
    renderRoute(request).pipe(
      Effect.catchCause((cause) =>
        Effect.succeed(
          Responded(
            new Response("The page could not be rendered", {
              status: 500,
              statusText: cause.toString(),
            })
          )
        )
      )
    )
  );
