import { pipe, Schema } from "effect";
import { Route } from "foldkit";

import type { EntryKind } from "../content/entry.js";

const Section = Schema.Literals(["explorations", "reports"]);

export type SectionValue = typeof Section.Type;

export const SiteRoute = Route.defineRouteUnion({
  Entry: { section: Section, slug: Schema.String },
  Home: {},
  List: { section: Section },
  NotFound: { path: Schema.String },
});

export type SiteRoute = typeof SiteRoute.Type;

const sectionSegment = Route.schemaSegment("section", Section);

export const homeRouter = pipe(Route.root, Route.mapTo(SiteRoute.Home));

export const listRouter = pipe(sectionSegment, Route.mapTo(SiteRoute.List));

export const entryRouter = pipe(
  sectionSegment,
  Route.slash(Route.string("slug")),
  Route.mapTo(SiteRoute.Entry)
);

export const parseRoute = Route.parseUrlWithFallback(
  Route.oneOf(homeRouter, listRouter, entryRouter),
  SiteRoute.NotFound
);

export const sectionFor = (kind: EntryKind): SectionValue =>
  kind === "exploration" ? "explorations" : "reports";

export const kindOf = (section: SectionValue): EntryKind =>
  section === "explorations" ? "exploration" : "report";

export const listPath = (kind: EntryKind): string =>
  listRouter({ section: sectionFor(kind) });

export const entryPath = (kind: EntryKind, slug: string): string =>
  entryRouter({ section: sectionFor(kind), slug });
