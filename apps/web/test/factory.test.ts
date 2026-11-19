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
import type { ShippingCellValue } from "../src/content/feed.js";
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
      {
        details: ["3 PRs merged in 7d. Open-to-merge includes draft time."],
        display: "1 / day · 3 / week · 20.0 min median",
        id: "merges",
        label: "PR throughput and merge time",
        source: "GitHub fleet PRs · createdAt and mergedAt",
        state: null,
        window: "Rolling 24h and 7d; merge-time cohort is 7d",
      },
      {
        details: ["1/2 live chats have matching named agent tokens."],
        display: "50%",
        id: "identity",
        label: "Chat identity sync",
        source: "Fleet hosted_chats · solo-wake identity-gap rule",
        state: "bad",
        window: "Live Multibot chats at export time",
      },
      {
        details: [
          "No matching Production receipts; latency unavailable, not zero.",
        ],
        display:
          "– to live · 0% confirmed infra · 0% confirmed code · 50% unclassified",
        id: "ci",
        label: "CI health",
        source: "GitHub Actions annotations and Production deployment statuses",
        state: null,
        window: "Runs created and PRs merged in rolling 24h",
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

const measured = (value: number, display: string): ShippingCellValue => ({
  kind: "measured",
  value,
  display,
  barPct: 50,
  source: "Seeded GitHub mergedAt and advisor daily source",
  window: "2026-11-14 00:00 UTC to 2026-11-15 00:00 UTC",
});

const missing: ShippingCellValue = {
  kind: "missing",
  reason: "No consecutive quota readings within 6h on this UTC date.",
  source: "Advisor daily_burn.readings · claude weekly quota",
  window: "2026-11-14 00:00 UTC to 2026-11-15 00:00 UTC",
};

const shippingFixture = {
  ...fixtureFeed,
  kpis: {
    ...fixtureFeed.kpis,
    shipping: {
      notes: [
        "Quota points are not tokens; £ is the attributed priced subset.",
      ],
      omissions: [
        {
          plan: "opencode",
          reason: "pacing sampler retired on 2026-11-15.",
        },
      ],
      days: [
        {
          date: "2026-11-13",
          merges: measured(1, "1 PRs"),
          burn: [
            { plan: "claude", reading: measured(1, "1 pts") },
            { plan: "codex", reading: missing },
            { plan: "grok", reading: missing },
            { plan: "opencode", reading: missing },
          ],
          cost: missing,
          perPr: missing,
        },
        {
          date: "2026-11-14",
          merges: measured(2, "2 PRs"),
          burn: [
            { plan: "claude", reading: missing },
            { plan: "codex", reading: measured(6, "6 pts") },
            { plan: "grok", reading: measured(0, "0 pts") },
            { plan: "opencode", reading: missing },
          ],
          cost: measured(12, "£12.00"),
          perPr: measured(6, "£6.00"),
        },
      ],
    },
  },
};

describe("factory page", () => {
  it.effect(
    "shows daily bars, exact costs and expandable provenance independently of the usage picker",
    () =>
      Effect.gen(function* showShipping() {
        const feed = yield* decodeFeed(
          fixturePath,
          JSON.stringify(shippingFixture)
        );

        scene(
          { update, view },
          given(
            initialModel(
              { items: [], route: SiteRoute.Factory() },
              Option.some(feed)
            )
          ),
          expectElement(
            role("region", { name: "Daily shipping and burn chart" })
          ).toExist(),
          expectElement(
            role("columnheader", { name: "Attributed £/PR" })
          ).toExist(),
          expectElement(text("2 PRs")).toExist(),
          expectElement(text("6 pts")).toExist(),
          expectElement(text("0 pts")).toExist(),
          expectElement(role("columnheader", { name: "Claude pts" })).toExist(),
          expectElement(role("columnheader", { name: "Grok pts" })).toExist(),
          expectElement(
            role("columnheader", { name: "OpenCode pts" })
          ).not.toExist(),
          expectElement(
            text("OpenCode omitted: pacing sampler retired on 2026-11-15.")
          ).toExist(),
          expectElement(
            text("Grok and OpenCode's pacing sampler retired on 2026-11-15.")
          ).not.toExist(),
          expectElement(text("£12.00")).toExist(),
          expectElement(text("£6.00")).toExist(),
          expectElement(text(missing.reason)).toExist(),
          expectElement(text(missing.window)).toExist(),
          expectElement(text(missing.source)).toExist(),
          click(role("button", { name: "30d" })),
          expectElement(text("£6.00")).toExist()
        );
      })
  );

  it.effect("does not blame a missing plan on another plan's sampler", () =>
    Effect.gen(function* keepReasonsApart() {
      const separated = {
        ...shippingFixture,
        kpis: {
          ...shippingFixture.kpis,
          shipping: {
            ...shippingFixture.kpis.shipping,
            omissions: [
              {
                plan: "claude",
                reason: "no quota readings on any of the 30 UTC dates.",
              },
              {
                plan: "grok",
                reason: "pacing sampler retired on 2026-11-15.",
              },
              {
                plan: "opencode",
                reason: "pacing sampler retired on 2026-11-15.",
              },
            ],
            days: shippingFixture.kpis.shipping.days.map((day) => ({
              ...day,
              burn: day.burn.map((item) =>
                item.plan === "claude" || item.plan === "grok"
                  ? { ...item, reading: missing }
                  : item
              ),
            })),
          },
        },
      };

      const feed = yield* decodeFeed(fixturePath, JSON.stringify(separated));

      scene(
        { update, view },
        given(
          initialModel(
            { items: [], route: SiteRoute.Factory() },
            Option.some(feed)
          )
        ),
        expectElement(role("columnheader", { name: "Codex pts" })).toExist(),
        expectElement(
          role("columnheader", { name: "Claude pts" })
        ).not.toExist(),
        expectElement(
          text(
            "Claude omitted: no quota readings on any of the 30 UTC dates. Grok, OpenCode omitted: pacing sampler retired on 2026-11-15."
          )
        ).toExist(),
        expectElement(
          text("Grok and OpenCode's pacing sampler retired on 2026-11-15.")
        ).not.toExist()
      );
    })
  );

  it.effect(
    "rejects daily values without provenance or with negative burn",
    () =>
      Effect.gen(function* rejectInvalidShipping() {
        for (const cell of [
          { ...measured(2, "2 PRs"), source: "" },
          { ...measured(2, "2 PRs"), value: -1 },
        ]) {
          const broken = {
            ...shippingFixture,
            kpis: {
              ...shippingFixture.kpis,
              shipping: {
                ...shippingFixture.kpis.shipping,
                days: shippingFixture.kpis.shipping.days.map((day) => ({
                  ...day,
                  merges: cell,
                })),
              },
            },
          };

          const failure = yield* Effect.flip(
            decodeFeed(fixturePath, JSON.stringify(broken))
          );

          expect(failure).toBeInstanceOf(FeedError);
        }
      })
  );
  it.effect("shows the fixture plan card and KPI tile", () =>
    Effect.gen(function* showFixturePlan() {
      const feed = yield* decodeFeed(fixturePath, JSON.stringify(fixtureFeed));
      const route = SiteRoute.Factory();

      scene(
        { update, view },
        given(initialModel({ items: [], route }, Option.some(feed))),
        expectElement(text("Fixture Plan")).toExist(),
        expectElement(
          text(
            "Daily shipping data unavailable. This feed predates the daily collector."
          )
        ).toExist(),
        expectElement(text("as of 28h ago")).toExist(),
        expectElement(text("29 / day · 87 / week")).toExist(),
        expectElement(
          text("Hypertask boards 15, 2060, 11514 · sectionChangedAt")
        ).toExist(),
        expectElement(text("Rolling 24h and 7d")).toExist(),
        expectElement(text("75%")).toExist(),
        expectElement(text("1/2 over pace")).toExist(),
        expectElement(text("1 / day · 3 / week · 20.0 min median")).toExist(),
        expectElement(text("Chat identity sync")).toExist(),
        expectElement(text("50%")).toExist(),
        expectElement(
          text("Runs created and PRs merged in rolling 24h")
        ).toExist(),
        expectElement(
          text(
            "– to live · 0% confirmed infra · 0% confirmed code · 50% unclassified"
          )
        ).toExist(),
        expectElement(
          text(
            "No matching Production receipts; latency unavailable, not zero."
          )
        ).toExist(),
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
        given(initialModel({ items: [], route }, Option.none())),
        expectElement(text("No factory numbers yet.")).toExist()
      );
    })
  );
});
