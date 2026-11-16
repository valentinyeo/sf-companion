import * as Cloudflare from "@alchemy.run/cloudflare";
import * as Alchemy from "alchemy";
import * as Effect from "effect/Effect";

import { Website } from "../web/src/website.js";
import { sfCompanionState } from "./src/state-store.js";

const SITE_DOMAIN = "TODO.example";

export default Alchemy.Stack(
  "SfCompanion",
  {
    providers: Cloudflare.providers(),
    state: sfCompanionState(),
  },
  Effect.gen(function* stack() {
    const website = yield* Website;

    return { siteDomain: SITE_DOMAIN, websiteUrl: website.url };
  })
);
