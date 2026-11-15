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
import { entryPath, listPath, parsePath, Route } from "./route.js";
import type { Route as RouteValue } from "./route.js";

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
  body
    .split(/\n{2,}/u)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph !== "");

const siteHeader = (h: HtmlBuilder<AppMessage>): Html =>
  h.header(
    [h.Class(className(styles.header))],
    [
      h.a([h.Href("/"), h.Class(className(styles.wordmark))], [SITE_NAME]),
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

const copyLink = (model: AppModel, h: HtmlBuilder<AppMessage>): Html =>
  Button.view(
    {
      onClick: Message.ClickedCopyEntryLink({ path: model.path }),
      toView: ({ button }) =>
        h.button([...button, h.Class(className(styles.button))], [
          copyLabel(model.copyState),
        ]),
      type: "button",
    },
    h
  );

const entryView = (
  route: Extract<RouteValue, { readonly _tag: "Entry" }>,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html =>
  Option.match(findEntry(model.entries, route.kind, route.slug), {
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
          copyLink(model, h),
          h.p(
            [h.Class(className(styles.back))],
            [
              h.a(
                [h.Href(listPath(entry.kind))],
                [`Back to ${sectionName(entry.kind).toLowerCase()}`]
              ),
            ]
          ),
        ]
      ),
  });

const missingView = (h: HtmlBuilder<AppMessage>): Html =>
  h.section(
    [],
    [
      h.h1([], ["Page not found"]),
      h.p([], [h.a([h.Href("/")], ["Go to the home page."])]),
    ]
  );

const titleOf = (route: RouteValue, model: AppModel) =>
  Route.match(route, {
    Entry: ({ kind, slug }) =>
      Option.match(findEntry(model.entries, kind, slug), {
        onNone: () => "Page not found",
        onSome: (entry) => entry.title,
      }),
    Home: () => SITE_NAME,
    List: ({ kind }) => sectionName(kind),
    Missing: () => "Page not found",
  });

const bodyOf = (
  route: RouteValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html =>
  Route.match(route, {
    Entry: (entry) => entryView(entry, model, h),
    Home: () => homeView(h),
    List: ({ kind }) => listView(kind, model, h),
    Missing: () => missingView(h),
  });

export const view = (model: AppModel, h: HtmlBuilder<AppMessage>): Document => {
  const route = parsePath(model.path);

  return {
    body: h.div(
      [h.Class(className(styles.shell))],
      [siteHeader(h), h.main([], [bodyOf(route, model, h)]), siteFooter(h)]
    ),
    title: titleOf(route, model),
  };
};
