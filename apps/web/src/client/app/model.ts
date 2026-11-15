import { Schema } from "effect";
import { defineTaggedUnion } from "foldkit/schema";

import { Entry } from "../../content/entry.js";
import type { Entry as EntryValue } from "../../content/entry.js";
import { FactoryFeed, WindowKey } from "../../content/feed.js";
import type { FactoryFeed as FactoryFeedValue } from "../../content/feed.js";
import { SiteRoute } from "../../features/route.js";

export const CopyState = defineTaggedUnion({
  Copied: {},
  Failed: {},
  Idle: {},
});

export const Flags = Schema.Struct({ route: SiteRoute });

export type PageFlags = typeof Flags.Type;

export const Model = Schema.Struct({
  copyState: CopyState,
  entries: Schema.Array(Entry),
  feed: Schema.NullOr(FactoryFeed),
  kpiWindow: WindowKey,
  route: SiteRoute,
});

export type AppModel = typeof Model.Type;

export const initialModel = (
  flags: PageFlags,
  entries: ReadonlyArray<EntryValue>,
  feed: FactoryFeedValue | null
): AppModel => ({
  copyState: CopyState.Idle(),
  entries: [...entries],
  feed,
  kpiWindow: "1h",
  route: flags.route,
});
