import { Schema } from "effect";
import { defineTaggedUnion } from "foldkit/schema";

import { Entry } from "../../content/entry.js";
import type { Entry as EntryValue } from "../../content/entry.js";

export const CopyState = defineTaggedUnion({
  Copied: {},
  Failed: {},
  Idle: {},
});

export const Flags = Schema.Struct({ path: Schema.String });

export type PageFlags = typeof Flags.Type;

export const Model = Schema.Struct({
  copyState: CopyState,
  entries: Schema.Array(Entry),
  path: Schema.String,
});

export type AppModel = typeof Model.Type;

export const initialModel = (
  flags: PageFlags,
  entries: ReadonlyArray<EntryValue>
): AppModel => ({
  copyState: CopyState.Idle(),
  entries: [...entries],
  path: flags.path,
});
