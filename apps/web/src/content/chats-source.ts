import { Effect, Option } from "effect";

import type { BucketObject, ContentBucket } from "./bucket.js";
import { ChatsError, decodeChats } from "./chats.js";
import type { ChatsSnapshotValue } from "./chats.js";

const CHATS_KEY = "chats/latest.json";

const bundled = import.meta.glob("../../content/feed/chats.json", {
  eager: true,
  import: "default",
  query: "?raw",
});

const bundledEntry = Object.entries(bundled).at(0);

export const bundledChats: Option.Option<ChatsSnapshotValue> =
  bundledEntry === undefined
    ? Option.none()
    : Option.some(
        Effect.runSync(decodeChats(bundledEntry[0], bundledEntry[1]))
      );

const loadPlatform = () => import("cloudflare:workers");

const failure = (cause: unknown) => new ChatsError({ cause, path: CHATS_KEY });

const platform: Effect.Effect<
  Awaited<ReturnType<typeof loadPlatform>>,
  ChatsError
> = Effect.tryPromise({ catch: failure, try: loadPlatform });

const platformBucket: Effect.Effect<Option.Option<ContentBucket>> =
  platform.pipe(
    Effect.map((loaded) => Option.fromNullishOr(loaded.env.CONTENT)),
    Effect.orElseSucceed(() => Option.none<ContentBucket>())
  );

const bucketChats: Effect.Effect<Option.Option<ChatsSnapshotValue>> =
  Effect.gen(function* readBucketSnapshot() {
    const bucket = Option.getOrNull(yield* platformBucket);

    if (bucket === null) {
      return Option.none<ChatsSnapshotValue>();
    }

    const object: BucketObject | null = yield* Effect.tryPromise({
      catch: failure,
      try: () => bucket.get(CHATS_KEY),
    });

    if (object === null) {
      return Option.none<ChatsSnapshotValue>();
    }

    const body: ArrayBuffer = yield* Effect.tryPromise({
      catch: failure,
      try: () => object.arrayBuffer(),
    });

    return Option.some(
      yield* decodeChats(CHATS_KEY, new TextDecoder().decode(body))
    );
  }).pipe(Effect.orElseSucceed(() => Option.none()));

export const chatsSnapshot = bucketChats.pipe(
  Effect.map((fromBucket) =>
    Option.match(fromBucket, {
      onNone: () => bundledChats,
      onSome: (snapshot) => Option.some(snapshot),
    })
  )
);
