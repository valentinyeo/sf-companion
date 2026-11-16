import * as Cloudflare from "@alchemy.run/cloudflare";
import { expect, it } from "@effect/vitest";

import { sfCompanionState } from "../src/state-store.js";

it("asks Alchemy for this project's own state store", () => {
  const requested: Parameters<typeof Cloudflare.state>[0][] = [];

  sfCompanionState((options) => {
    requested.push(options);

    return Cloudflare.state(options);
  });

  expect(requested).toEqual([
    { workerName: "alchemy-state-store-sf-companion-state-store" },
  ]);
});
