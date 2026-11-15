import * as stylex from "@stylexjs/stylex";
import type { Html, HtmlBuilder } from "foldkit/html";

import { Message } from "../client/app/message.js";
import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import { windowKeys } from "../content/feed.js";
import type {
  BigTile,
  BurnByWindow,
  FactoryFeed,
  HourBucket,
  KpiState,
  KpiWindow,
  MoreTile,
  Tone,
  UsageCard,
  Violations,
  WindowKey,
  WindowReading,
} from "../content/feed.js";
import { factoryStyles } from "./factory.stylex.js";

type Ui = HtmlBuilder<AppMessage>;

type StateWord = "ok" | "bad" | "warm" | "hot";

const classes = (
  ...styles: ReadonlyArray<stylex.StyleXStyles | null>
): string =>
  stylex
    .props(
      ...styles.filter(
        (style): style is stylex.StyleXStyles => style !== null
      )
    )
    .className ?? "";

const trimmed = (value: number): string => {
  const fixed = value.toFixed(2);

  return fixed.endsWith(".00")
    ? fixed.slice(0, -3)
    : fixed.endsWith("0")
      ? fixed.slice(0, -1)
      : fixed;
};

const signed = (value: number): string =>
  `${value >= 0 ? "+" : ""}${trimmed(value)}`;

const percent = (value: number): string => `${value.toFixed(0)}%`;

const hourLabel = (t: number): string =>
  `${String(Math.floor(t / 3600) % 24).padStart(2, "0")}:00`;

const ISO_PREFIX = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/u;

const numbersFrom = (iso: string): string => {
  const parts = ISO_PREFIX.exec(iso);
  const year = parts?.[1];
  const month = parts?.[2];
  const day = parts?.[3];
  const hour = parts?.[4];
  const minute = parts?.[5];

  return year === undefined ||
    month === undefined ||
    day === undefined ||
    hour === undefined ||
    minute === undefined
    ? `Numbers from ${iso}`
    : `Numbers from ${year}-${month}-${day} ${hour}:${minute} UTC`;
};

const toneStyle = (tone: Tone): stylex.StyleXStyles | null =>
  tone === "hot"
    ? factoryStyles.bigValueHot
    : tone === "warm"
      ? factoryStyles.bigValueWarm
      : null;

const cueStyle = (word: StateWord): stylex.StyleXStyles =>
  word === "ok"
    ? factoryStyles.cueOk
    : word === "bad"
      ? factoryStyles.cueBad
      : word === "warm"
        ? factoryStyles.cueWarm
        : factoryStyles.cueHot;

const cue = (word: StateWord, label: string, h: Ui): Html =>
  h.span([h.Class(classes(factoryStyles.cue, cueStyle(word)))], [label]);

const toneWord = (tone: Tone): string =>
  tone === "hot"
    ? "well over pace"
    : tone === "warm"
      ? "over pace"
      : "at pace";

const tileStateWord = (state: KpiState): StateWord =>
  state === "ok" ? "ok" : "bad";

const tileStateLabel = (state: KpiState): string =>
  state === "ok" ? "on target" : "off target";

const bigNumber = (card: UsageCard): string => {
  if (card.mode === "credit" && card.creditUsd !== null) {
    return `$${card.creditUsd.toFixed(2)} left`;
  }

  return card.mode === "percent" && card.usedPct !== null
    ? percent(card.usedPct)
    : "no reading";
};

const resetLine = (card: UsageCard): string => {
  if (card.resetsText === null) {
    return "";
  }

  const prefix =
    card.mode === "credit" && card.creditSubLabel !== null
      ? `${card.creditSubLabel} · `
      : "";

  return `${prefix}resets ${card.resetsText}${card.creditAsOf ?? ""}`;
};

const burnLine = (
  card: UsageCard,
  burn: BurnByWindow,
  window: WindowKey
): string => {
  const cell = burn[window]?.[card.plan];

  if (cell === undefined) {
    return "–";
  }

  const { gbp, pts } = cell;

  if ((pts === null || pts === 0) && (gbp === null || gbp === 0)) {
    return "–";
  }

  const dropPercent = !(card.mode === "credit" && card.plan === "opencode");
  const parts: ReadonlyArray<string> = [
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

  return `${body === "" ? "" : `${body} `}in ${window}${runners}${today}`;
};

const paceLine = (card: UsageCard, h: Ui): Html | null => {
  if (card.paceDelta === null || card.mode === "credit") {
    return null;
  }

  return h.p([h.Class(classes(factoryStyles.small))], [
    `${signed(card.paceDelta)} vs pace · `,
    cue(card.tone === "plain" ? "ok" : card.tone, toneWord(card.tone), h),
  ]);
};

const windowsDetails = (
  windows: ReadonlyArray<WindowReading>,
  h: Ui
): Html | null =>
  windows.length === 0
    ? null
    : h.details([h.Class(classes(factoryStyles.details))], [
        h.summary([], ["Windows"]),
        h.ul([h.Class(classes(factoryStyles.windowsList))], [
          ...windows.map((reading) =>
            h.li([h.Key(reading.label)], [
              `${reading.label} ${
                reading.usedPct === null ? "–" : percent(reading.usedPct)
              }`,
            ])
          ),
        ]),
      ]);

const usageCard = (
  card: UsageCard,
  burn: BurnByWindow,
  window: WindowKey,
  h: Ui
): Html => {
  const reset = resetLine(card);
  const summary = bigNumber(card);
  const pace = paceLine(card, h);
  const details = windowsDetails(card.windows, h);

  return h.li([h.Key(card.plan), h.Class(classes(factoryStyles.card))], [
    h.div([h.Class(classes(factoryStyles.cardTop))], [
      h.h3([h.Class(classes(factoryStyles.cardName))], [card.name]),
      ...(reset === ""
        ? []
        : [h.p([h.Class(classes(factoryStyles.reset))], [reset])]),
    ]),
    h.p(
      [h.Class(classes(factoryStyles.bigValue, toneStyle(card.tone)))],
      [summary]
    ),
    ...(pace === null ? [] : [pace]),
    h.p([h.Class(classes(factoryStyles.small))], [
      burnLine(card, burn, window),
    ]),
    ...(details === null ? [] : [details]),
    h.p([h.Class(classes(factoryStyles.small))], [card.runnersText]),
  ]);
};

const usageSection = (
  feed: FactoryFeed,
  window: WindowKey,
  h: Ui
): Html =>
  h.section([h.Class(classes(factoryStyles.section))], [
    h.h2([], ["Usage"]),
    ...(feed.usage.cards.length === 0
      ? [h.p([], ["No plans yet."])]
      : [
          h.ul([h.Class(classes(factoryStyles.cards))], [
            ...feed.usage.cards.map((card) =>
              usageCard(card, feed.usage.burn, window, h)
            ),
          ]),
        ]),
  ]);

const picker = (selected: WindowKey, h: Ui): Html =>
  h.div(
    [
      h.Role("group"),
      h.AriaLabel("KPI window"),
      h.Class(classes(factoryStyles.picker)),
    ],
    [
      ...windowKeys.map((key) =>
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
      ),
    ]
  );

const bigTileRow = (tile: BigTile, h: Ui): Html =>
  h.li([h.Key(tile.id), h.Class(classes(factoryStyles.tile))], [
    h.p([h.Class(classes(factoryStyles.tileLabel))], [tile.label]),
    h.p([h.Class(classes(factoryStyles.tileValue))], [tile.display]),
    ...(tile.sub === null
      ? []
      : [h.p([h.Class(classes(factoryStyles.small))], [tile.sub])]),
    h.p([h.Class(classes(factoryStyles.meta))], [
      ...(tile.target === null ? [] : [`target ${tile.target}`]),
      ...(tile.target === null || tile.state === null ? [] : ["·"]),
      ...(tile.state === null
        ? []
        : [cue(tileStateWord(tile.state), tileStateLabel(tile.state), h)]),
    ]),
  ]);

const barLevels: ReadonlyArray<stylex.StyleXStyles> = [
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

const barLevel = (violations: number, top: number): number =>
  violations === 0
    ? 0
    : Math.min(8, Math.max(1, Math.ceil((violations / top) * 8)));

const hourLabels = (hours: ReadonlyArray<HourBucket>, h: Ui): readonly Html[] =>
  hours
    .filter((_bucket, index) => index % 4 === 0)
    .map((bucket) =>
      h.span(
        [
          h.Key(`label-${String(bucket.t)}`),
          h.Class(classes(factoryStyles.hourLabel)),
        ],
        [hourLabel(bucket.t)]
      )
    );

const chart = (violations: Violations, h: Ui): Html => {
  const top = Math.max(violations.top, 1);
  const hours = violations.hourly;

  return h.figure([h.Class(classes(factoryStyles.chartFigure))], [
    h.figcaption([h.Class(classes(factoryStyles.axis))], [
      `Violations per hour, last 24h, scale 0 to ${String(top)}`,
    ]),
    ...(hours.length === 0
      ? [h.p([h.Class(classes(factoryStyles.small))], ["No hourly readings."])]
      : [
          h.div(
            [
              h.Role("img"),
              h.AriaLabel(
                `Violations per hour, last 24 hours, scale 0 to ${String(top)}`
              ),
              h.Class(classes(factoryStyles.bars)),
            ],
            [
              ...hours.map((bucket) =>
                h.div(
                  [
                    h.Key(String(bucket.t)),
                    h.Class(classes(factoryStyles.column)),
                  ],
                  [
                    h.span([h.Class(classes(factoryStyles.count))], [
                      bucket.violations === 0
                        ? ""
                        : String(bucket.violations),
                    ]),
                    h.div(
                      [
                        h.Class(
                          classes(
                            barLevels[barLevel(bucket.violations, top)] ??
                              factoryStyles.bar,
                            bucket.violations > 0
                              ? factoryStyles.barLit
                              : factoryStyles.barQuiet
                          )
                        ),
                        h.Title(
                          `${hourLabel(bucket.t)}: ${String(
                            bucket.violations
                          )} violations, ${String(bucket.runs)} runs`
                        ),
                      ],
                      []
                    ),
                  ]
                )
              ),
            ]
          ),
          h.div([h.Class(classes(factoryStyles.hourLabels))], [
            ...hourLabels(hours, h),
          ]),
        ]),
  ]);
};

const moreRow = (tiles: ReadonlyArray<MoreTile>, h: Ui): Html =>
  h.details([h.Class(classes(factoryStyles.details))], [
    h.summary([], ["More"]),
    h.dl([h.Class(classes(factoryStyles.moreGrid))], [
      ...tiles.map((tile) =>
        h.div([h.Key(tile.id), h.Class(classes(factoryStyles.moreRow))], [
          h.dt([], [tile.label]),
          h.dd([h.Class(classes(factoryStyles.moreValue))], [
            tile.sub === null ? tile.display : `${tile.display} · ${tile.sub}`,
          ]),
        ])
      ),
    ]),
  ]);

const windowBody = (
  numbers: KpiWindow,
  violations: Violations,
  h: Ui
): readonly Html[] => [
  ...(numbers.note === null
    ? []
    : [h.p([h.Class(classes(factoryStyles.small))], [numbers.note])]),
  h.h3([], ["Output"]),
  h.ul([h.Class(classes(factoryStyles.tiles))], [
    ...numbers.big.slice(0, 3).map((tile) => bigTileRow(tile, h)),
  ]),
  h.h3([], ["Waste"]),
  h.ul([h.Class(classes(factoryStyles.tiles))], [
    ...numbers.big.slice(3).map((tile) => bigTileRow(tile, h)),
  ]),
  chart(violations, h),
  moreRow(numbers.more, h),
];

const kpisSection = (
  feed: FactoryFeed,
  window: WindowKey,
  h: Ui
): Html => {
  const numbers = feed.kpis.windows[window];

  return h.section([h.Class(classes(factoryStyles.section))], [
    h.h2([], ["KPIs"]),
    picker(window, h),
    ...(numbers === undefined
      ? [
          h.p([h.Class(classes(factoryStyles.small))], [
            "No numbers for this window.",
          ]),
        ]
      : windowBody(numbers, feed.kpis.violations, h)),
  ]);
};

export const factoryView = (
  model: AppModel,
  h: Ui
): readonly Html[] => {
  if (model.feed === null) {
    return [
      h.h1([], ["Factory"]),
      h.p([], ["No factory numbers yet."]),
    ];
  }

  return [
    h.h1([], ["Factory"]),
    h.p([h.Class(classes(factoryStyles.small))], [
      numbersFrom(model.feed.generatedAt),
    ]),
    usageSection(model.feed, model.kpiWindow, h),
    kpisSection(model.feed, model.kpiWindow, h),
  ];
};
