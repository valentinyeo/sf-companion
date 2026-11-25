import type * as stylex from "@stylexjs/stylex";
import { DateTime, Option } from "effect";
import type { Html, HtmlBuilder } from "foldkit/html";

import type { AppMessage } from "../client/app/message.js";
import type { AppModel } from "../client/app/model.js";
import type {
  BurnByWindowValue,
  FactoryFeedValue,
  ToneValue,
  UsageCardValue,
  WindowReadingValue,
} from "../content/feed.js";
import { classes, cue } from "./cue.js";
import { factoryStyles } from "./factory.stylex.js";

const BURN_WINDOW = "1h";

const MILLIS_PER_MINUTE = 60_000;

const USAGE_PAGES: Readonly<Record<UsageCardValue["plan"], string>> = {
  antigravity: "https://antigravity.google/",
  claude: "https://claude.ai/new#settings/usage",
  codex: "https://chatgpt.com/settings/usage?tab=overview",
  commandcode: "https://commandcode.ai/",
  opencode: "https://opencode.ai/console/wrk_01KF5VZPS53BNVE2RR9QAYJSB4/go",
  openrouter: "https://openrouter.ai/settings/credits",
  vercel: "https://vercel.com/hypertaskai/~/ai-gateway/token-pass",
};

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

const toneStyle = (tone: ToneValue): stylex.StyleXStyles | null => {
  if (tone === "hot") {
    return factoryStyles.bigValueHot;
  }

  return tone === "warm" ? factoryStyles.bigValueWarm : null;
};

const toneWord = (tone: ToneValue): string => {
  if (tone === "hot") {
    return "well over pace";
  }

  return tone === "warm" ? "over pace" : "at pace";
};

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
    if (card.mode !== "credit") {
      return "";
    }

    if (card.creditSubLabel === "estimate") {
      return `estimate${card.creditAsOf ?? ""}`;
    }

    return card.creditAsOf === null ? "" : card.creditAsOf.replace(/^ · /u, "");
  }

  const prefix =
    card.mode === "credit" && card.creditSubLabel !== null
      ? `${card.creditSubLabel} · `
      : "";

  return `${prefix}resets ${card.resetsText}${card.creditAsOf ?? ""}`;
};

const burnLine = (card: UsageCardValue, burn: BurnByWindowValue): string => {
  const cell = burn[BURN_WINDOW]?.[card.plan];

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

  return `${body === "" ? "" : `${body} `}in ${BURN_WINDOW}${runners}${today}`;
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

const skipLine = (card: UsageCardValue): string | null =>
  card.skip === null
    ? null
    : `Skipped until ${card.skip.untilText} (${card.skip.reason})`;

const updatedText = (generatedAt: string, nowMs: number): string | null =>
  Option.match(DateTime.make(generatedAt), {
    onNone: () => null,
    onSome: (generated) => {
      const minutes = Math.floor(
        Math.max(0, nowMs - DateTime.toEpochMillis(generated)) /
          MILLIS_PER_MINUTE
      );
      const clock = DateTime.formatLocal(generated, {
        hour: "2-digit",
        hourCycle: "h23",
        locale: "en-GB",
        minute: "2-digit",
      });

      return `Updated ${clock} (${minutes} min ago)`;
    },
  });

const updatedLine = (
  generatedAt: string,
  nowMs: Option.Option<number>,
  h: HtmlBuilder<AppMessage>
): Html | null =>
  Option.match(nowMs, {
    onNone: () => null,
    onSome: (measured) => {
      const line = updatedText(generatedAt, measured);

      return line === null
        ? null
        : h.p([h.Class(classes(factoryStyles.small))], [line]);
    },
  });

const usageCard = (
  card: UsageCardValue,
  burn: BurnByWindowValue,
  h: HtmlBuilder<AppMessage>
): Html => {
  const reset = resetLine(card);
  const summary = bigNumber(card);
  const pace = paceLine(card, h);
  const skip = skipLine(card);
  const details = windowsDetails(card.windows, h);

  return h.li(
    [h.Key(card.plan), h.Class(classes(factoryStyles.card))],
    [
      h.div(
        [h.Class(classes(factoryStyles.cardTop))],
        [
          h.h3(
            [h.Class(classes(factoryStyles.cardName))],
            [
              h.a(
                [
                  h.Href(USAGE_PAGES[card.plan]),
                  h.Rel("noopener"),
                  h.Target("_blank"),
                ],
                [card.name]
              ),
            ]
          ),
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
      ...(skip === null
        ? []
        : [h.p([h.Class(classes(factoryStyles.small))], [skip])]),
      ...(card.note === null
        ? []
        : [h.p([h.Class(classes(factoryStyles.small))], [card.note])]),
      h.p([h.Class(classes(factoryStyles.small))], [burnLine(card, burn)]),
      ...(details === null ? [] : [details]),
      h.p([h.Class(classes(factoryStyles.loadLine))], [card.loadText]),
      h.p([h.Class(classes(factoryStyles.small))], [card.runnersText]),
    ]
  );
};

const usageCards = (
  feed: FactoryFeedValue,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  feed.usage.cards.length === 0
    ? [h.p([], ["No plans yet."])]
    : [
        h.ul(
          [h.Class(classes(factoryStyles.cards))],
          feed.usage.cards.map((card) => usageCard(card, feed.usage.burn, h))
        ),
      ];

export const usageView = (
  model: AppModel,
  h: HtmlBuilder<AppMessage>
): readonly Html[] =>
  Option.match(model.feed, {
    onNone: () => [h.h1([], ["Usage"]), h.p([], ["No usage numbers yet."])],
    onSome: (feed) => {
      const age = updatedLine(feed.generatedAt, model.nowMs, h);

      return [
        h.h1([], ["Usage"]),
        ...(age === null ? [] : [age]),
        h.section(
          [h.Class(classes(factoryStyles.section))],
          usageCards(feed, h)
        ),
      ];
    },
  });
