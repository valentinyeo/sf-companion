import { describe, expect, it } from "@effect/vitest";
import { Effect, Option } from "effect";
import {
  click,
  expect as expectElement,
  given,
  role,
  scene,
  text,
} from "foldkit/scene";

import { initialModel } from "../src/client/app/model.js";
import { update } from "../src/client/app/update.js";
import { decodeFeed, FeedError } from "../src/content/feed.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const fixturePath = "content/feed/factory.json";

const deliveredTile = {
  details: ["Board 15 / Product Lead, 1d: 29"],
  display: "29 / day · 87 / week",
  id: "delivered",
  label: "Tickets delivered",
  source: "Hypertask boards 15, 2060, 11514 · sectionChangedAt",
  state: null,
  window: "Rolling 24h and 7d",
};

const fixtureFeed = {
  generatedAt: "2026-11-15T00:41:07Z",
  kpis: {
    notes: [
      "Drain-loop health unavailable. No recent loop observations; not a measured zero.",
    ],
    tiles: [
      deliveredTile,
      {
        details: [
          "3/4 PRs passed their first verdict",
          "Merged without verdict: 25% (1/4)",
        ],
        display: "75%",
        id: "verifier",
        label: "Verifier first-pass rate",
        source: "GitHub fleet PR comments",
        state: null,
        window: "First verdicts and merges in rolling 7d",
      },
      {
        details: ["claude: 1.25× · over pace"],
        display: "1/2 over pace",
        id: "pace",
        label: "Plan usage pace",
        source: "token-ladder pools --json · pace_ratio",
        state: "bad",
        window: "Current plan windows at export time",
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
        paceDelta: 13.2,
        plan: "claude",
        primaryWindow: "week",
        resetsText: "Sun 18:00",
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "0 runners",
        tone: "warm",
        usedPct: 67,
        windows: [],
      },
      {
        creditAsOf: " · as of 28h ago",
        creditReadAt: "2026-11-14T00:41:00Z",
        creditSubLabel: "credit",
        creditUsd: 29.1,
        mode: "credit",
        name: "Credit Plan",
        paceDelta: null,
        plan: "opencode",
        primaryWindow: "week",
        resetsText: null,
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "0 runners",
        tone: "plain",
        usedPct: null,
        windows: [],
      },
    ],
  },
};

describe("factory page", () => {
  it.effect("shows the fixture plan card and KPI tile", () =>
    Effect.gen(function* showFixturePlan() {
      const feed = yield* decodeFeed(fixturePath, JSON.stringify(fixtureFeed));
      const route = SiteRoute.Factory();

      scene(
        { update, view },
        given(initialModel({ route }, [], Option.some(feed))),
        expectElement(text("Fixture Plan")).toExist(),
        expectElement(text("as of 28h ago")).toExist(),
        expectElement(text("29 / day · 87 / week")).toExist(),
        expectElement(
          text("Hypertask boards 15, 2060, 11514 · sectionChangedAt")
        ).toExist(),
        expectElement(text("Rolling 24h and 7d")).toExist(),
        expectElement(text("75%")).toExist(),
        expectElement(text("1/2 over pace")).toExist(),
        expectElement(text("Board 15 / Product Lead, 1d: 29")).toExist(),
        expectElement(text("Numbers from 2026-11-15 00:41 UTC")).toExist(),
        click(role("button", { name: "7d" })),
        expectElement(text("29 / day · 87 / week")).toExist()
      );
    })
  );

  it.effect("rejects a feed with an unknown state", () =>
    Effect.gen(function* rejectUnknownState() {
      const broken = {
        ...fixtureFeed,
        kpis: {
          ...fixtureFeed.kpis,
          tiles: [{ ...deliveredTile, state: "great" }],
        },
      };

      const failure = yield* Effect.flip(
        decodeFeed(fixturePath, JSON.stringify(broken))
      );

      expect(failure).toBeInstanceOf(FeedError);
    })
  );

  it.effect("shows one line when the feed is missing", () =>
    Effect.sync(() => {
      const route = SiteRoute.Factory();

      scene(
        { update, view },
        given(initialModel({ route }, [], Option.none())),
        expectElement(text("No factory numbers yet.")).toExist()
      );
    })
  );
});
