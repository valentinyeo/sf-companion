import { defineMessageUnion } from "foldkit/message";

import { WindowKey } from "../../content/feed.js";

export const Message = defineMessageUnion({
  SelectedKpiWindow: { window: WindowKey },
});

export type AppMessage = typeof Message.Type;
