import { pipe, Schema } from "effect";
import { Route } from "foldkit";

import { Section } from "../content/item.js";
import type { SectionValue } from "../content/item.js";

export const SiteRoute = Route.defineRouteUnion({
  Entry: { section: Section, slug: Schema.String },
  Factory: {},
  Home: {},
  List: { section: Section },
  NotFound: { path: Schema.String },
});

export type SiteRouteValue = typeof SiteRoute.Type;

const sectionSegment = Route.schemaSegment("section", Section);

export const homeRouter = pipe(Route.root, Route.mapTo(SiteRoute.Home));

export const listRouter = pipe(sectionSegment, Route.mapTo(SiteRoute.List));

export const factoryRouter = pipe(
  Route.literal("factory"),
  Route.mapTo(SiteRoute.Factory)
);

export const entryRouter = pipe(
  sectionSegment,
  Route.slash(Route.string("slug")),
  Route.mapTo(SiteRoute.Entry)
);

export const parseRoute = Route.parseUrlWithFallback(
  Route.oneOf(homeRouter, factoryRouter, listRouter, entryRouter),
  SiteRoute.NotFound
);

export const listPath = (section: SectionValue): string =>
  listRouter({ section });

export const entryPath = (section: SectionValue, slug: string): string =>
  entryRouter({ section, slug });
