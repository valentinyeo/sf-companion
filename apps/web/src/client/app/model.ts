import { Option, Schema } from "effect";

import { FactoryFeed, WindowKey } from "../../content/feed.js";
import type { FactoryFeedValue } from "../../content/feed.js";
import { Item } from "../../content/item.js";
import { SiteRoute } from "../../features/route.js";

export const Flags = Schema.Struct({
  items: Schema.Array(Item),
  route: SiteRoute,
});

export type PageFlags = typeof Flags.Type;

export const Model = Schema.Struct({
  feed: Schema.Option(FactoryFeed),
  items: Schema.Array(Item),
  kpiWindow: WindowKey,
  nowMs: Schema.Option(Schema.Number),
  route: SiteRoute,
});

export type AppModel = typeof Model.Type;

export const initialModel = (
  flags: PageFlags,
  feed: Option.Option<FactoryFeedValue>
): AppModel => ({
  feed,
  items: [...flags.items],
  kpiWindow: "1h",
  nowMs: Option.none(),
  route: flags.route,
});
