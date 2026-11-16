import { Effect, Schema } from "effect";
import { Command } from "foldkit";

import { Message } from "./message.js";

class ClipboardFailure extends Schema.TaggedError<
  ClipboardFailure,
  { readonly brand: unique symbol }
>()("ClipboardFailure", { cause: Schema.Unknown }) {}

export const CopyEntryLink = Command.define("CopyEntryLink", {
  args: { path: Schema.String },
  execute: ({ path }) =>
    Effect.tryPromise({
      catch: (cause) => new ClipboardFailure({ cause }),
      try: () =>
        navigator.clipboard.writeText(new URL(path, location.href).href),
    }).pipe(
      Effect.match({
        onFailure: () => Message.CompletedCopyEntryLink({ copied: false }),
        onSuccess: () => Message.CompletedCopyEntryLink({ copied: true }),
      })
    ),
  messages: [Message.CompletedCopyEntryLink],
});
