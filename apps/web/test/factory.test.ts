import { describe, expect, it } from "@effect/vitest";
import { Effect } from "effect";
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

const productTile = {
  display: "29",
  id: "product_tickets",
  label: "Product tickets done",
  state: "ok",
  sub: null,
  target: "≥ 1",
};

const oneHourBig = [
  productTile,
  {
    display: "0.73",
    id: "per_runner_hour",
    label: "Per runner-hour",
    state: "ok",
    sub: "39.7 h",
    target: "≥ 0.37",
  },
  {
    display: "£0.44",
    id: "gbp_per_product",
    label: "£ per Product ticket",
    state: "ok",
    sub: null,
    target: "≤ £0.50",
  },
  {
    display: "11.2",
    id: "runs_per_product",
    label: "Runs per Product ticket",
    state: "bad",
    sub: null,
    target: "≤ 1",
  },
];

const windowOf = (display: string) => ({
  big: oneHourBig.map((tile, index) =>
    index === 2 ? { ...tile, display } : tile
  ),
  from: 1_794_695_497,
  more: [],
  note: null,
  to: 1_794_699_097,
});

const fixtureFeed = {
  generatedAt: "2026-11-15T00:41:07Z",
  kpis: {
    violations: {
      hourly: [{ runs: 7, t: 1_794_686_400, violations: 1 }],
      top: 3,
    },
    windows: {
      "1h": windowOf("£0.44"),
      "7d": windowOf("£12.74 / 0"),
    },
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
    ],
  },
};

describe("factory page", () => {
  it.effect("shows the fixture plan card and KPI tile", () =>
    Effect.gen(function* () {
      const feed = yield* decodeFeed(
        fixturePath,
        JSON.stringify(fixtureFeed)
      );
      const route = SiteRoute.Factory();

      scene(
        { update, view },
        given(initialModel({ route }, [], feed)),
        expectElement(text("Fixture Plan")).toExist(),
        expectElement(text("£0.44")).toExist(),
        expectElement(text("Numbers from 2026-11-15 00:41 UTC")).toExist(),
        click(role("button", { name: "7d" })),
        expectElement(text("£12.74 / 0")).toExist()
      );
    })
  );

  it.effect("rejects a feed with an unknown state", () =>
    Effect.gen(function* () {
      const broken = {
        ...fixtureFeed,
        kpis: {
          ...fixtureFeed.kpis,
          windows: {
            "1h": {
              ...windowOf("£0.44"),
              big: [{ ...productTile, state: "great" }],
            },
          },
        },
      };

      const failure = yield* Effect.flip(
        decodeFeed(fixturePath, JSON.stringify(broken))
      );

      expect(failure).toBeInstanceOf(FeedError);
    })
  );

  it.effect("shows one line when the feed is missing", () =>
    Effect.gen(function* () {
      const route = SiteRoute.Factory();

      scene(
        { update, view },
        given(initialModel({ route }, [], null)),
        expectElement(text("No factory numbers yet.")).toExist()
      );
    })
  );
});
