import { Array, Effect, Option, Schema } from "effect";

export const Kind = Schema.Literals(["exploration", "report"]);

export type EntryKind = typeof Kind.Type;

const day = Schema.String.check(Schema.isPattern(/^\d{4}-\d{2}-\d{2}$/u));

export const Entry = Schema.Struct({
  body: Schema.NonEmptyString,
  date: day,
  kind: Kind,
  slug: Schema.NonEmptyString,
  summary: Schema.NonEmptyString,
  title: Schema.NonEmptyString,
});

export type Entry = typeof Entry.Type;

export class ContentError extends Schema.TaggedError<
  ContentError,
  { readonly brand: unique symbol }
>()("ContentError", {
  cause: Schema.Unknown,
  path: Schema.String,
}) {}

const EntryFile = Schema.Struct({
  body: Schema.NonEmptyString,
  date: day,
  kind: Kind,
  summary: Schema.NonEmptyString,
  title: Schema.NonEmptyString,
});

const slugFromPath = (path: string) =>
  path.slice(path.lastIndexOf("/") + 1).replace(/\.json$/u, "");

export const decodeEntry = Effect.fn("content.decodeEntry")(
  function* decodeEntry(kind: EntryKind, path: string, raw: string) {
    const file = yield* Schema.decodeEffect(
      Schema.fromJsonString(EntryFile)
    )(raw).pipe(Effect.mapError((cause) => new ContentError({ cause, path })));

    if (file.kind !== kind) {
      return yield* new ContentError({
        cause: `An entry in ${kind} declares kind ${file.kind}`,
        path,
      });
    }

    return { ...file, slug: slugFromPath(path) };
  }
);

export const entriesOf = (
  entries: ReadonlyArray<Entry>,
  kind: EntryKind
): ReadonlyArray<Entry> =>
  entries
    .filter((entry) => entry.kind === kind)
    .toSorted(
      (left, right) =>
        right.date.localeCompare(left.date) ||
        left.title.localeCompare(right.title)
    );

export const findEntry = (
  entries: ReadonlyArray<Entry>,
  kind: EntryKind,
  slug: string
): Option.Option<Entry> =>
  Array.findFirst(
    entries,
    (entry) => entry.kind === kind && entry.slug === slug
  );
