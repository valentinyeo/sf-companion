import { describe, expect, it } from "@effect/vitest";
import { Effect, Option, Schema } from "effect";
import {
  click,
  expect as expectElement,
  given,
  role,
  scene,
  text,
} from "foldkit/scene";

import fixture from "../../../.claude/skills/verify-sf-companion/fixture.json";
import { initialModel } from "../src/client/app/model.js";
import { update } from "../src/client/app/update.js";
import { BurnReport, rankBurn, selectedBurnRows } from "../src/content/burn.js";
import type { BurnRowValue, BurnSelectionValue } from "../src/content/burn.js";
import { decodeFeed } from "../src/content/feed.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const selection: BurnSelectionValue = {
  chatId: "",
  end: "",
  plan: "",
  range: "7d",
  start: "",
};

const decodeReport = Schema.decodeUnknownEffect(BurnReport);

const row: BurnRowValue = {
  account: "fixture account",
  attribution: "unknown",
  cacheRead: 0,
  cacheWrite: 0,
  chat: "Fixture chat",
  chatId: "fixture-chat",
  hour: "2026-11-24T00:00:00Z",
  input: 0,
  listCostUsd: null,
  model: "fixture-model",
  output: 0,
  plan: "claude",
  requests: 1,
  ticket: "unassigned",
  tokensKnown: true,
};

const Count = Schema.Int.check(
  Schema.isBetween({ minimum: 0, maximum: 1_000_000 })
);

describe("burn report", () => {
  it.effect(
    "filters a plan's chats and a chat's tickets through actual controls",
    () =>
      Effect.gen(function* filterBurnChat() {
        const feed = yield* decodeFeed("fixture", JSON.stringify(fixture));
        scene(
          { update, view },
          given(
            initialModel(
              { items: [], route: SiteRoute.Burn() },
              Option.some(feed)
            )
          ),
          expectElement(
            role("heading", { name: "Where did the tokens go?" })
          ).toExist(),
          click(
            role("button", {
              name: "Show chats for claude / claude fixture account",
            })
          ),
          click(role("button", { name: "Show tickets for Burn heavy chat" })),
          expectElement(
            role("rowheader", { name: "VSTA-329 (recorded)" })
          ).toExist(),
          expectElement(
            role("rowheader", { name: "VSTA-328 (inferred)" })
          ).toExist(),
          expectElement(
            role("rowheader", { name: "MUBO-45 (inferred)" })
          ).not.toExist(),
          click(role("button", { name: "All chats" })),
          expectElement(
            role("rowheader", { name: "MUBO-45 (inferred)" })
          ).toExist(),
          expectElement(
            role("rowheader", { name: "HTPR-9 (inferred)" })
          ).not.toExist()
        );
      })
  );

  it.effect(
    "uses distinct rolling, plan-reset, and inclusive custom date ranges",
    () =>
      Effect.gen(function* compareBurnRanges() {
        const report = yield* decodeReport(fixture.usage.report);

        const chats = (range: BurnSelectionValue) =>
          selectedBurnRows(report, range).map((item) => item.chat);

        expect(chats({ ...selection, range: "24h" })).not.toContain(
          "Codex older chat"
        );
        expect(chats(selection)).toContain("Codex older chat");
        expect(chats({ ...selection, range: "week" })).not.toContain(
          "Codex older chat"
        );
        expect(chats({ ...selection, range: "week" })).not.toContain(
          "Request-only chat"
        );
        expect(
          chats({
            ...selection,
            range: "custom",
            start: "2000-01-01",
            end: "2099-01-01",
          })
        ).toContain("Historical chat");
        expect(
          chats({
            ...selection,
            range: "custom",
            start: "2099-01-01",
            end: "2000-01-01",
          })
        ).toEqual([]);
        const first = report.rows.at(0);

        if (first !== undefined) {
          const date = first.hour.slice(0, 10);
          expect(
            chats({ ...selection, range: "custom", start: date, end: date })
          ).toContain(first.chat);
        }
      })
  );

  it.effect(
    "shows a missing report rather than an empty measured ranking",
    () =>
      Effect.sync(() => {
        scene(
          { update, view },
          given(
            initialModel({ items: [], route: SiteRoute.Burn() }, Option.none())
          ),
          expectElement(
            text("No burn report yet. The hourly feed will populate it.")
          ).toExist(),
          expectElement(role("table")).not.toExist()
        );
      })
  );

  it.effect("keeps request-only usage and unpriced cost unknown", () =>
    Effect.gen(function* unknownBurnCosts() {
      const report = yield* decodeReport(fixture.usage.report);

      const groups = rankBurn(
        report.rows.filter((item) => item.plan === "antigravity"),
        "plan"
      );

      expect(groups.at(0)?.tokensKnown).toBe(false);
      expect(groups.at(0)?.listCostUsd).toBeNull();
      expect(groups.at(0)?.requests).toBe(3);
      expect(
        rankBurn([{ ...row, listCostUsd: 1 }, row], "plan").at(0)?.listCostUsd
      ).toBeNull();
    })
  );

  it.effect(
    "ranks cache-heavy usage by price rather than raw or fixed-weight tokens",
    () =>
      Effect.sync(() => {
        const groups = rankBurn(
          [
            {
              ...row,
              chatId: "cache-heavy",
              cacheRead: 10_000_000,
              listCostUsd: 0.01,
            },
            { ...row, chatId: "expensive", input: 100, listCostUsd: 2 },
            { ...row, chatId: "unpriced", input: 100_000_000 },
          ],
          "chat"
        );

        expect(groups.map((group) => group.key)).toEqual([
          "expensive",
          "cache-heavy",
          "unpriced",
        ]);
        expect(groups.at(2)?.listCostUsd).toBeNull();
      })
  );

  it.effect(
    "shows daily provider charges separately from attributed chat usage",
    () =>
      Effect.gen(function* providerBurnTotals() {
        const feed = yield* decodeFeed("fixture", JSON.stringify(fixture));
        scene(
          { update, view },
          given(
            initialModel(
              { items: [], route: SiteRoute.Burn() },
              Option.some(feed)
            )
          ),
          expectElement(
            role("heading", { name: "Paid keys · provider totals" })
          ).toExist(),
          expectElement(
            role("rowheader", { name: "opencode / OpenCode fixture usage key" })
          ).toExist(),
          expectElement(role("cell", { name: "$0.12" })).toExist(),
          expectElement(
            role("button", {
              name: "Show tickets for Provider total, not a chat",
            })
          ).not.toExist(),
          expectElement(
            role("button", { name: "Show tickets for Pi fixture chat" })
          ).toExist()
        );
        const { report } = feed.usage;

        if (report !== undefined) {
          const providerRows = report.keyUsage?.map((item) => item.row) ?? [];

          const midDay = {
            ...report,
            generatedAt: "2026-11-15T12:00:00Z",
            rows: providerRows,
          };

          expect(
            selectedBurnRows(midDay, { ...selection, range: "24h" }, 24)
          ).toHaveLength(1);
          expect(
            selectedBurnRows(
              midDay,
              {
                ...selection,
                range: "custom",
                start: "2026-11-15",
                end: "2026-11-15",
              },
              24
            )
          ).toHaveLength(0);
        }
      })
  );

  it.prop(
    "conserves every token and request count across each ranking level",
    {
      inputs: Schema.Array(Count),
    },
    ({ inputs }) => {
      const rows = inputs.map((input, index) => ({
        ...row,
        account: `account-${index % 2}`,
        chatId: `chat-${index % 3}`,
        input,
        output: input * 2,
        cacheRead: input * 3,
        cacheWrite: input * 4,
      }));

      for (const level of ["plan", "chat", "ticket"] satisfies readonly (
        | "plan"
        | "chat"
        | "ticket"
      )[]) {
        const groups = rankBurn(rows, level);

        for (const field of [
          "input",
          "output",
          "cacheRead",
          "cacheWrite",
          "requests",
        ] satisfies readonly (
          | "input"
          | "output"
          | "cacheRead"
          | "cacheWrite"
          | "requests"
        )[]) {
          expect(groups.reduce((sum, group) => sum + group[field], 0)).toBe(
            rows.reduce((sum, item) => sum + item[field], 0)
          );
        }

        expect(groups.map((group) => group.weight)).toEqual(
          groups
            .map((group) => group.weight)
            .toSorted((left, right) => right - left)
        );
      }
    }
  );
});
