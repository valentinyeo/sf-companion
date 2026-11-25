import { Effect, Schema } from "effect";

const REDACTED = "[redacted]";

const FIELD_LIMIT = 60;

const EMAIL = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/gu;

const IPV4 = /\b\d{1,3}(?:\.\d{1,3}){3}\b/gu;

const HOSTNAME =
  /\b[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}\b/gu;

const TOKEN = /[A-Za-z0-9_+/=-]{32,}/gu;

export const ChatsServer = Schema.Literals(["Contabo", "inne Hetzner"]);

export type ChatsServerValue = typeof ChatsServer.Type;

export const ChatHarness = Schema.Literals([
  "claude",
  "codex",
  "pi",
  "antigravity",
  "cursor",
  "unknown",
]);

export type ChatHarnessValue = typeof ChatHarness.Type;

export const ChatRow = Schema.Struct({
  effort: Schema.String,
  harness: ChatHarness,
  model: Schema.String,
  name: Schema.NonEmptyString,
  project: Schema.String,
  server: ChatsServer,
});

export type ChatRowValue = typeof ChatRow.Type;

export const ChatsServerLine = Schema.Struct({
  collectedAt: Schema.NullOr(Schema.String),
  server: ChatsServer,
  state: Schema.Literals(["live", "not-connected"]),
});

export type ChatsServerLineValue = typeof ChatsServerLine.Type;

export const ChatsSnapshot = Schema.Struct({
  chats: Schema.Array(ChatRow),
  generatedAt: Schema.String,
  servers: Schema.Array(ChatsServerLine),
});

export type ChatsSnapshotValue = typeof ChatsSnapshot.Type;

export class ChatsError extends Schema.TaggedError<
  ChatsError,
  { readonly brand: unique symbol }
>()("ChatsError", {
  cause: Schema.Unknown,
  path: Schema.String,
}) {}

const printable = (value: string): string => {
  const kept: string[] = [];

  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;

    kept.push(code < 32 || code === 127 ? " " : character);
  }

  return kept.join("");
};

const publishable = (value: string): string => {
  const text = printable(value)
    .replaceAll(EMAIL, REDACTED)
    .replaceAll(IPV4, REDACTED)
    .replaceAll(HOSTNAME, REDACTED)
    .replaceAll(TOKEN, REDACTED)
    .replaceAll(/\s+/gu, " ")
    .trim()
    .slice(0, FIELD_LIMIT);

  return text === "" ? "unknown" : text;
};

export const publishedRow = (row: ChatRowValue): ChatRowValue => ({
  effort: publishable(row.effort),
  harness: row.harness,
  model: publishable(row.model),
  name: publishable(row.name),
  project: publishable(row.project),
  server: row.server,
});

export const publishedSnapshot = (
  snapshot: ChatsSnapshotValue
): ChatsSnapshotValue => ({
  chats: snapshot.chats.map(publishedRow),
  generatedAt: snapshot.generatedAt,
  servers: snapshot.servers.map((line) => ({
    collectedAt: line.collectedAt,
    server: line.server,
    state: line.state,
  })),
});

export const decodeChats = Effect.fn("content.decodeChats")(
  function* decodeChats(path: string, raw: string) {
    const snapshot = yield* Schema.decodeEffect(
      Schema.fromJsonString(ChatsSnapshot)
    )(raw).pipe(Effect.mapError((cause) => new ChatsError({ cause, path })));

    return publishedSnapshot(snapshot);
  }
);
