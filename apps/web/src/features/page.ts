import { Button } from "@foldkit/ui";
import * as stylex from "@stylexjs/stylex";
import { Array, Option } from "effect";
import type { Document, Html, HtmlBuilder } from "foldkit/html";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import { CopyState } from "../client/app/model.js";
import type { AppModel } from "../client/app/model.js";
import { entriesOf, findEntry } from "../content/entry.js";
import type { EntryValue, EntryKind } from "../content/entry.js";
import { factoryView } from "./factory.js";
import { readerStyles } from "./reader.stylex.js";
import {
  entryPath,
  entryRouter,
  factoryRouter,
  homeRouter,
  kindOf,
  listPath,
  SiteRoute,
} from "./route.js";
import type { SiteRouteValue } from "./route.js";

const SITE_NAME = "Software Factory Companion";

const sectionName = (kind: EntryKind) =>
  kind === "exploration" ? "Explorations" : "Reports";

const emptyLine = (kind: EntryKind) =>
  kind === "exploration" ? "No explorations yet." : "No reports yet.";

const backLabel = (kind: EntryKind) =>
  `Back to ${sectionName(kind).toLowerCase()}`;

const className = (...styles: readonly stylex.StyleXStyles[]) =>
  stylex.props(...styles).className ?? "";

const copyLabel = CopyState.match({
  Copied: () => "Link copied",
  Failed: () => "Copy failed. Copy the address bar instead.",
  Idle: () => "Copy link",
});

const paragraphs = (body: string) =>
  body.split(/\n{2,}/u).flatMap((paragraph) => {
    const trimmed = paragraph.trim();

    return trimmed === "" ? [] : [trimmed];
  });

const sectionLinks = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.li([], [h.a([h.Href(listPath("exploration"))], ["Explorations"])]),
  h.li([], [h.a([h.Href(listPath("report"))], ["Reports"])]),
  h.li([], [h.a([h.Href(factoryRouter())], ["Factory"])]),
];

const siteHeader = (h: HtmlBuilder<AppMessage>): Html =>
  h.header(
    [h.Class(className(readerStyles.bounded, readerStyles.header))],
    [
      h.nav(
        [h.AriaLabel("Primary navigation"), h.Class("site-nav")],
        [
          h.a(
            [h.Class("brand"), h.Href(homeRouter())],
            [h.strong([], [SITE_NAME])]
          ),
          h.div([h.Class("site-links")], [h.ul([], sectionLinks(h))]),
        ]
      ),
    ]
  );

const siteFooter = (h: HtmlBuilder<AppMessage>): Html =>
  h.footer(
    [h.Class(className(readerStyles.bounded))],
    [h.hr([]), h.p([], ["Built with Foldkit, Effect, Alchemy, and StyleX."])]
  );

const homeBranches = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.li(
    [],
    [
      h.a([h.Href(listPath("exploration"))], ["Explorations"]),
      h.p([], ["Open questions, experiments, and working notes."]),
    ]
  ),
  h.li(
    [],
    [
      h.a([h.Href(listPath("report"))], ["Reports"]),
      h.p([], ["Finished findings and write-ups."]),
    ]
  ),
  h.li(
    [],
    [
      h.a([h.Href(factoryRouter())], ["Factory"]),
      h.p([], ["Usage and KPIs from the factory's own numbers."]),
    ]
  ),
];

const homeView = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.h1([], [SITE_NAME]),
  h.p([], ["Working notes and finished reports from the Software Factory."]),
  h.ul([], homeBranches(h)),
];

const entryRow = (entry: EntryValue, h: HtmlBuilder<AppMessage>): Html =>
  h.li(
    [h.Key(entry.slug)],
    [
      h.a([h.Href(entryPath(entry.kind, entry.slug))], [entry.title]),
      h.p([], [entry.summary]),
      h.time([h.Datetime(entry.date)], [entry.date]),
    ]
  );

const listView = (
  kind: EntryKind,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => {
  const present = entriesOf(model.entries, kind);

  return [
    h.h1([], [sectionName(kind)]),
    Array.match(present, {
      onEmpty: () => h.p([], [emptyLine(kind)]),
      onNonEmpty: (listed) =>
        h.ul(
          [],
          listed.map((entry) => entryRow(entry, h))
        ),
    }),
  ];
};

const copyLink = (
  model: AppModel,
  path: string,
  h: HtmlBuilder<AppMessage>
): Html =>
  Button.view(
    {
      onClick: Message.ClickedCopyEntryLink({ path }),
      toView: ({ button }) =>
        h.button([...button], [copyLabel(model.copyState)]),
      type: "button",
    },
    h
  );

const entryView = (
  route: Extract<SiteRouteValue, { readonly _tag: "Entry" }>,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => {
  const kind = kindOf(route.section);

  return Option.match(findEntry(model.entries, kind, route.slug), {
    onNone: () => missingView(h),
    onSome: (entry) => [
      h.article(
        [],
        [
          h.h1([], [entry.title]),
          h.p([], [entry.summary]),
          h.time([h.Datetime(entry.date)], [entry.date]),
          ...paragraphs(entry.body).map((paragraph) => h.p([], [paragraph])),
          copyLink(
            model,
            entryRouter({ section: route.section, slug: route.slug }),
            h
          ),
          h.p([], [h.a([h.Href(listPath(kind))], [backLabel(kind)])]),
        ]
      ),
    ],
  });
};

const missingView = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.h1([], ["Page not found"]),
  h.p([], [h.a([h.Href(homeRouter())], ["Go to the home page."])]),
];

const titleOf = (route: SiteRouteValue, model: AppModel) =>
  SiteRoute.match(route, {
    Entry: ({ section, slug }) =>
      Option.match(findEntry(model.entries, kindOf(section), slug), {
        onNone: () => "Page not found",
        onSome: (entry) => entry.title,
      }),
    Factory: () => "Factory",
    Home: () => SITE_NAME,
    List: ({ section }) => sectionName(kindOf(section)),
    NotFound: () => "Page not found",
  });

const bodyOf = (
  route: SiteRouteValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  SiteRoute.match(route, {
    Entry: (entry) => entryView(entry, model, h),
    Factory: () => factoryView(model, h),
    Home: () => homeView(h),
    List: ({ section }) => listView(kindOf(section), model, h),
    NotFound: () => missingView(h),
  });

export const view = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Document => ({
  body: h.div(
    [h.Class(className(readerStyles.shell))],
    [siteHeader(h), h.main([], bodyOf(model.route, model, h)), siteFooter(h)]
  ),
  title: titleOf(model.route, model),
});
