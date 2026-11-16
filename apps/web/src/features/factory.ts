import * as stylex from "@stylexjs/stylex";
import { Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import { windowKeys } from "../content/feed.js";
import type {
  KpiTileValue,
  ShippingCellValue,
  BurnByWindowValue,
  FactoryFeedValue,
  KpiStateValue,
  ToneValue,
  UsageCardValue,
  WindowKeyValue,
  WindowReadingValue,
} from "../content/feed.js";
import { factoryStyles } from "./factory.stylex.js";

type StateWord = "ok" | "bad" | "warm" | "hot";

const classes = (...styles: readonly (stylex.StyleXStyles | null)[]): string =>
  stylex.props(
    ...styles.filter((style): style is stylex.StyleXStyles => style !== null)
  ).className ?? "";

const trimmed = (value: number): string => {
  const fixed = value.toFixed(2);

  if (fixed.endsWith(".00")) {
    return fixed.slice(0, -3);
  }

  return fixed.endsWith("0") ? fixed.slice(0, -1) : fixed;
};

const signed = (value: number): string =>
  `${value >= 0 ? "+" : ""}${trimmed(value)}`;

const percent = (value: number): string => `${value.toFixed(0)}%`;

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

const toneStyle = (tone: ToneValue): stylex.StyleXStyles | null => {
  if (tone === "hot") {
    return factoryStyles.bigValueHot;
  }

  return tone === "warm" ? factoryStyles.bigValueWarm : null;
};

const cueStyle = (word: StateWord): stylex.StyleXStyles => {
  if (word === "ok") {
    return factoryStyles.cueOk;
  }

  if (word === "bad") {
    return factoryStyles.cueBad;
  }

  return word === "warm" ? factoryStyles.cueWarm : factoryStyles.cueHot;
};

const cue = (
  word: StateWord,
  label: string,
  h: HtmlBuilder<AppMessage>
): Html =>
  h.span([h.Class(classes(factoryStyles.cue, cueStyle(word)))], [label]);

const toneWord = (tone: ToneValue): string => {
  if (tone === "hot") {
    return "well over pace";
  }

  return tone === "warm" ? "over pace" : "at pace";
};

const tileStateWord = (state: KpiStateValue): StateWord =>
  state === "ok" ? "ok" : "bad";

const tileStateLabel = (state: KpiStateValue): string =>
  state === "ok" ? "on target" : "off target";

const bigNumber = (card: UsageCardValue): string => {
  if (card.mode === "credit" && card.creditUsd !== null) {
    return `$${card.creditUsd.toFixed(2)} left`;
  }

  return card.mode === "percent" && card.usedPct !== null
    ? percent(card.usedPct)
    : "no reading";
};

const resetLine = (card: UsageCardValue): string => {
  if (card.resetsText === null) {
    return card.mode === "credit" && card.creditAsOf !== null
      ? card.creditAsOf.replace(/^ · /u, "")
      : "";
  }

  const prefix =
    card.mode === "credit" && card.creditSubLabel !== null
      ? `${card.creditSubLabel} · `
      : "";

  return `${prefix}resets ${card.resetsText}${card.creditAsOf ?? ""}`;
};

const burnLine = (
  card: UsageCardValue,
  burn: BurnByWindowValue,
  windowKey: WindowKeyValue
): string => {
  const cell = burn[windowKey]?.[card.plan];

  if (cell === undefined) {
    return "–";
  }

  const { gbp, pts } = cell;

  if ((pts === null || pts === 0) && (gbp === null || gbp === 0)) {
    return "–";
  }

  const dropPercent = !(card.mode === "credit" && card.plan === "opencode");

  const parts: readonly string[] = [
    dropPercent && pts !== null ? `+${trimmed(pts)}%` : "",
    gbp === null ? "" : `£${gbp.toFixed(2)}`,
  ].filter((part) => part !== "");

  const body = parts.join(" · ");

  const runners =
    cell.pricedPts === null || cell.pricedPts === pts ? "" : " on runners";

  const today =
    dropPercent || cell.todayUsd === null
      ? ""
      : ` · $${cell.todayUsd.toFixed(2)} today`;

  return `${body === "" ? "" : `${body} `}in ${windowKey}${runners}${today}`;
};

const paceLine = (
  card: UsageCardValue,
  h: HtmlBuilder<AppMessage>
): Html | null => {
  if (card.paceDelta === null || card.mode === "credit") {
    return null;
  }

  return h.p(
    [h.Class(classes(factoryStyles.small))],
    [
      `${signed(card.paceDelta)} vs pace · `,
      cue(card.tone === "plain" ? "ok" : card.tone, toneWord(card.tone), h),
    ]
  );
};

const windowsDetails = (
  windows: readonly WindowReadingValue[],
  h: HtmlBuilder<AppMessage>
): Html | null =>
  windows.length === 0
    ? null
    : h.details(
        [h.Class(classes(factoryStyles.details))],
        [
          h.summary([], ["Windows"]),
          h.ul(
            [h.Class(classes(factoryStyles.windowsList))],
            windows.map((reading) =>
              h.li(
                [h.Key(reading.label)],
                [
                  `${reading.label} ${
                    reading.usedPct === null ? "–" : percent(reading.usedPct)
                  }`,
                ]
              )
            )
          ),
        ]
      );

const usageCard = (
  card: UsageCardValue,
  burn: BurnByWindowValue,
  windowKey: WindowKeyValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const reset = resetLine(card);
  const summary = bigNumber(card);
  const pace = paceLine(card, h);
  const details = windowsDetails(card.windows, h);

  return h.li(
    [h.Key(card.plan), h.Class(classes(factoryStyles.card))],
    [
      h.div(
        [h.Class(classes(factoryStyles.cardTop))],
        [
          h.h3([h.Class(classes(factoryStyles.cardName))], [card.name]),
          ...(reset === ""
            ? []
            : [h.p([h.Class(classes(factoryStyles.reset))], [reset])]),
        ]
      ),
      h.p(
        [h.Class(classes(factoryStyles.bigValue, toneStyle(card.tone)))],
        [summary]
      ),
      ...(pace === null ? [] : [pace]),
      h.p(
        [h.Class(classes(factoryStyles.small))],
        [burnLine(card, burn, windowKey)]
      ),
      ...(details === null ? [] : [details]),
      h.p([h.Class(classes(factoryStyles.small))], [card.runnersText]),
    ]
  );
};

const usageSection = (
  feed: FactoryFeedValue,
  windowKey: WindowKeyValue,
  h: HtmlBuilder<AppMessage>
): Html =>
  h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], ["Usage"]),
      picker(windowKey, h),
      ...(feed.usage.cards.length === 0
        ? [h.p([], ["No plans yet."])]
        : [
            h.ul(
              [h.Class(classes(factoryStyles.cards))],
              feed.usage.cards.map((card) =>
                usageCard(card, feed.usage.burn, windowKey, h)
              )
            ),
          ]),
    ]
  );

const picker = (selected: WindowKeyValue, h: HtmlBuilder<AppMessage>): Html =>
  h.div(
    [
      h.Role("group"),
      h.AriaLabel("Usage window"),
      h.Class(classes(factoryStyles.picker)),
    ],
    windowKeys.map((key) =>
      h.button(
        [
          h.Key(key),
          h.Type("button"),
          h.AriaPressed(key === selected ? "true" : "false"),
          h.OnClick(Message.SelectedKpiWindow({ window: key })),
          h.Class(
            classes(
              factoryStyles.pickerButton,
              key === selected ? factoryStyles.pickerSelected : null
            )
          ),
        ],
        [key]
      )
    )
  );

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
          "Each metric uses its own source window. Usage buttons do not change these readings.",
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
      shippingSection(feed, h),
      usageSection(feed, model.kpiWindow, h),
      kpisSection(feed, h),
    ],
  });
