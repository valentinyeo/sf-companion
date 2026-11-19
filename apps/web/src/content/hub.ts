import { DateTime, Effect, Option, Schema } from "effect";

import type { BucketEntry, BucketListing, ContentBucket } from "./bucket.js";
import { SECTION_PREFIX, itemOf, sortListed } from "./item.js";
import type { ItemValue, SectionValue } from "./item.js";

const CONTENT_TYPES = new Map<string, string>([
  ["gif", "image/gif"],
  ["htm", "text/html; charset=utf-8"],
  ["html", "text/html; charset=utf-8"],
  ["jpeg", "image/jpeg"],
  ["jpg", "image/jpeg"],
  ["json", "application/json"],
  ["md", "text/markdown; charset=utf-8"],
  ["mp4", "video/mp4"],
  ["pdf", "application/pdf"],
  ["png", "image/png"],
  ["svg", "image/svg+xml"],
  ["txt", "text/plain; charset=utf-8"],
  ["webp", "image/webp"],
]);

const SLUG_PATTERN = /^[A-Za-z0-9._-]{1,120}$/u;

const SECTIONS = ["explorations", "reports"] as const;

const LOCAL_HUB = new URL("../../content/hub/", import.meta.url);

export class HubFailure extends Schema.TaggedError<
  HubFailure,
  { readonly brand: unique symbol }
>()("HubFailure", {
  cause: Schema.Unknown,
  operation: Schema.String,
}) {}

export interface StoredItem {
  readonly bytes: ArrayBuffer;
  readonly contentType: string | undefined;
}

export interface HubStore {
  readonly get: (
    section: SectionValue,
    slug: string
  ) => Effect.Effect<Option.Option<StoredItem>, HubFailure>;
  readonly list: Effect.Effect<readonly ItemValue[], HubFailure>;
  readonly put: (
    section: SectionValue,
    slug: string,
    bytes: ArrayBuffer,
    metadata: Readonly<Record<string, string>>
  ) => Effect.Effect<void, HubFailure>;
  readonly remove: (
    section: SectionValue,
    slug: string
  ) => Effect.Effect<boolean, HubFailure>;
}

interface ListedEntry {
  readonly customMetadata: Readonly<Record<string, string>> | undefined;
  readonly key: string;
  readonly uploaded: string;
}

export const contentTypeOf = (slug: string): string | undefined =>
  CONTENT_TYPES.get(slug.toLowerCase().split(".").pop() ?? "");

export const isValidSlug = (slug: string): boolean => SLUG_PATTERN.test(slug);

const attempt = <A>(
  operation: string,
  run: () => Promise<A>
): Effect.Effect<A, HubFailure> =>
  Effect.tryPromise({
    catch: (cause) => new HubFailure({ cause, operation }),
    try: run,
  });

const keyOf = (section: SectionValue, slug: string): string =>
  `${SECTION_PREFIX[section]}${slug}`;

const listed = (
  section: SectionValue,
  entries: readonly ListedEntry[]
): readonly { readonly item: ItemValue; readonly uploaded: string }[] =>
  entries.map((entry) => ({
    item: itemOf(
      section,
      entry.key.slice(SECTION_PREFIX[section].length),
      entry.customMetadata ?? {},
      entry.uploaded
    ),
    uploaded: entry.uploaded,
  }));

const toListed = (entries: readonly BucketEntry[]): readonly ListedEntry[] =>
  entries.map((entry) => ({
    customMetadata: entry.customMetadata,
    key: entry.key,
    uploaded: entry.uploaded.toISOString(),
  }));

const listPage = (
  bucket: ContentBucket,
  prefix: string,
  cursor: string | undefined
): Effect.Effect<BucketListing, HubFailure> =>
  attempt("list", () =>
    bucket.list(
      cursor === undefined
        ? { include: ["customMetadata"], prefix }
        : { cursor, include: ["customMetadata"], prefix }
    )
  );

const bucketEntries = (
  bucket: ContentBucket,
  prefix: string,
  cursor?: string
): Effect.Effect<readonly BucketEntry[], HubFailure> =>
  Effect.gen(function* listEveryPage() {
    const page = yield* listPage(bucket, prefix, cursor);

    const rest = page.truncated
      ? yield* bucketEntries(bucket, prefix, page.cursor)
      : [];

    return [...page.objects, ...rest];
  });

const bucketStore = (bucket: ContentBucket): HubStore => ({
  get: (section, slug) =>
    Effect.gen(function* readObject() {
      const object = yield* attempt("get", () =>
        bucket.get(keyOf(section, slug))
      );

      if (object === null) {
        return Option.none<StoredItem>();
      }

      const bytes = yield* attempt("body", () => object.arrayBuffer());

      return Option.some({
        bytes,
        contentType: contentTypeOf(slug) ?? object.httpMetadata?.contentType,
      });
    }),
  list: Effect.gen(function* listItems() {
    const groups = yield* Effect.all(
      SECTIONS.map((section) =>
        bucketEntries(bucket, SECTION_PREFIX[section]).pipe(
          Effect.map((entries) => listed(section, toListed(entries)))
        )
      )
    );

    return sortListed(groups.flat());
  }),
  put: (section, slug, bytes, metadata) =>
    attempt("put", () =>
      bucket.put(keyOf(section, slug), bytes, {
        customMetadata: metadata,
        httpMetadata: {
          contentType: contentTypeOf(slug) ?? "application/octet-stream",
        },
      })
    ).pipe(Effect.asVoid),
  remove: (section, slug) =>
    Effect.gen(function* deleteObject() {
      const existing = yield* attempt("head", () =>
        bucket.head(keyOf(section, slug))
      );

      if (existing === null) {
        return false;
      }

      yield* attempt("delete", () => bucket.delete(keyOf(section, slug)));

      return true;
    }),
});

const LocalEntry = Schema.Struct({
  date: Schema.String,
  key: Schema.String,
  project: Schema.String,
  title: Schema.String,
  uploaded: Schema.String,
});

const LocalIndex = Schema.Array(LocalEntry);

const loadNodeFs = () => import("node:fs/promises");

const nodeFs: Effect.Effect<
  Awaited<ReturnType<typeof loadNodeFs>>,
  HubFailure
> = Effect.tryPromise({
  catch: (cause) => new HubFailure({ cause, operation: "node" }),
  try: loadNodeFs,
});

const readIndex = (fs: Awaited<ReturnType<typeof loadNodeFs>>) =>
  Effect.gen(function* readListing() {
    const text = yield* attempt("read-index", () =>
      fs.readFile(new URL("index.json", LOCAL_HUB), "utf-8")
    ).pipe(Effect.orElseSucceed(() => "[]"));

    return yield* Schema.decodeEffect(Schema.fromJsonString(LocalIndex))(
      text
    ).pipe(
      Effect.mapError((cause) => new HubFailure({ cause, operation: "index" }))
    );
  });

const writeIndex = (
  fs: Awaited<ReturnType<typeof loadNodeFs>>,
  entries: readonly { readonly key: string }[]
) =>
  attempt("write-index", () =>
    fs.writeFile(
      new URL("index.json", LOCAL_HUB),
      `${JSON.stringify(entries, undefined, 2)}\n`
    )
  );

const localStore: HubStore = {
  get: (section, slug) =>
    Effect.gen(function* readFixture() {
      const fs = yield* nodeFs;
      const file = new URL(keyOf(section, slug), LOCAL_HUB);

      const exists = yield* attempt("stat", () => fs.access(file)).pipe(
        Effect.map(() => true),
        Effect.orElseSucceed(() => false)
      );

      if (!exists) {
        return Option.none<StoredItem>();
      }

      const bytes = yield* attempt("read", () => fs.readFile(file)).pipe(
        Effect.map((data) => {
          const copy = new ArrayBuffer(data.byteLength);

          new Uint8Array(copy).set(data);

          return copy;
        })
      );

      return Option.some({
        bytes,
        contentType: contentTypeOf(slug) ?? "application/octet-stream",
      });
    }),
  list: Effect.gen(function* listFixtures() {
    const fs = yield* nodeFs;
    const entries = yield* readIndex(fs);

    return sortListed(
      entries.flatMap((entry) => {
        const section = SECTIONS.find((candidate) =>
          entry.key.startsWith(SECTION_PREFIX[candidate])
        );

        return section === undefined
          ? []
          : listed(section, [
              {
                customMetadata: {
                  date: entry.date,
                  project: entry.project,
                  title: entry.title,
                },
                key: entry.key,
                uploaded: entry.uploaded,
              },
            ]);
      })
    );
  }),
  put: (section, slug, bytes, metadata) =>
    Effect.gen(function* writeFixture() {
      const fs = yield* nodeFs;
      const key = keyOf(section, slug);
      const entries = yield* readIndex(fs);
      const uploaded = DateTime.formatIso(yield* DateTime.now);

      yield* attempt("mkdir", () =>
        fs.mkdir(new URL(".", new URL(key, LOCAL_HUB)), { recursive: true })
      );
      yield* attempt("write", () =>
        fs.writeFile(new URL(key, LOCAL_HUB), new Uint8Array(bytes))
      );
      yield* writeIndex(fs, [
        ...entries.filter((entry) => entry.key !== key),
        {
          date: metadata.date ?? "",
          key,
          project: metadata.project ?? "",
          title: metadata.title ?? slug,
          uploaded,
        },
      ]);
    }),
  remove: (section, slug) =>
    Effect.gen(function* removeFixture() {
      const fs = yield* nodeFs;
      const key = keyOf(section, slug);
      const file = new URL(key, LOCAL_HUB);

      const exists = yield* attempt("stat", () => fs.access(file)).pipe(
        Effect.map(() => true),
        Effect.orElseSucceed(() => false)
      );

      if (!exists) {
        return false;
      }

      const entries = yield* readIndex(fs);

      yield* attempt("delete", () => fs.rm(file));
      yield* writeIndex(
        fs,
        entries.filter((entry) => entry.key !== key)
      );

      return true;
    }),
};

const loadPlatform = () => import("cloudflare:workers");

const platform: Effect.Effect<
  Awaited<ReturnType<typeof loadPlatform>>,
  HubFailure
> = Effect.tryPromise({
  catch: () => new HubFailure({ cause: "no platform", operation: "platform" }),
  try: loadPlatform,
});

const platformBucket: Effect.Effect<Option.Option<ContentBucket>> =
  platform.pipe(
    Effect.map((loaded) => Option.fromNullishOr(loaded.env.CONTENT)),
    Effect.orElseSucceed(() => Option.none<ContentBucket>())
  );

export const envShareToken: Effect.Effect<string | undefined> = platform.pipe(
  Effect.map((loaded) => loaded.env.SHARE_TOKEN),
  Effect.orElseSucceed(() => process.env.SF_SHARE_TOKEN)
);

export const hubStore: Effect.Effect<HubStore> = platformBucket.pipe(
  Effect.map((bucket) =>
    Option.match(bucket, { onNone: () => localStore, onSome: bucketStore })
  )
);
