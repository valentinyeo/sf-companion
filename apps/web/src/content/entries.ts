import { Effect } from "effect";

import { decodeEntry } from "./entry.js";
import type { EntryValue, EntryKind } from "./entry.js";

const explorationFiles = import.meta.glob("../../content/explorations/*.json", {
  eager: true,
  import: "default",
  query: "?raw",
});

const reportFiles = import.meta.glob("../../content/reports/*.json", {
  eager: true,
  import: "default",
  query: "?raw",
});

const loadFolder = (kind: EntryKind, files: Readonly<Record<string, string>>) =>
  Effect.runSync(
    Effect.forEach(Object.entries(files), ([path, raw]) =>
      decodeEntry(kind, path, raw)
    )
  );

export const entries: readonly EntryValue[] = [
  ...loadFolder("exploration", explorationFiles),
  ...loadFolder("report", reportFiles),
];
