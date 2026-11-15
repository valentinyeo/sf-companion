import { describe, expect, it } from "@effect/vitest";
import { Effect } from "effect";
import {
  expect as expectElement,
  given,
  role,
  scene,
  text,
} from "foldkit/scene";

import { initialModel } from "../src/client/app/model.js";
import { update } from "../src/client/app/update.js";
import { ContentError, decodeEntry } from "../src/content/entry.js";
import { view } from "../src/features/page.js";
import { SiteRoute } from "../src/features/route.js";

const fixturePath = "content/explorations/fixture-exploration.json";

const fixtureFile = {
  body: "A fixture body proves the detail page renders entry text.",
  date: "2026-02-01",
  kind: "exploration",
  summary: "A fixture summary.",
  title: "Fixture exploration",
};

describe("entry pages", () => {
  it.effect("renders a decoded entry on both of its pages", () =>
    Effect.gen(function* () {
      const entry = yield* decodeEntry(
        "exploration",
        fixturePath,
        JSON.stringify(fixtureFile)
      );

      const list = SiteRoute.List({ section: "explorations" });
      const detail = SiteRoute.Entry({
        section: "explorations",
        slug: entry.slug,
      });

      scene(
        { update, view },
        given(initialModel({ route: list }, [entry])),
        expectElement(role("link", { name: entry.title })).toExist()
      );

      scene(
        { update, view },
        given(initialModel({ route: detail }, [entry])),
        expectElement(role("heading", { name: entry.title })).toExist(),
        expectElement(text(entry.body)).toExist()
      );
    })
  );

  it.effect("rejects an entry whose kind is unknown", () =>
    Effect.gen(function* () {
      const failure = yield* Effect.flip(
        decodeEntry(
          "exploration",
          fixturePath,
          JSON.stringify({ ...fixtureFile, kind: "note" })
        )
      );

      expect(failure).toBeInstanceOf(ContentError);
    })
  );
});
