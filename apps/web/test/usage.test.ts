import { describe, expect, it } from "@effect/vitest";
import { DateTime, Effect, Exit, Option } from "effect";
import {
  expect as expectElement,
  given,
  role,
  scene,
  Subscription,
  text,
} from "foldkit/scene";

import { Message } from "../src/client/app/message.js";
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
        loadText: "41 chats · 3 runners",
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
        loadText: "2 runners",
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
        loadText: "idle",
        mode: "none",
        name: "Idle Plan",
        note: null,
        paceDelta: null,
        plan: "vercel",
        primaryWindow: "week",
        resetsText: null,
        reviewer: { known: true, show: false, tip: "" },
        runnersLive: true,
        runnersText: "0 runners",
        skip: null,
        tone: "plain",
        usedPct: null,
        windows: [],
      },
    ],
  },
};

describe("usage page", () => {
  it.effect(
    "shows one card per plan with fixed 1h burn, load, live runners, and no window picker",
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
          expectElement(
            role("link", { name: "Open OpenCode usage page" })
          ).toExist(),
          expectElement(text("$6.20 left")).toExist(),
          expectElement(text("estimate · as of 1h ago")).toExist(),
          expectElement(text("2 DeepSeek 4.1 Flash medium")).toExist(),
          expectElement(text("41 chats · 3 runners")).toExist(),
          expectElement(text("2 runners")).toExist(),
          expectElement(text("idle")).toExist(),
          expectElement(text("inactive")).not.toExist(),
          expectElement(text(/^Updated /u)).not.toExist(),
          expectElement(text("Weekly 67%")).toExist(),
          expectElement(text("29 / day · 87 / week")).not.toExist()
        );
      })
  );

  it.effect("links each card heading to that plan's own usage page", () =>
    Effect.gen(function* linkHeadings() {
      const linked = [
        ["claude", "Claude Code", "https://claude.ai/new#settings/usage"],
        ["codex", "Codex", "https://chatgpt.com/settings/usage?tab=overview"],
        [
          "vercel",
          "Vercel Token Pass",
          "https://vercel.com/hypertaskai/~/ai-gateway/token-pass",
        ],
        [
          "opencode",
          "OpenCode",
          "https://opencode.ai/console/wrk_01KF5VZPS53BNVE2RR9QAYJSB4/go",
        ],
        ["antigravity", "Antigravity", "https://antigravity.google/"],
        ["commandcode", "CommandCode", "https://commandcode.ai/"],
        ["openrouter", "OpenRouter", "https://openrouter.ai/settings/credits"],
      ] as const;

      const feed = yield* decodeFeed(
        fixturePath,
        JSON.stringify({
          ...usageFeed,
          usage: {
            ...usageFeed.usage,
            cards: linked.map(([plan, name]) => ({
              ...usageFeed.usage.cards[0],
              name,
              plan,
            })),
          },
        })
      );

      const head = (name: string) => role("heading", { name });
      const link = (name: string) =>
        role("link", { name: `Open ${name} usage page` });

      scene(
        { update, view },
        given(
          initialModel(
            { items: [], route: SiteRoute.Usage() },
            Option.some(feed)
          )
        ),
        expectElement(head("Claude Code")).toHaveText("Claude Code ↗"),
        expectElement(head("Codex")).toHaveText("Codex ↗"),
        expectElement(head("Vercel Token Pass")).toHaveText(
          "Vercel Token Pass ↗"
        ),
        expectElement(head("OpenCode")).toHaveText("OpenCode ↗"),
        expectElement(head("Antigravity")).toHaveText("Antigravity ↗"),
        expectElement(head("CommandCode")).toHaveText("CommandCode ↗"),
        expectElement(head("OpenRouter")).toHaveText("OpenRouter ↗"),
        expectElement(link("Claude Code")).toHaveAttr(
          "href",
          "https://claude.ai/new#settings/usage"
        ),
        expectElement(link("Claude Code")).toHaveAttr("target", "_blank"),
        expectElement(link("Claude Code")).toHaveAttr("rel", "noopener"),
        expectElement(link("Codex")).toHaveAttr(
          "href",
          "https://chatgpt.com/settings/usage?tab=overview"
        ),
        expectElement(link("Vercel Token Pass")).toHaveAttr(
          "href",
          "https://vercel.com/hypertaskai/~/ai-gateway/token-pass"
        ),
        expectElement(link("OpenCode")).toHaveAttr(
          "href",
          "https://opencode.ai/console/wrk_01KF5VZPS53BNVE2RR9QAYJSB4/go"
        ),
        expectElement(link("Antigravity")).toHaveAttr(
          "href",
          "https://antigravity.google/"
        ),
        expectElement(link("CommandCode")).toHaveAttr(
          "href",
          "https://commandcode.ai/"
        ),
        expectElement(link("OpenRouter")).toHaveAttr(
          "href",
          "https://openrouter.ai/settings/credits"
        )
      );
    })
  );

  it.effect("shows one data age line and updates it when the clock ticks", () =>
    Effect.gen(function* showAge() {
      const feed = yield* decodeFeed(fixturePath, JSON.stringify(usageFeed));

      const generated = DateTime.toEpochMillis(
        DateTime.makeUnsafe(usageFeed.generatedAt)
      );

      const at = (minutes: number) => Option.some(generated + minutes * 60_000);

      scene(
        { update, view },
        given({
          ...initialModel(
            { items: [], route: SiteRoute.Usage() },
            Option.some(feed)
          ),
          nowMs: at(5),
        }),
        expectElement(text(/^Updated \d{2}:\d{2} \(5 min ago\)$/u)).toExist(),
        Subscription.emit(
          Message.TickedClock({ nowMs: generated + 35 * 60_000 })
        ),
        expectElement(text(/^Updated \d{2}:\d{2} \(35 min ago\)$/u)).toExist()
      );
    })
  );

  it.effect("rejects a card for a retired plan", () =>
    Effect.gen(function* rejectRetiredPlan() {
      const retired = {
        ...usageFeed,
        usage: {
          ...usageFeed.usage,
          cards: usageFeed.usage.cards.map((card, index) =>
            index === 0 ? { ...card, plan: "grok" } : card
          ),
        },
      };

      const attempt = yield* Effect.exit(
        decodeFeed(fixturePath, JSON.stringify(retired))
      );

      expect(Exit.isFailure(attempt)).toBe(true);
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
