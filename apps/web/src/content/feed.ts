import { Effect, Schema } from "effect";

export const PlanKey = Schema.Literals([
  "claude",
  "codex",
  "grok",
  "opencode",
  "vercel",
]);

export type PlanKey = typeof PlanKey.Type;

export const WindowKey = Schema.Literals([
  "1h",
  "3h",
  "6h",
  "12h",
  "24h",
  "7d",
  "30d",
]);

export type WindowKey = typeof WindowKey.Type;

export const windowKeys: ReadonlyArray<WindowKey> = [
  "1h",
  "3h",
  "6h",
  "12h",
  "24h",
  "7d",
  "30d",
];

const PrimaryWindowKey = Schema.Literals(["week", "month"]);

const UsageMode = Schema.Literals(["percent", "credit", "none"]);

const Tone = Schema.Literals(["plain", "warm", "hot"]);

const CreditSubLabel = Schema.Literals(["credit", "month full"]);

const KpiState = Schema.Literals(["ok", "bad"]);

const BigTileId = Schema.Literals([
  "product_tickets",
  "per_runner_hour",
  "gbp_per_product",
  "runs_per_product",
  "violations",
  "linked_runs",
]);

const MoreTileId = Schema.Literals([
  "upkeep_tickets",
  "unattributed_runs",
  "runs_per_upkeep_ticket",
  "product_runs",
  "upkeep_runs",
  "prs_merged",
  "reviews",
]);

const WindowReading = Schema.Struct({
  label: Schema.NonEmptyString,
  usedPct: Schema.NullOr(Schema.Number),
});

const Reviewer = Schema.Struct({
  known: Schema.Boolean,
  show: Schema.Boolean,
  tip: Schema.String,
});

const UsageCard = Schema.Struct({
  creditAsOf: Schema.NullOr(Schema.String),
  creditReadAt: Schema.NullOr(Schema.String),
  creditSubLabel: Schema.NullOr(CreditSubLabel),
  creditUsd: Schema.NullOr(Schema.Number),
  mode: UsageMode,
  name: Schema.NonEmptyString,
  paceDelta: Schema.NullOr(Schema.Number),
  plan: PlanKey,
  primaryWindow: PrimaryWindowKey,
  resetsText: Schema.NullOr(Schema.String),
  reviewer: Reviewer,
  runnersLive: Schema.Boolean,
  runnersText: Schema.String,
  tone: Tone,
  usedPct: Schema.NullOr(Schema.Number),
  windows: Schema.Array(WindowReading),
});

export type UsageCard = typeof UsageCard.Type;

export type WindowReading = typeof WindowReading.Type;

const BurnCell = Schema.Struct({
  gbp: Schema.NullOr(Schema.Number),
  pricedPts: Schema.NullOr(Schema.Number),
  pts: Schema.NullOr(Schema.Number),
  todayUsd: Schema.NullOr(Schema.Number),
});

export type BurnCell = typeof BurnCell.Type;

const BurnByPlan = Schema.Struct({
  claude: Schema.optional(BurnCell),
  codex: Schema.optional(BurnCell),
  grok: Schema.optional(BurnCell),
  opencode: Schema.optional(BurnCell),
  vercel: Schema.optional(BurnCell),
});

const BurnByWindow = Schema.Struct({
  "1h": Schema.optional(BurnByPlan),
  "3h": Schema.optional(BurnByPlan),
  "6h": Schema.optional(BurnByPlan),
  "12h": Schema.optional(BurnByPlan),
  "24h": Schema.optional(BurnByPlan),
  "7d": Schema.optional(BurnByPlan),
  "30d": Schema.optional(BurnByPlan),
});

export type BurnByWindow = typeof BurnByWindow.Type;

const tileFields = {
  display: Schema.NonEmptyString,
  label: Schema.NonEmptyString,
  state: Schema.NullOr(KpiState),
  sub: Schema.NullOr(Schema.String),
  target: Schema.NullOr(Schema.String),
};

const BigTile = Schema.Struct({ id: BigTileId, ...tileFields });

export type BigTile = typeof BigTile.Type;

const MoreTile = Schema.Struct({ id: MoreTileId, ...tileFields });

export type MoreTile = typeof MoreTile.Type;

export type KpiState = typeof KpiState.Type;

const KpiWindow = Schema.Struct({
  big: Schema.Array(BigTile),
  from: Schema.Number,
  more: Schema.Array(MoreTile),
  note: Schema.NullOr(Schema.String),
  to: Schema.Number,
});

export type KpiWindow = typeof KpiWindow.Type;

const KpiWindows = Schema.Struct({
  "1h": Schema.optional(KpiWindow),
  "3h": Schema.optional(KpiWindow),
  "6h": Schema.optional(KpiWindow),
  "12h": Schema.optional(KpiWindow),
  "24h": Schema.optional(KpiWindow),
  "7d": Schema.optional(KpiWindow),
  "30d": Schema.optional(KpiWindow),
});

export type KpiWindows = typeof KpiWindows.Type;

const HourBucket = Schema.Struct({
  runs: Schema.Number,
  t: Schema.Number,
  violations: Schema.Number,
});

export type HourBucket = typeof HourBucket.Type;

const Violations = Schema.Struct({
  hourly: Schema.Array(HourBucket),
  top: Schema.Number,
});

export type Violations = typeof Violations.Type;

export const FactoryFeed = Schema.Struct({
  generatedAt: Schema.String,
  kpis: Schema.Struct({
    violations: Violations,
    windows: KpiWindows,
  }),
  usage: Schema.Struct({
    burn: BurnByWindow,
    cards: Schema.Array(UsageCard),
  }),
});

export type FactoryFeed = typeof FactoryFeed.Type;

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
  return yield* Schema.decodeEffect(Schema.fromJsonString(FactoryFeed))(raw).pipe(
    Effect.mapError((cause) => new FeedError({ cause, path }))
  );
});
