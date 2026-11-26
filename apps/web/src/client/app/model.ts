import { Option, Schema } from "effect";

import { BurnSelection } from "../../content/burn.js";
import { ChatsSnapshot } from "../../content/chats.js";
import { FactoryFeed, WindowKey } from "../../content/feed.js";
import type { FactoryFeedValue } from "../../content/feed.js";
import { Item } from "../../content/item.js";
import { SiteRoute } from "../../features/route.js";

export const Flags = Schema.Struct({
  chats: Schema.optionalKey(Schema.NullOr(ChatsSnapshot)),
  items: Schema.Array(Item),
  nowMs: Schema.optionalKey(Schema.NullOr(Schema.Number)),
  route: SiteRoute,
});

export type PageFlags = typeof Flags.Type;

export const Model = Schema.Struct({
  burn: BurnSelection,
  chats: Schema.Option(ChatsSnapshot),
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
  burn: { chatId: "", end: "", plan: "", range: "7d", start: "" },
  chats: Option.fromNullishOr(flags.chats),
  feed,
  items: [...flags.items],
  kpiWindow: "1h",
  nowMs: Option.fromNullishOr(flags.nowMs),
  route: flags.route,
});
