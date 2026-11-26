import { Effect, Schema } from "effect";

import { BurnReport } from "./burn.js";

export const PlanKey = Schema.Literals([
  "claude",
  "codex",
  "grok",
  "opencode",
  "vercel",
  "deepseek",
  "openrouter",
  "antigravity",
  "commandcode",
  "cursor",
]);

export type PlanKeyValue = typeof PlanKey.Type;

const UsagePlan = Schema.Literals([
  "claude",
  "codex",
  "opencode",
  "vercel",
  "openrouter",
  "antigravity",
  "commandcode",
]);

export const WindowKey = Schema.Literals(["1h"]);

export type WindowKeyValue = typeof WindowKey.Type;

const PrimaryWindowKey = Schema.Literals(["week", "month"]);

const UsageMode = Schema.Literals(["percent", "credit", "none"]);

const Tone = Schema.Literals(["plain", "warm", "hot"]);

export type ToneValue = typeof Tone.Type;

const CreditSubLabel = Schema.Literals(["credit", "month full", "estimate"]);

const KpiState = Schema.Literals(["ok", "bad"]);

const WindowReading = Schema.Struct({
  label: Schema.NonEmptyString,
  usedPct: Schema.NullOr(Schema.Number),
});

const Reviewer = Schema.Struct({
  known: Schema.Boolean,
  show: Schema.Boolean,
  tip: Schema.String,
});

const CardSkip = Schema.Struct({
  reason: Schema.NonEmptyString,
  untilText: Schema.NonEmptyString,
});

const UsageCard = Schema.Struct({
  creditAsOf: Schema.NullOr(Schema.String),
  creditReadAt: Schema.NullOr(Schema.String),
  creditSubLabel: Schema.NullOr(CreditSubLabel),
  creditUsd: Schema.NullOr(Schema.Number),
  loadText: Schema.NonEmptyString,
  mode: UsageMode,
  name: Schema.NonEmptyString,
  note: Schema.NullOr(Schema.NonEmptyString),
  paceDelta: Schema.NullOr(Schema.Number),
  plan: UsagePlan,
  primaryWindow: PrimaryWindowKey,
  resetsText: Schema.NullOr(Schema.String),
  reviewer: Reviewer,
  runnersLive: Schema.Boolean,
  runnersText: Schema.String,
  skip: Schema.NullOr(CardSkip),
  tone: Tone,
  usedPct: Schema.NullOr(Schema.Number),
  windows: Schema.Array(WindowReading),
});

export type UsageCardValue = typeof UsageCard.Type;

export type WindowReadingValue = typeof WindowReading.Type;

const BurnCell = Schema.Struct({
  gbp: Schema.NullOr(Schema.Number),
  pricedPts: Schema.NullOr(Schema.Number),
  pts: Schema.NullOr(Schema.Number),
  todayUsd: Schema.NullOr(Schema.Number),
});

export type BurnCellValue = typeof BurnCell.Type;

const BurnByPlan = Schema.Struct({
  claude: Schema.optional(BurnCell),
  codex: Schema.optional(BurnCell),
  opencode: Schema.optional(BurnCell),
  vercel: Schema.optional(BurnCell),
  openrouter: Schema.optional(BurnCell),
  antigravity: Schema.optional(BurnCell),
  commandcode: Schema.optional(BurnCell),
});

const BurnByWindow = Schema.Struct({
  "1h": Schema.optional(BurnByPlan),
});

export type BurnByWindowValue = typeof BurnByWindow.Type;

const KpiTile = Schema.Struct({
  details: Schema.NonEmptyArray(Schema.NonEmptyString),
  display: Schema.NonEmptyString,
  id: Schema.Literals([
    "delivered",
    "verifier",
    "pace",
    "loops",
    "merges",
    "identity",
    "ci",
  ]),
  label: Schema.NonEmptyString,
  source: Schema.NonEmptyString,
  state: Schema.NullOr(KpiState),
  window: Schema.NonEmptyString,
});

export type KpiTileValue = typeof KpiTile.Type;

export type KpiStateValue = typeof KpiState.Type;

const ShippingCell = Schema.Union([
  Schema.Struct({
    kind: Schema.Literal("measured"),
    value: Schema.Finite.check(Schema.isGreaterThanOrEqualTo(0)),
    display: Schema.NonEmptyString,
    barPct: Schema.Finite.check(Schema.isBetween({ minimum: 0, maximum: 100 })),
    source: Schema.NonEmptyString,
    window: Schema.NonEmptyString,
  }),
  Schema.Struct({
    kind: Schema.Literal("missing"),
    reason: Schema.NonEmptyString,
    source: Schema.NonEmptyString,
    window: Schema.NonEmptyString,
  }),
]);

export type ShippingCellValue = typeof ShippingCell.Type;

const Shipping = Schema.Struct({
  days: Schema.Array(
    Schema.Struct({
      date: Schema.NonEmptyString,
      merges: ShippingCell,
      burn: Schema.Array(
        Schema.Struct({ plan: PlanKey, reading: ShippingCell })
      ),
      cost: ShippingCell,
      perPr: ShippingCell,
    })
  ),
  notes: Schema.Array(Schema.NonEmptyString),
  omissions: Schema.optional(
    Schema.Array(
      Schema.Struct({
        plan: PlanKey,
        reason: Schema.NonEmptyString,
      })
    )
  ),
});

export const FactoryFeed = Schema.Struct({
  generatedAt: Schema.String,
  kpis: Schema.Struct({
    shipping: Schema.optional(Shipping),
    notes: Schema.Array(Schema.NonEmptyString),
    tiles: Schema.Array(KpiTile),
  }),
  usage: Schema.Struct({
    report: Schema.optional(BurnReport),
    burn: BurnByWindow,
    cards: Schema.Array(UsageCard),
  }),
});

export type FactoryFeedValue = typeof FactoryFeed.Type;

export class FeedError extends Schema.TaggedError<
  FeedError,
  { readonly brand: unique symbol }
>()("FeedError", {
  cause: Schema.Unknown,
  path: Schema.String,
}) {}

export const decodeFeed = Effect.fn("content.decodeFeed")(function* decodeFeed(
  path: string,
  raw: string
) {
  return yield* Schema.decodeEffect(Schema.fromJsonString(FactoryFeed))(
    raw
  ).pipe(Effect.mapError((cause) => new FeedError({ cause, path })));
});
