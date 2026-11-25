import { Schema } from "effect";
import { defineMessageUnion } from "foldkit/message";

import { WindowKey } from "../../content/feed.js";

export const Message = defineMessageUnion({
  SelectedKpiWindow: { window: WindowKey },
  TickedClock: { nowMs: Schema.Number },
});

export type AppMessage = typeof Message.Type;
