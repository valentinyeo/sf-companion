import { describe, expect, it } from "@effect/vitest";
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
import { decodeChats } from "../src/content/chats.js";
import type { ChatsSnapshotValue } from "../src/content/chats.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const snapshot: ChatsSnapshotValue = {
  chats: [
    {
      effort: "high",
      harness: "claude",
      model: "claude-opus-5-5",
      name: "HT Bugs",
      project: "hypertask",
      server: "Contabo",
    },
    {
      effort: "unknown",
      harness: "cursor",
      model: "unknown",
      name: "Design Lead",
      project: "vstack",
      server: "Contabo",
    },
  ],
  generatedAt: "2026-11-25T18:00:00Z",
  servers: [
    { collectedAt: "2026-11-25T18:00:00Z", server: "Contabo", state: "live" },
    { collectedAt: null, server: "inne Hetzner", state: "not-connected" },
  ],
};

const fakeToken = ["sk", "live", "9f2b7c41d8e5a6b3c0d1e2f3a4b5c6d7"].join("-");

const leaky = {
  chats: [
    {
      effort: "high",
      harness: "claude",
      model: "claude-opus-5-5",
      name: "Ops valentin@example.com",
      project: "vstack",
      server: "Contabo",
    },
    {
      effort: "medium",
      harness: "codex",
      model: "gpt-6.1-sol",
      name: `Deploy ${fakeToken}`,
      project: "hypertask",
      server: "Contabo",
    },
    {
      effort: "high",
      harness: "pi",
      model: "deepseek-v4.1-flash",
      name: "Runner box-42.corp.internal",
      project: "10.0.4.19",
      privateKey: "s3cretExtraValue",
      server: "Contabo",
      transcript: "/home/someone/.claude/projects/secret.jsonl",
    },
  ],
  generatedAt: "2026-11-25T18:00:00Z",
  servers: [
    { collectedAt: "2026-11-25T18:00:00Z", server: "Contabo", state: "live" },
  ],
};

const chatsPage = (value: ChatsSnapshotValue | null) =>
  initialModel(
    {
      chats: value,
      items: [],
      nowMs: Date.parse("2026-11-25T18:03:00Z"),
      route: SiteRoute.Chats({}),
    },
    Option.none()
  );

describe("chats snapshot", () => {
  it.effect(
    "publishes only the allowlisted fields and redacts what leaks into them",
    () =>
      Effect.gen(function* publishOnlyAllowlistedFields() {
        const decoded = yield* decodeChats("chats.json", JSON.stringify(leaky));
        const published = JSON.stringify(decoded);

        expect(decoded.chats).toHaveLength(3);
        expect(published).not.toContain("example.com");
        expect(published).not.toContain("valentin@");
        expect(published).not.toContain("9f2b7c41d8e5a6b3c0d1e2f3a4b5c6d7");
        expect(published).not.toContain("sk-live");
        expect(published).not.toContain("corp.internal");
        expect(published).not.toContain("10.0.4.19");
        expect(published).not.toContain("s3cretExtraValue");
        expect(published).not.toContain("/home/");
        expect(published).not.toContain("transcript");
        expect(decoded.chats[0]?.name).toBe("Ops [redacted]");
        expect(decoded.chats[1]?.name).toBe("Deploy [redacted]");
        expect(decoded.chats[2]?.name).toBe("Runner [redacted]");
        expect(decoded.chats[2]?.project).toBe("[redacted]");
        expect(Object.keys(decoded.chats[2] ?? {})).toStrictEqual([
          "effort",
          "harness",
          "model",
          "name",
          "project",
          "server",
        ]);
      })
  );

  it.effect("keeps a plain row exactly as collected", () =>
    Effect.gen(function* keepPlainRow() {
      const decoded = yield* decodeChats(
        "chats.json",
        JSON.stringify({ ...snapshot, chats: snapshot.chats.slice(0, 1) })
      );

      expect(decoded.chats[0]).toStrictEqual(snapshot.chats[0]);
    })
  );
});

describe("chats page", () => {
  it.effect("lists both servers with their counts, models and data age", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(chatsPage(snapshot)),
        expectElement(role("heading", { name: "Chats" })).toExist(),
        expectElement(role("heading", { name: "Contabo" })).toExist(),
        expectElement(role("heading", { name: "inne Hetzner" })).toExist(),
        expectElement(text("2 live chats", { exact: false })).toExist(),
        expectElement(text("not connected yet", { exact: false })).toExist(),
        expectElement(role("rowheader", { name: "HT Bugs" })).toExist(),
        expectElement(role("cell", { name: "Claude Code" })).toExist(),
        expectElement(role("cell", { name: "claude-opus-5-5" })).toExist(),
        expectElement(role("cell", { name: "high" })).toExist(),
        expectElement(role("cell", { name: "Cursor" })).toExist(),
        expectElement(role("cell", { name: /^unknown$/u })).toExist(),
        expectElement(text("(3 min ago)", { exact: false })).toExist()
      );
    })
  );

  it.effect("says so when no snapshot has been collected yet", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(chatsPage(null)),
        expectElement(role("heading", { name: "Chats" })).toExist(),
        expectElement(text("No chat snapshot yet.")).toExist()
      );
    })
  );
});
