import { Schema } from "effect";
import { defineMessageUnion } from "foldkit/message";

export const Message = defineMessageUnion({
  ClickedCopyEntryLink: { path: Schema.String },
  CompletedCopyEntryLink: { copied: Schema.Boolean },
});

export type AppMessage = typeof Message.Type;
