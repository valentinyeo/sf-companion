import { Button } from "@foldkit/ui";
import { Array, Option } from "effect";
import type { Document, Html, HtmlBuilder } from "foldkit/html";
import * as stylex from "@stylexjs/stylex";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import { CopyState } from "../client/app/model.js";
import type { AppModel } from "../client/app/model.js";
import { entriesOf, findEntry } from "../content/entry.js";
import type { Entry, EntryKind } from "../content/entry.js";
import { styles } from "./page.stylex.js";
import {
  entryPath,
  entryRouter,
  homeRouter,
  kindOf,
  listPath,
  SiteRoute,
} from "./route.js";
import type { SiteRoute as SiteRouteValue } from "./route.js";

const SITE_NAME = "Software Factory Companion";

const sectionName = (kind: EntryKind) =>
  kind === "exploration" ? "Explorations" : "Reports";

const emptyLine = (kind: EntryKind) =>
  kind === "exploration" ? "No explorations yet." : "No reports yet.";

const className = (style: stylex.StyleXStyles) =>
  stylex.props(style).className ?? "";

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

const siteHeader = (h: HtmlBuilder<AppMessage>): Html =>
  h.header(
    [h.Class(className(styles.header))],
    [
      h.a([h.Href(homeRouter()), h.Class(className(styles.wordmark))], [
        SITE_NAME,
      ]),
      h.nav(
        [h.AriaLabel("Sections")],
        [
          h.ul(
            [h.Class(className(styles.navList))],
            [
              h.li(
                [],
                [h.a([h.Href(listPath("exploration"))], ["Explorations"])]
              ),
              h.li([], [h.a([h.Href(listPath("report"))], ["Reports"])]),
            ]
          ),
        ]
      ),
    ]
  );

const siteFooter = (h: HtmlBuilder<AppMessage>): Html =>
  h.footer(
    [h.Class(className(styles.footer))],
    [h.p([], ["Built with Foldkit, Effect, Alchemy, and StyleX."])]
  );

const homeView = (h: HtmlBuilder<AppMessage>): Html =>
  h.section(
    [],
    [
      h.h1([], [SITE_NAME]),
      h.p(
        [h.Class(className(styles.lede))],
        ["Working notes and finished reports from the Software Factory."]
      ),
      h.ul(
        [h.Class(className(styles.branchList))],
        [
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
        ]
      ),
    ]
  );

const entryRow = (entry: Entry, h: HtmlBuilder<AppMessage>): Html =>
  h.li(
    [h.Key(entry.slug), h.Class(className(styles.row))],
    [
      h.a(
        [
          h.Href(entryPath(entry.kind, entry.slug)),
          h.Class(className(styles.rowTitle)),
        ],
        [entry.title]
      ),
      h.p([h.Class(className(styles.summary))], [entry.summary]),
      h.time(
        [h.Datetime(entry.date), h.Class(className(styles.meta))],
        [entry.date]
      ),
    ]
  );

const listView = (
  kind: EntryKind,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html => {
  const present = entriesOf(model.entries, kind);

  return h.section(
    [],
    [
      h.h1([], [sectionName(kind)]),
      Array.match(present, {
        onEmpty: () =>
          h.p([h.Class(className(styles.empty))], [emptyLine(kind)]),
        onNonEmpty: (listed) =>
          h.ul(
            [h.Class(className(styles.entryList))],
            listed.map((entry) => entryRow(entry, h))
          ),
      }),
    ]
  );
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
        h.button([...button, h.Class(className(styles.button))], [
          copyLabel(model.copyState),
        ]),
      type: "button",
    },
    h
  );

const entryView = (
  route: Extract<SiteRouteValue, { readonly _tag: "Entry" }>,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html => {
  const kind = kindOf(route.section);

  return Option.match(findEntry(model.entries, kind, route.slug), {
    onNone: () => missingView(h),
    onSome: (entry) =>
      h.article(
        [h.Class(className(styles.article))],
        [
          h.h1([], [entry.title]),
          h.p([h.Class(className(styles.lede))], [entry.summary]),
          h.time(
            [h.Datetime(entry.date), h.Class(className(styles.meta))],
            [entry.date]
          ),
          h.div(
            [h.Class(className(styles.prose))],
            paragraphs(entry.body).map((paragraph) => h.p([], [paragraph]))
          ),
          copyLink(
            model,
            entryRouter({ section: route.section, slug: route.slug }),
            h
          ),
          h.p(
            [h.Class(className(styles.back))],
            [
              h.a(
                [h.Href(listPath(kind))],
                [`Back to ${sectionName(kind).toLowerCase()}`]
              ),
            ]
          ),
        ]
      ),
  });
};

const missingView = (h: HtmlBuilder<AppMessage>): Html =>
  h.section(
    [],
    [
      h.h1([], ["Page not found"]),
      h.p([], [h.a([h.Href(homeRouter())], ["Go to the home page."])]),
    ]
  );

const titleOf = (route: SiteRouteValue, model: AppModel) =>
  SiteRoute.match(route, {
    Entry: ({ section, slug }) =>
      Option.match(findEntry(model.entries, kindOf(section), slug), {
        onNone: () => "Page not found",
        onSome: (entry) => entry.title,
      }),
    Home: () => SITE_NAME,
    List: ({ section }) => sectionName(kindOf(section)),
    NotFound: () => "Page not found",
  });

const bodyOf = (
  route: SiteRouteValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html =>
  SiteRoute.match(route, {
    Entry: (entry) => entryView(entry, model, h),
    Home: () => homeView(h),
    List: ({ section }) => listView(kindOf(section), model, h),
    NotFound: () => missingView(h),
  });

export const view = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Document => ({
  body: h.div(
    [h.Class(className(styles.shell))],
    [siteHeader(h), h.main([], [bodyOf(model.route, model, h)]), siteFooter(h)]
  ),
  title: titleOf(model.route, model),
});
