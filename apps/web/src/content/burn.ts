import { Schema } from "effect";

const Count = Schema.Finite.check(Schema.isGreaterThanOrEqualTo(0));

export const BurnRange = Schema.Literals(["24h", "7d", "week", "custom"]);

export const BurnRow = Schema.Struct({
  account: Schema.NonEmptyString,
  attribution: Schema.Literals(["recorded", "inferred", "unknown"]),
  cacheRead: Count,
  cacheWrite: Count,
  chat: Schema.NonEmptyString,
  chatId: Schema.NonEmptyString,
  hour: Schema.String,
  input: Count,
  listCostUsd: Schema.NullOr(Count),
  model: Schema.NonEmptyString,
  output: Count,
  plan: Schema.NonEmptyString,
  requests: Count,
  ticket: Schema.NonEmptyString,
  tokensKnown: Schema.Boolean,
});

export const BurnReport = Schema.Struct({
  generatedAt: Schema.String,
  keyUsage: Schema.optional(
    Schema.Array(
      Schema.Struct({
        billedCostUsd: Schema.NullOr(Count),
        periodEndsAt: Schema.String,
        row: BurnRow,
      })
    )
  ),
  notes: Schema.Array(Schema.NonEmptyString),
  plans: Schema.Array(
    Schema.Struct({
      plan: Schema.NonEmptyString,
      weekResetsAt: Schema.NullOr(Schema.String),
      weekStartsAt: Schema.NullOr(Schema.String),
    })
  ),
  rows: Schema.Array(BurnRow),
});

export type BurnReportValue = typeof BurnReport.Type;

export type BurnRowValue = typeof BurnRow.Type;

export const BurnSelection = Schema.Struct({
  chatId: Schema.String,
  end: Schema.String,
  plan: Schema.String,
  range: BurnRange,
  start: Schema.String,
});

export type BurnSelectionValue = typeof BurnSelection.Type;

export const selectedBurnRows = (
  report: BurnReportValue,
  selection: BurnSelectionValue,
  bucketHours = 1
): readonly BurnRowValue[] => {
  const bucketMs = bucketHours * 3_600_000;
  const end = Date.parse(report.generatedAt);
  const customStart = Date.parse(`${selection.start}T00:00:00Z`);
  const customEnd = Date.parse(`${selection.end}T00:00:00Z`) + 86_400_000;

  return report.rows.filter((row) => {
    const hour = Date.parse(row.hour);
    const plan = report.plans.find((candidate) => candidate.plan === row.plan);

    if (
      selection.plan !== "" &&
      selection.plan !== `${row.plan} / ${row.account}`
    ) {
      return false;
    }

    if (selection.range === "custom") {
      return hour >= customStart && hour < customEnd;
    }

    if (selection.range === "week") {
      return (
        plan?.weekStartsAt !== null &&
        plan?.weekStartsAt !== undefined &&
        hour >=
          Math.floor(Date.parse(plan.weekStartsAt) / bucketMs) * bucketMs &&
        hour <= end
      );
    }

    const start = end - (selection.range === "24h" ? 24 : 168) * 3_600_000;

    return hour >= Math.floor(start / bucketMs) * bucketMs && hour <= end;
  });
};

export const rankBurn = (
  rows: readonly BurnRowValue[],
  level: "plan" | "chat" | "ticket"
) => {
  const groups = new Map<
    string,
    { key: string; name: string; rows: BurnRowValue[] }
  >();

  for (const row of rows) {
    const keys = {
      plan: `${row.plan} / ${row.account}`,
      chat: row.chatId,
      ticket: `${row.ticket} (${row.attribution})`,
    };

    const key = keys[level];

    const group = groups.get(key) ?? {
      key,
      name: level === "chat" ? row.chat : key,
      rows: [],
    };

    group.rows.push(row);
    groups.set(key, group);
  }

  return [...groups.values()]
    .map((group) => {
      const listCostUsd = group.rows.some((row) => row.listCostUsd !== null)
        ? group.rows.reduce((sum, row) => sum + (row.listCostUsd ?? 0), 0)
        : null;

      const unpricedRequests = group.rows.reduce(
        (sum, row) => sum + (row.listCostUsd === null ? row.requests : 0),
        0
      );

      return {
        ...group,
        cacheRead: group.rows.reduce((sum, row) => sum + row.cacheRead, 0),
        cacheWrite: group.rows.reduce((sum, row) => sum + row.cacheWrite, 0),
        input: group.rows.reduce((sum, row) => sum + row.input, 0),
        output: group.rows.reduce((sum, row) => sum + row.output, 0),
        requests: group.rows.reduce((sum, row) => sum + row.requests, 0),
        tokensKnown: group.rows.every((row) => row.tokensKnown),
        listCostUsd,
        unpricedRequests,
        weight: listCostUsd ?? 0,
      };
    })
    .toSorted(
      (left, right) =>
        right.weight - left.weight ||
        right.requests - left.requests ||
        left.key.localeCompare(right.key)
    );
};
