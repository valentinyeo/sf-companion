import { Schema } from "effect";
import { defineMessageUnion } from "foldkit/message";

import { WindowKey } from "../../content/feed.js";

export const Message = defineMessageUnion({
  ClickedCopyEntryLink: { path: Schema.String },
  CompletedCopyEntryLink: { copied: Schema.Boolean },
  SelectedKpiWindow: { window: WindowKey },
});

export type AppMessage = typeof Message.Type;
