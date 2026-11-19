import { DateTime, Effect, Option } from "effect";

import type { HubFailure, HubStore } from "./hub.js";
import type { SectionValue } from "./item.js";

const DAY = /^\d{4}-\d{2}-\d{2}$/u;

const PROJECT = /^[a-z0-9-]{1,40}$/u;

export const invalidSlug = (): Response =>
  Response.json({ error: "Invalid slug" }, { status: 400 });

export const methodNotAllowed = (): Response =>
  new Response("Method not allowed", {
    headers: { Allow: "GET, PUT, DELETE" },
    status: 405,
  });

const urlOf = (section: SectionValue, slug: string): string =>
  `https://yeoux.net/${section}/${slug}`;

const authorized = (
  headers: Headers,
  shareToken: string | undefined
): boolean =>
  shareToken !== undefined &&
  shareToken !== "" &&
  headers.get("authorization") === `Bearer ${shareToken}`;

const read = (headers: Headers, name: string): string =>
  (headers.get(name) ?? "").trim().slice(0, 200);

const metadataFor = (headers: Headers, today: string) => {
  const date = read(headers, "x-date");
  const project = read(headers, "x-project").toLowerCase();
  const title = read(headers, "x-title");
  const legacy = read(headers, "x-legacy-key");
  const dated = { date: date === "" ? today : date };
  const titled = title === "" ? dated : { ...dated, title };
  const projected = project === "" ? titled : { ...titled, project };

  return legacy === "" ? projected : { ...projected, legacy };
};

export const serveItem = (
  store: HubStore,
  section: SectionValue,
  slug: string,
  head: boolean
): Effect.Effect<Response> =>
  store.get(section, slug).pipe(
    Effect.map((stored) =>
      Option.match(stored, {
        onNone: () => new Response("Not found", { status: 404 }),
        onSome: (item) => {
          const headers = new Headers({
            "cache-control": "private, no-store",
            "content-length": String(item.bytes.byteLength),
            "content-type": item.contentType ?? "application/octet-stream",
          });

          return new Response(head ? null : item.bytes, {
            headers,
            status: 200,
          });
        },
      })
    ),
    Effect.orElseSucceed(() => new Response("Not found", { status: 404 }))
  );

export const uploadItem = (
  store: HubStore,
  request: Request,
  section: SectionValue,
  slug: string,
  shareToken: string | undefined
): Effect.Effect<Response, HubFailure> => {
  if (!authorized(request.headers, shareToken)) {
    return Effect.succeed(
      Response.json({ error: "Unauthorized" }, { status: 401 })
    );
  }

  if (request.body === null || request.headers.get("content-length") === "0") {
    return store
      .remove(section, slug)
      .pipe(
        Effect.map(() =>
          Response.json({ deleted: true, url: urlOf(section, slug) })
        )
      );
  }

  return Effect.gen(function* storeUpload() {
    const date = read(request.headers, "x-date");
    const project = read(request.headers, "x-project").toLowerCase();

    if (date !== "" && !DAY.test(date)) {
      return Response.json(
        { error: "X-Date must look like 2026-10-17" },
        { status: 400 }
      );
    }

    if (project !== "" && !PROJECT.test(project)) {
      return Response.json(
        { error: "X-Project must be lowercase letters, digits and dashes" },
        { status: 400 }
      );
    }

    const today = DateTime.formatIsoDateUtc(yield* DateTime.now);
    const bytes = yield* Effect.promise(() => request.arrayBuffer());

    yield* store.put(section, slug, bytes, metadataFor(request.headers, today));

    return Response.json({ url: urlOf(section, slug) });
  });
};

export const deleteItem = (
  store: HubStore,
  section: SectionValue,
  slug: string,
  request: Request,
  shareToken: string | undefined
): Effect.Effect<Response, HubFailure> => {
  if (!authorized(request.headers, shareToken)) {
    return Effect.succeed(
      Response.json({ error: "Unauthorized" }, { status: 401 })
    );
  }

  return store
    .remove(section, slug)
    .pipe(
      Effect.map((removed) =>
        removed
          ? Response.json({ deleted: true, url: urlOf(section, slug) })
          : Response.json({ error: "Not found" }, { status: 404 })
      )
    );
};
