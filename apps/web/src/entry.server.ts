import { Clock, Effect, Option } from "effect";
import {
  Rendered,
  Responded,
  renderToString,
} from "foldkit/experimental/server";
import { fromString } from "foldkit/url";

import { Flags, initialModel } from "./client/app/model.js";
import type { PageFlags } from "./client/app/model.js";
import { chatsSnapshot } from "./content/chats-source.js";
import type { ChatsSnapshotValue } from "./content/chats.js";
import { factoryFeed } from "./content/factory.js";
import { envShareToken, hubStore, isValidSlug } from "./content/hub.js";
import type { HubFailure } from "./content/hub.js";
import type { SectionValue, ItemValue } from "./content/item.js";
import {
  deleteItem,
  invalidSlug,
  methodNotAllowed,
  serveItem,
  uploadItem,
} from "./content/share.js";
import { view } from "./features/page.js";
import {
  factoryRouter,
  parseRoute,
  SiteRoute,
  usageRouter,
} from "./features/route.js";
import type { SiteRouteValue } from "./features/route.js";

export { renderDocument } from "foldkit/experimental/server";

export const prerenderPaths = [factoryRouter(), usageRouter()];

const SECTIONS: readonly SectionValue[] = ["explorations", "reports"];

interface ItemTarget {
  readonly section: SectionValue;
  readonly slug: string;
}

const decodeSlug = (raw: string): string => {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
};

const itemTarget = (url: URL): Option.Option<ItemTarget> => {
  const parts = url.pathname.split("/");
  const section = SECTIONS.find((candidate) => candidate === parts[1]);
  const rest = parts.slice(2).join("/");

  return section === undefined || rest === ""
    ? Option.none()
    : Option.some({ section, slug: decodeSlug(rest) });
};

const answerItem = (
  request: Request,
  target: ItemTarget
): Effect.Effect<Response, HubFailure> => {
  if (!isValidSlug(target.slug)) {
    return Effect.succeed(invalidSlug());
  }

  const method = request.method.toUpperCase();

  return Effect.gen(function* answerStoredItem() {
    const store = yield* hubStore;

    if (method === "GET" || method === "HEAD") {
      return yield* serveItem(
        store,
        target.section,
        target.slug,
        method === "HEAD"
      );
    }

    if (method !== "PUT" && method !== "DELETE") {
      return methodNotAllowed();
    }

    const shareToken = yield* envShareToken;

    return method === "PUT"
      ? yield* uploadItem(
          store,
          request,
          target.section,
          target.slug,
          shareToken
        )
      : yield* deleteItem(
          store,
          target.section,
          target.slug,
          request,
          shareToken
        );
  });
};

const itemsFor = (
  route: SiteRouteValue
): Effect.Effect<readonly ItemValue[], HubFailure> =>
  SiteRoute.match(route, {
    Chats: () => Effect.succeed([]),
    Entry: () => Effect.succeed([]),
    Factory: () => Effect.succeed([]),
    Home: () => hubStore.pipe(Effect.flatMap((store) => store.list)),
    List: ({ section }) =>
      hubStore.pipe(
        Effect.flatMap((store) => store.list),
        Effect.map((listed) =>
          listed.filter((item) => item.section === section)
        )
      ),
    NotFound: () => Effect.succeed([]),
    Usage: () => Effect.succeed([]),
  });

const renderRoute = Effect.fn("site.renderRoute")(function* renderRoute(
  request: Request
) {
  const method = request.method.toUpperCase();
  const target = itemTarget(new URL(request.url));

  if (Option.isSome(target)) {
    return Responded(yield* answerItem(request, target.value));
  }

  if (method !== "GET" && method !== "HEAD") {
    return Responded(
      new Response("This site accepts GET or HEAD", {
        headers: { Allow: "GET, HEAD" },
        status: 405,
      })
    );
  }

  const route = parseRoute(Option.getOrThrow(fromString(request.url)));
  const items = yield* itemsFor(route);

  const chats: ChatsSnapshotValue | null = SiteRoute.guards.Chats(route)
    ? Option.getOrNull(yield* chatsSnapshot)
    : null;

  const fetchedAt = yield* Clock.currentTimeMillis;

  const application = yield* renderToString(
    {
      Flags,
      init: (flags: PageFlags) => ({
        model: initialModel(flags, Option.fromNullOr(factoryFeed)),
      }),
      view,
    },
    { flags: { chats, items, nowMs: fetchedAt, route } }
  );

  return SiteRoute.guards.NotFound(route)
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
