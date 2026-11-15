import { Schema } from "effect";
import { defineTaggedUnion } from "foldkit/schema";

import { Kind } from "../content/entry.js";
import type { EntryKind } from "../content/entry.js";

export const Route = defineTaggedUnion({
  Entry: { kind: Kind, slug: Schema.String },
  Home: {},
  List: { kind: Kind },
  Missing: {},
});

export type Route = typeof Route.Type;

const kindForSection = (section: string): EntryKind | undefined => {
  if (section === "explorations") {
    return "exploration";
  }

  if (section === "reports") {
    return "report";
  }

  return undefined;
};

export const listPath = (kind: EntryKind): string =>
  kind === "exploration" ? "/explorations" : "/reports";

export const entryPath = (kind: EntryKind, slug: string): string =>
  `${listPath(kind)}/${slug}`;

export const normalizePath = (path: string): string => {
  const trimmed = path.length > 1 ? path.replace(/\/+$/u, "") : path;

  return trimmed === "" ? "/" : trimmed;
};

export const parsePath = (path: string): Route => {
  const [section, slug, ...rest] = normalizePath(path)
    .split("/")
    .filter((segment) => segment !== "");

  if (section === undefined) {
    return Route.Home();
  }

  const kind = kindForSection(section);

  if (kind === undefined) {
    return Route.Missing();
  }

  if (slug === undefined) {
    return Route.List({ kind });
  }

  return rest.length > 0 ? Route.Missing() : Route.Entry({ kind, slug });
};
