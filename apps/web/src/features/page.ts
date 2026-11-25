import * as stylex from "@stylexjs/stylex";
import { Array } from "effect";
import type { Document, Html, HtmlBuilder } from "foldkit/html";

import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import { itemsIn, titleFromSlug } from "../content/item.js";
import type { ItemValue, SectionValue } from "../content/item.js";
import { chatsView } from "./chats.js";
import { factoryView } from "./factory.js";
import { hubStyles } from "./hub.stylex.js";
import { readerStyles } from "./reader.stylex.js";
import {
  chatsRouter,
  entryPath,
  factoryRouter,
  homeRouter,
  listPath,
  SiteRoute,
  usageRouter,
} from "./route.js";
import type { SiteRouteValue } from "./route.js";
import { usageView } from "./usage.js";

const SITE_NAME = "Software Factory Companion";

const HOME_LIMIT = 5;

const SECTION_TEXT: Readonly<
  Record<
    SectionValue,
    { readonly blurb: string; readonly empty: string; readonly name: string }
  >
> = {
  explorations: {
    blurb: "Research, plans and experiments, newest first.",
    empty: "No explorations yet.",
    name: "Explorations",
  },
  reports: {
    blurb: "Finished reports and status pages, newest first.",
    empty: "No reports yet.",
    name: "Reports",
  },
};

const className = (...styles: readonly stylex.StyleXStyles[]) =>
  stylex.props(...styles).className ?? "";

const sectionLinks = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.li([], [h.a([h.Href(listPath("explorations"))], ["Explorations"])]),
  h.li([], [h.a([h.Href(listPath("reports"))], ["Reports"])]),
  h.li([], [h.a([h.Href(factoryRouter())], ["Factory"])]),
  h.li([], [h.a([h.Href(usageRouter())], ["Usage"])]),
  h.li([], [h.a([h.Href(chatsRouter())], ["Chats"])]),
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

const itemRow = (item: ItemValue, h: HtmlBuilder<AppMessage>): Html =>
  h.li(
    [h.Key(`${item.section}/${item.slug}`), h.Class(className(hubStyles.row))],
    [
      h.a(
        [
          h.Class(className(hubStyles.title)),
          h.Href(entryPath(item.section, item.slug)),
        ],
        [item.title]
      ),
      h.span(
        [h.Class(className(hubStyles.meta))],
        [item.project === "" ? item.date : `${item.project} · ${item.date}`]
      ),
    ]
  );

const emptyLine = (section: SectionValue, h: HtmlBuilder<AppMessage>): Html =>
  h.p([h.Class(className(hubStyles.empty))], [SECTION_TEXT[section].empty]);

const sectionHeading = (
  section: SectionValue,
  items: readonly ItemValue[],
  h: HtmlBuilder<AppMessage>
): Html =>
  h.div(
    [h.Class(className(hubStyles.heading))],
    [
      h.h2([], [SECTION_TEXT[section].name]),
      h.a([h.Href(listPath(section))], [`All ${items.length}`]),
    ]
  );

const homeSection = (
  section: SectionValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Html => {
  const present = itemsIn(model.items, section);

  return h.section(
    [h.Class(className(hubStyles.section))],
    [
      sectionHeading(section, present, h),
      Array.match(present, {
        onEmpty: () => emptyLine(section, h),
        onNonEmpty: (listed) =>
          h.ul(
            [h.Class(className(hubStyles.rows))],
            listed.slice(0, HOME_LIMIT).map((item) => itemRow(item, h))
          ),
      }),
    ]
  );
};

const homeView = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => [
  h.h1([], [SITE_NAME]),
  h.p([], ["Working notes and finished reports from the Software Factory."]),
  homeSection("explorations", model, h),
  homeSection("reports", model, h),
  h.section(
    [h.Class(className(hubStyles.section))],
    [
      h.div(
        [h.Class(className(hubStyles.heading))],
        [h.h2([], ["Factory"]), h.a([h.Href(factoryRouter())], ["Open"])]
      ),
      h.p(
        [h.Class(className(hubStyles.empty))],
        ["PRs shipped versus plan burn, and the output and waste tiles."]
      ),
    ]
  ),
  h.section(
    [h.Class(className(hubStyles.section))],
    [
      h.div(
        [h.Class(className(hubStyles.heading))],
        [h.h2([], ["Usage"]), h.a([h.Href(usageRouter())], ["Open"])]
      ),
      h.p(
        [h.Class(className(hubStyles.empty))],
        ["Plan cards, 1h burn and reset lines."]
      ),
    ]
  ),
  h.section(
    [h.Class(className(hubStyles.section))],
    [
      h.div(
        [h.Class(className(hubStyles.heading))],
        [h.h2([], ["Chats"]), h.a([h.Href(chatsRouter())], ["Open"])]
      ),
      h.p(
        [h.Class(className(hubStyles.empty))],
        ["Every live chat on both servers, with its harness, model and effort."]
      ),
    ]
  ),
];

const listView = (
  section: SectionValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => {
  const present = itemsIn(model.items, section);

  return [
    h.h1([], [SECTION_TEXT[section].name]),
    h.p(
      [h.Class(className(hubStyles.lede))],
      [`${present.length} items. ${SECTION_TEXT[section].blurb}`]
    ),
    Array.match(present, {
      onEmpty: () => emptyLine(section, h),
      onNonEmpty: (listed) =>
        h.ul(
          [h.Class(className(hubStyles.rows))],
          listed.map((item) => itemRow(item, h))
        ),
    }),
  ];
};

const missingView = (h: HtmlBuilder<AppMessage>): readonly Html[] => [
  h.h1([], ["Page not found"]),
  h.p([], [h.a([h.Href(homeRouter())], ["Go to the home page."])]),
];

const titleOf = (route: SiteRouteValue): string =>
  SiteRoute.match(route, {
    Chats: () => "Chats",
    Entry: ({ slug }) => titleFromSlug(slug),
    Factory: () => "Factory",
    Home: () => SITE_NAME,
    List: ({ section }) => SECTION_TEXT[section].name,
    NotFound: () => "Page not found",
    Usage: () => "Usage",
  });

const bodyOf = (
  route: SiteRouteValue,
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  SiteRoute.match(route, {
    Chats: () => chatsView(model, h),
    Entry: () => missingView(h),
    Factory: () => factoryView(model, h),
    Home: () => homeView(model, h),
    List: ({ section }) => listView(section, model, h),
    NotFound: () => missingView(h),
    Usage: () => usageView(model, h),
  });

export const view = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): Document => ({
  body: h.div(
    [h.Class(className(readerStyles.shell))],
    [siteHeader(h), h.main([], bodyOf(model.route, model, h)), siteFooter(h)]
  ),
  title: titleOf(model.route),
});
