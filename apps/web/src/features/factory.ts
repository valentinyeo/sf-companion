import * as stylex from "@stylexjs/stylex";
import { Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import type {
  KpiTileValue,
  ShippingCellValue,
  FactoryFeedValue,
  KpiStateValue,
} from "../content/feed.js";
import { classes, cue } from "./cue.js";
import type { StateWord } from "./cue.js";
import { factoryStyles } from "./factory.stylex.js";
import { usageRouter } from "./route.js";

const ISO_PREFIX =
  /^(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})T(?<hour>\d{2}):(?<minute>\d{2})/u;

const numbersFrom = (iso: string): string => {
  const groups = ISO_PREFIX.exec(iso)?.groups;
  const year = groups?.year;
  const month = groups?.month;
  const day = groups?.day;
  const hour = groups?.hour;
  const minute = groups?.minute;

  return year === undefined ||
    month === undefined ||
    day === undefined ||
    hour === undefined ||
    minute === undefined
    ? `Numbers from ${iso}`
    : `Numbers from ${year}-${month}-${day} ${hour}:${minute} UTC`;
};

const tileStateWord = (state: KpiStateValue): StateWord =>
  state === "ok" ? "ok" : "bad";

const tileStateLabel = (state: KpiStateValue): string =>
  state === "ok" ? "on target" : "off target";

const kpiTileRow = (tile: KpiTileValue, h: HtmlBuilder<AppMessage>): Html =>
  h.li(
    [h.Key(tile.id), h.Class(classes(factoryStyles.tile))],
    [
      h.h3([h.Class(classes(factoryStyles.tileLabel))], [tile.label]),
      h.p([h.Class(classes(factoryStyles.tileValue))], [tile.display]),
      h.p([h.Class(classes(factoryStyles.small))], [tile.source]),
      h.p([h.Class(classes(factoryStyles.meta))], [tile.window]),
      ...tile.details
        .slice(0, 2)
        .map((detail) =>
          h.p([h.Class(classes(factoryStyles.small))], [detail])
        ),
      ...(tile.state === null
        ? []
        : [cue(tileStateWord(tile.state), tileStateLabel(tile.state), h)]),
      ...(tile.details.length <= 2
        ? []
        : [
            h.details(
              [],
              [
                h.summary([], ["Measurement details"]),
                h.ul(
                  [],
                  tile.details.slice(2).map((detail) => h.li([], [detail]))
                ),
              ]
            ),
          ]),
    ]
  );

const kpisSection = (
  feed: FactoryFeedValue,
  h: HtmlBuilder<AppMessage>
): Html =>
  h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], ["Output and waste"]),
      h.p(
        [h.Class(classes(factoryStyles.small))],
        [
          "Each metric uses its own source window. The usage window buttons do not change these readings.",
        ]
      ),
      h.ul(
        [h.Class(classes(factoryStyles.tiles))],
        feed.kpis.tiles.map((tile) => kpiTileRow(tile, h))
      ),
      ...feed.kpis.notes.map((note) =>
        h.p([h.Class(classes(factoryStyles.small))], [note])
      ),
    ]
  );

const shippingCell = (
  cell: ShippingCellValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const bar = stylex.props(
    factoryStyles.bar(cell.kind === "measured" ? cell.barPct : 0)
  );

  return h.td(
    [h.Class(classes(factoryStyles.chartCell))],
    [
      h.details(
        [],
        [
          h.summary(
            [],
            [cell.kind === "measured" ? cell.display : "Unavailable"]
          ),
          ...(cell.kind === "missing" ? [h.p([], [cell.reason])] : []),
          h.p([], [cell.source]),
          h.p([], [cell.window]),
        ]
      ),
      ...(cell.kind === "measured"
        ? [
            h.div(
              [h.AriaHidden(true), h.Class(classes(factoryStyles.barTrack))],
              [
                h.div([
                  h.Class(bar.className ?? ""),
                  h.Style(
                    Object.fromEntries(
                      Object.entries(bar.style ?? {}).map(([key, value]) => [
                        key,
                        String(value),
                      ])
                    )
                  ),
                ]),
              ]
            ),
          ]
        : []),
    ]
  );
};

const omissionNote = (
  items: readonly { readonly plan: string; readonly reason: string }[],
  labels: readonly (readonly [string, string])[]
): string => {
  const groups: { labels: string[]; reason: string }[] = [];

  for (const item of items) {
    const label = labels.find(([plan]) => plan === item.plan)?.[1] ?? item.plan;
    const previous = groups.at(-1);

    if (previous !== undefined && previous.reason === item.reason) {
      previous.labels.push(label);
    } else {
      groups.push({ labels: [label], reason: item.reason });
    }
  }

  return groups
    .map((group) => `${group.labels.join(", ")} omitted: ${group.reason}`)
    .join(" ");
};

const shippingSection = (
  feed: FactoryFeedValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const { shipping } = feed.kpis;

  const burnColumns = Object.entries({
    claude: "Claude",
    codex: "Codex",
    grok: "Grok",
    opencode: "OpenCode",
  });

  const availablePlans = new Set<string>(
    shipping?.days.flatMap((day) =>
      day.burn
        .filter((burn) => burn.reading.kind === "measured")
        .map((burn) => burn.plan)
    )
  );

  const omittedPlans = burnColumns.filter(
    ([plan]) => !availablePlans.has(plan)
  );

  const statedOmissions = shipping?.omissions?.filter(
    (item) => !availablePlans.has(item.plan)
  );

  const omissionItems =
    statedOmissions ??
    omittedPlans.map(([plan]) => ({
      plan,
      reason: "no quota readings on any of the 30 UTC dates.",
    }));

  return h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], ["PRs shipped vs plan burn"]),
      ...(shipping === undefined
        ? [
            h.p(
              [],
              [
                "Daily shipping data unavailable. This feed predates the daily collector.",
              ]
            ),
          ]
        : [
            h.p(
              [h.Class(classes(factoryStyles.small))],
              [
                "Expand any value for its source and UTC window. Scroll the chart horizontally on small screens.",
              ]
            ),
            h.div(
              [
                h.Role("region"),
                h.AriaLabel("Daily shipping and burn chart"),
                h.Tabindex(0),
                h.Class(classes(factoryStyles.chartScroll)),
              ],
              [
                h.table(
                  [h.Class(classes(factoryStyles.chartTable))],
                  [
                    h.caption(
                      [],
                      [
                        "Last 30 UTC dates · fleet merges, observed weekly quota points and attributed £",
                      ]
                    ),
                    h.thead(
                      [h.Class(classes(factoryStyles.chartHead))],
                      [
                        h.tr(
                          [h.Class(classes(factoryStyles.chartRow))],
                          [
                            "UTC date",
                            "Merged PRs",
                            ...burnColumns
                              .filter(([plan]) => availablePlans.has(plan))
                              .map(([, label]) => `${label} pts`),
                            "Attributed £",
                            "Attributed £/PR",
                          ].map((label) =>
                            h.th(
                              [
                                h.Scope("col"),
                                h.Class(classes(factoryStyles.chartCell)),
                              ],
                              [label]
                            )
                          )
                        ),
                      ]
                    ),
                    h.tbody(
                      [h.Class(classes(factoryStyles.chartBody))],
                      shipping.days
                        .toReversed()
                        .map((day) =>
                          h.tr(
                            [
                              h.Key(day.date),
                              h.Class(classes(factoryStyles.chartRow)),
                            ],
                            [
                              h.th(
                                [
                                  h.Scope("row"),
                                  h.Class(classes(factoryStyles.chartCell)),
                                ],
                                [day.date]
                              ),
                              shippingCell(day.merges, h),
                              ...day.burn
                                .filter((burn) => availablePlans.has(burn.plan))
                                .map((burn) => shippingCell(burn.reading, h)),
                              shippingCell(day.cost, h),
                              shippingCell(day.perPr, h),
                            ]
                          )
                        )
                    ),
                  ]
                ),
              ]
            ),
            ...shipping.notes.map((note) =>
              h.p([h.Class(classes(factoryStyles.small))], [note])
            ),
            ...(omissionItems.length === 0
              ? []
              : [
                  h.p(
                    [h.Class(classes(factoryStyles.small))],
                    [omissionNote(omissionItems, burnColumns)]
                  ),
                ]),
          ]),
    ]
  );
};

export const factoryView = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  Option.match(model.feed, {
    onNone: () => [h.h1([], ["Factory"]), h.p([], ["No factory numbers yet."])],
    onSome: (feed) => [
      h.h1([], ["Factory"]),
      h.p(
        [h.Class(classes(factoryStyles.small))],
        [numbersFrom(feed.generatedAt)]
      ),
      h.p(
        [h.Class(classes(factoryStyles.small))],
        [
          h.a([h.Href(usageRouter())], ["Usage"]),
          " has the plan cards, their burn windows and reset lines.",
        ]
      ),
      shippingSection(feed, h),
      kpisSection(feed, h),
    ],
  });
