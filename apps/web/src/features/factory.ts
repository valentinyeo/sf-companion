import * as stylex from "@stylexjs/stylex";
import { Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import { windowKeys } from "../content/feed.js";
import type {
  BigTileValue,
  BurnByWindowValue,
  FactoryFeedValue,
  HourBucketValue,
  KpiStateValue,
  KpiWindowValue,
  MoreTileValue,
  ToneValue,
  UsageCardValue,
  ViolationsValue,
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

const hourLabel = (t: number): string =>
  `${String(Math.floor(t / 3600) % 24).padStart(2, "0")}:00`;

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
      h.AriaLabel("KPI window"),
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

const bigTileRow = (tile: BigTileValue, h: HtmlBuilder<AppMessage>): Html =>
  h.li(
    [h.Key(tile.id), h.Class(classes(factoryStyles.tile))],
    [
      h.p([h.Class(classes(factoryStyles.tileLabel))], [tile.label]),
      h.p([h.Class(classes(factoryStyles.tileValue))], [tile.display]),
      ...(tile.sub === null
        ? []
        : [h.p([h.Class(classes(factoryStyles.small))], [tile.sub])]),
      h.p(
        [h.Class(classes(factoryStyles.meta))],
        [
          ...(tile.target === null ? [] : [`target ${tile.target}`]),
          ...(tile.target === null || tile.state === null ? [] : ["·"]),
          ...(tile.state === null
            ? []
            : [cue(tileStateWord(tile.state), tileStateLabel(tile.state), h)]),
        ]
      ),
    ]
  );

const barLevels: readonly stylex.StyleXStyles[] = [
  factoryStyles.bar,
  factoryStyles.barLevel1,
  factoryStyles.barLevel2,
  factoryStyles.barLevel3,
  factoryStyles.barLevel4,
  factoryStyles.barLevel5,
  factoryStyles.barLevel6,
  factoryStyles.barLevel7,
  factoryStyles.barLevel8,
];

const barLevel = (violations: number, maxPerHour: number): number =>
  violations === 0
    ? 0
    : Math.min(8, Math.max(1, Math.ceil((violations / maxPerHour) * 8)));

const barStyles = (
  violations: number,
  maxPerHour: number
): readonly stylex.StyleXStyles[] => [
  barLevels[barLevel(violations, maxPerHour)] ?? factoryStyles.bar,
  violations === 0 ? factoryStyles.barQuiet : factoryStyles.barLit,
];

const hourLabels = (
  hours: readonly HourBucketValue[],
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  hours.flatMap((bucket, index) =>
    index % 4 === 0
      ? [
          h.span(
            [
              h.Key(`label-${String(bucket.t)}`),
              h.Class(classes(factoryStyles.hourLabel)),
            ],
            [hourLabel(bucket.t)]
          ),
        ]
      : []
  );

const chart = (
  violations: ViolationsValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const maxPerHour = Math.max(violations.top, 1);
  const hours = violations.hourly;

  return h.figure(
    [h.Class(classes(factoryStyles.chartFigure))],
    [
      h.figcaption(
        [h.Class(classes(factoryStyles.axis))],
        [`Violations per hour, last 24h, scale 0 to ${String(maxPerHour)}`]
      ),
      ...(hours.length === 0
        ? [
            h.p(
              [h.Class(classes(factoryStyles.small))],
              ["No hourly readings."]
            ),
          ]
        : [
            h.div(
              [
                h.Role("img"),
                h.AriaLabel("Violations per hour, last 24 hours"),
                h.Class(classes(factoryStyles.bars)),
              ],
              hours.map((bucket) =>
                h.div(
                  [
                    h.Key(String(bucket.t)),
                    h.Class(classes(factoryStyles.column)),
                  ],
                  [
                    h.span(
                      [h.Class(classes(factoryStyles.count))],
                      [bucket.violations === 0 ? "" : String(bucket.violations)]
                    ),
                    h.div([
                      h.Class(
                        classes(...barStyles(bucket.violations, maxPerHour))
                      ),
                      h.Title(
                        `${hourLabel(bucket.t)}: ${String(
                          bucket.violations
                        )} violations, ${String(bucket.runs)} runs`
                      ),
                    ]),
                  ]
                )
              )
            ),
            h.div(
              [h.Class(classes(factoryStyles.hourLabels))],
              [...hourLabels(hours, h)]
            ),
          ]),
    ]
  );
};

const moreRow = (
  tiles: readonly MoreTileValue[],
  h: HtmlBuilder<AppMessage>
): Html =>
  h.details(
    [h.Class(classes(factoryStyles.details))],
    [
      h.summary([], ["More"]),
      h.dl(
        [h.Class(classes(factoryStyles.moreGrid))],
        tiles.map((tile) =>
          h.div(
            [h.Key(tile.id), h.Class(classes(factoryStyles.moreRow))],
            [
              h.dt([], [tile.label]),
              h.dd(
                [h.Class(classes(factoryStyles.moreValue))],
                [
                  tile.sub === null
                    ? tile.display
                    : `${tile.display} · ${tile.sub}`,
                ]
              ),
            ]
          )
        )
      ),
    ]
  );

const windowBody = (
  numbers: KpiWindowValue,
  violations: ViolationsValue,
  h: HtmlBuilder<AppMessage>
): readonly Html[] => [
  ...(numbers.note === null
    ? []
    : [h.p([h.Class(classes(factoryStyles.small))], [numbers.note])]),
  h.h3([], ["Output"]),
  h.ul(
    [h.Class(classes(factoryStyles.tiles))],
    numbers.big.slice(0, 3).map((tile) => bigTileRow(tile, h))
  ),
  h.h3([], ["Waste"]),
  h.ul(
    [h.Class(classes(factoryStyles.tiles))],
    numbers.big.slice(3).map((tile) => bigTileRow(tile, h))
  ),
  chart(violations, h),
  moreRow(numbers.more, h),
];

const kpisSection = (
  feed: FactoryFeedValue,
  windowKey: WindowKeyValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const numbers = feed.kpis.windows[windowKey];

  return h.section(
    [h.Class(classes(factoryStyles.section))],
    [
      h.h2([], ["KPIs"]),
      picker(windowKey, h),
      ...(numbers === undefined
        ? [
            h.p(
              [h.Class(classes(factoryStyles.small))],
              ["No numbers for this window."]
            ),
          ]
        : windowBody(numbers, feed.kpis.violations, h)),
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
      usageSection(feed, model.kpiWindow, h),
      kpisSection(feed, model.kpiWindow, h),
    ],
  });
