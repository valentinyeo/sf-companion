import { Effect } from "effect";

import { decodeFeed } from "./feed.js";
import type { FactoryFeedValue } from "./feed.js";

const feedFiles = import.meta.glob("../../content/feed/factory.json", {
  eager: true,
  import: "default",
  query: "?raw",
});

const feedEntry = Object.entries(feedFiles).at(0);

export const factoryFeed: FactoryFeedValue | null =
  feedEntry === undefined
    ? null
    : Effect.runSync(decodeFeed(feedEntry[0], feedEntry[1]));
