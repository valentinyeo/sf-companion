import { Schema } from "effect";
import { defineMessageUnion } from "foldkit/message";

import { BurnRange } from "../../content/burn.js";
import { WindowKey } from "../../content/feed.js";

export const Message = defineMessageUnion({
  SelectedBurnRange: { range: BurnRange },
  SelectedBurnPlan: { plan: Schema.String },
  SelectedBurnChat: { chatId: Schema.String },
  ChangedBurnStart: { value: Schema.String },
  ChangedBurnEnd: { value: Schema.String },
  SelectedKpiWindow: { window: WindowKey },
  TickedClock: { nowMs: Schema.Number },
});

export type AppMessage = typeof Message.Type;
