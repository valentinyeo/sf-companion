import { describe, expect, it } from "@effect/vitest";
import { Effect, Option, Schema } from "effect";
import {
  expect as expectElement,
  given,
  role,
  scene,
  text,
} from "foldkit/scene";

import { initialModel } from "../src/client/app/model.js";
import { update } from "../src/client/app/update.js";
import { contentTypeOf, isValidSlug } from "../src/content/hub.js";
import { Item, itemOf, itemsIn, titleFromSlug } from "../src/content/item.js";
import type { ItemValue } from "../src/content/item.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const financeReport = itemOf(
  "reports",
  "7a7420f9-finance-triage-2026-11-19.html",
  {
    date: "2026-11-19",
    project: "finance",
    title: "Finance triage 2026-11-19",
  },
  "2026-11-19T09:00:00.000Z"
);

const quoteReport = itemOf(
  "reports",
  "5ee43a0a-matt-quote.html",
  { date: "2026-10-29", project: "clickshades", title: "Matt rebrand quote" },
  "2026-10-29T09:00:00.000Z"
);

const exploration = itemOf(
  "explorations",
  "1f3069d2-shipping.html",
  { date: "2026-11-08", project: "" },
  "2026-11-08T09:00:00.000Z"
);

const listed: readonly ItemValue[] = [financeReport, quoteReport, exploration];

describe("hub pages", () => {
  it.effect("lists every kept report on its own index", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(
          initialModel(
            { items: listed, route: SiteRoute.List({ section: "reports" }) },
            Option.none()
          )
        ),
        expectElement(role("heading", { name: "Reports" })).toExist(),
        expectElement(text("2 items.", { exact: false })).toExist(),
        expectElement(
          role("link", { name: "Finance triage 2026-11-19" })
        ).toExist(),
        expectElement(role("link", { name: "Matt rebrand quote" })).toExist(),
        expectElement(text("finance · 2026-11-19")).toExist()
      );
    })
  );

  it.effect("keeps explorations off the reports index", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(
          initialModel(
            {
              items: listed,
              route: SiteRoute.List({ section: "explorations" }),
            },
            Option.none()
          )
        ),
        expectElement(role("heading", { name: "Explorations" })).toExist(),
        expectElement(role("link", { name: "Shipping" })).toExist(),
        expectElement(
          role("link", { name: "Matt rebrand quote" })
        ).not.toExist()
      );
    })
  );

  it.effect("shows both sections and their newest rows on the home page", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(
          initialModel(
            { items: listed, route: SiteRoute.Home() },
            Option.none()
          )
        ),
        expectElement(
          role("heading", { name: "Software Factory Companion" })
        ).toExist(),
        expectElement(role("heading", { name: "Explorations" })).toExist(),
        expectElement(role("heading", { name: "Reports" })).toExist(),
        expectElement(
          role("link", { name: "Finance triage 2026-11-19" })
        ).toExist(),
        expectElement(role("link", { name: "All 2" })).toExist()
      );
    })
  );

  it.effect("says so when a section holds nothing", () =>
    Effect.sync(() => {
      scene(
        { update, view },
        given(
          initialModel(
            { items: [], route: SiteRoute.List({ section: "reports" }) },
            Option.none()
          )
        ),
        expectElement(text("No reports yet.")).toExist()
      );
    })
  );

  it.effect("names an item from its slug when metadata has no title", () =>
    Effect.sync(() => {
      expect(titleFromSlug("7a7420f9-finance-triage-2026-11-19.html")).toBe(
        "Finance triage 2026 11 19"
      );
      expect(itemsIn(listed, "reports").length).toBe(2);
      expect(financeReport.project).toBe("finance");
    })
  );

  it.effect("decodes the item schema the flags carry", () =>
    Effect.gen(function* decodeItem() {
      const decoded = yield* Schema.decodeEffect(Item)(financeReport);

      expect(decoded.slug).toBe(financeReport.slug);
      expect(decoded.date).toBe("2026-11-19");
    })
  );

  it.effect("serves only slugs the share surface accepts", () =>
    Effect.sync(() => {
      expect(isValidSlug("7a7420f9-finance-triage-2026-11-19.html")).toBe(true);
      expect(isValidSlug("../secret")).toBe(false);
      expect(isValidSlug("a/b")).toBe(false);
      expect(contentTypeOf("a.html")).toBe("text/html; charset=utf-8");
      expect(contentTypeOf("a.bin")).toBeUndefined();
    })
  );
});
