import { describe, it } from "@effect/vitest";
import { Effect, Option } from "effect";
import {
  expect as expectElement,
  given,
  role,
  scene,
  text,
} from "foldkit/scene";

import { initialModel } from "../src/client/app/model.js";
import { update } from "../src/client/app/update.js";
import { decodeFeed } from "../src/content/feed.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const fixturePath = "content/feed/factory.json";

const usageFeed = {
  generatedAt: "2026-11-15T00:41:07Z",
  kpis: {
    notes: [],
    tiles: [
      {
        details: ["Board 15 / Product Lead, 1d: 29"],
        display: "29 / day · 87 / week",
        id: "delivered",
        label: "Tickets delivered",
        source: "Hypertask boards 15, 2060, 11514 · sectionChangedAt",
        state: null,
        window: "Rolling 24h and 7d",
      },
    ],
  },
  usage: {
    burn: {
      "1h": {
        claude: { gbp: 0, pricedPts: 0, pts: 2, todayUsd: null },
      },
    },
    cards: [
      {
        creditAsOf: null,
        creditReadAt: null,
        creditSubLabel: null,
        creditUsd: null,
        mode: "percent",
        name: "Fixture Plan",
        note: null,
        paceDelta: 13.2,
        plan: "claude",
        primaryWindow: "week",
        resetsText: "Sun 18:00",
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "0 runners",
        skip: null,
        tone: "warm",
        usedPct: 67,
        windows: [{ label: "Weekly", usedPct: 67 }],
      },
      {
        creditAsOf: " · as of 1h ago",
        creditReadAt: "2026-11-14T23:41:00Z",
        creditSubLabel: "estimate",
        creditUsd: 6.2,
        mode: "credit",
        name: "OpenCode",
        note: "Anchored credit estimate (lane-credits.json)",
        paceDelta: null,
        plan: "opencode",
        primaryWindow: "month",
        resetsText: null,
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "2 DeepSeek 4.1 Flash medium",
        skip: null,
        tone: "plain",
        usedPct: null,
        windows: [],
      },
      {
        creditAsOf: null,
        creditReadAt: null,
        creditSubLabel: null,
        creditUsd: null,
        mode: "none",
        name: "Retired Plan",
        note: "Quota used up at 2026-11-24T00:46:05Z",
        paceDelta: null,
        plan: "cursor",
        primaryWindow: "week",
        resetsText: null,
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "0 runners",
        skip: {
          reason: "manual skip (lane-limits)",
          untilText: "2036-11-20 20:22 UTC",
        },
        tone: "plain",
        usedPct: null,
        windows: [],
      },
    ],
  },
};

describe("usage page", () => {
  it.effect(
    "shows one card per plan with fixed 1h burn, live runners, and no window picker",
    () =>
      Effect.gen(function* showCards() {
        const feed = yield* decodeFeed(fixturePath, JSON.stringify(usageFeed));

        scene(
          { update, view },
          given(
            initialModel(
              { items: [], route: SiteRoute.Usage() },
              Option.some(feed)
            )
          ),
          expectElement(role("heading", { name: "Usage" })).toExist(),
          expectElement(role("group", { name: "Usage window" })).not.toExist(),
          expectElement(
            text("The buttons change the burn window only.", { exact: false })
          ).not.toExist(),
          expectElement(text("Fixture Plan")).toExist(),
          expectElement(text("67%")).toExist(),
          expectElement(text("+13.2 vs pace · over pace")).toExist(),
          expectElement(text("resets Sun 18:00")).toExist(),
          expectElement(text("+2% · £0.00 in 1h on runners")).toExist(),
          expectElement(text("OpenCode")).toExist(),
          expectElement(text("$6.20 left")).toExist(),
          expectElement(text("estimate · as of 1h ago")).toExist(),
          expectElement(text("2 DeepSeek 4.1 Flash medium")).toExist(),
          expectElement(text("Weekly 67%")).toExist(),
          expectElement(text("29 / day · 87 / week")).not.toExist()
        );
      })
  );

  it.effect(
    "shows a skipped plan with the skip's end date and its reason",
    () =>
      Effect.gen(function* showSkip() {
        const feed = yield* decodeFeed(fixturePath, JSON.stringify(usageFeed));

        scene(
          { update, view },
          given(
            initialModel(
              { items: [], route: SiteRoute.Usage() },
              Option.some(feed)
            )
          ),
          expectElement(text("Retired Plan")).toExist(),
          expectElement(
            text(
              "Skipped until 2036-11-20 20:22 UTC (manual skip (lane-limits))"
            )
          ).toExist(),
          expectElement(
            text("Quota used up at 2026-11-24T00:46:05Z")
          ).toExist(),
          expectElement(text("no reading")).toExist()
        );
      })
  );

  it.effect("says so when the feed is missing", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(
          initialModel({ items: [], route: SiteRoute.Usage() }, Option.none())
        ),
        expectElement(text("No usage numbers yet.")).toExist(),
        expectElement(role("group", { name: "Usage window" })).not.toExist()
      );
    })
  );
});
