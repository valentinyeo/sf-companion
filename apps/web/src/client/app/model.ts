import { Schema } from "effect";
import type { Option } from "effect";
import { defineTaggedUnion } from "foldkit/schema";

import { Entry } from "../../content/entry.js";
import type { EntryValue } from "../../content/entry.js";
import { FactoryFeed, WindowKey } from "../../content/feed.js";
import type { FactoryFeedValue } from "../../content/feed.js";
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
  feed: Schema.Option(FactoryFeed),
  kpiWindow: WindowKey,
  route: SiteRoute,
});

export type AppModel = typeof Model.Type;

export const initialModel = (
  flags: PageFlags,
  entries: readonly EntryValue[],
  feed: Option.Option<FactoryFeedValue>
): AppModel => ({
  copyState: CopyState.Idle(),
  entries: [...entries],
  feed,
  kpiWindow: "1h",
  route: flags.route,
});
