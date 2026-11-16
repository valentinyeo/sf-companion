import * as Cloudflare from "@alchemy.run/cloudflare";
import * as Alchemy from "alchemy";
import { localState } from "alchemy/State";
import * as Effect from "effect/Effect";

const allowedEmail = process.env.SF_ACCESS_EMAIL;

if (allowedEmail === undefined || allowedEmail === "") {
  throw new Error(
    "Set SF_ACCESS_EMAIL to the one email allowed to open the site."
  );
}

const serviceTokenId = process.env.SF_ACCESS_SERVICE_TOKEN_ID;

class Website extends Cloudflare.Website.Foldkit<Website>()("Website", {
  name: "sf-companion",
  rootDir: "../web",
  // The Factory page also lives at yeoux.net/factory/, behind yeoux.net's own login.
  // yeoux-site keeps every other yeoux.net path; its build assets sit under /_astro, so /assets is free.
  routes: [
    { pattern: "yeoux.net/factory*", zoneName: "yeoux.net" },
    { pattern: "yeoux.net/assets/*", zoneName: "yeoux.net" },
  ],
  memo: {
    include: [
      "src/**",
      "content/**",
      "public/**",
      "index.html",
      "package.json",
      "vite.config.ts",
    ],
    lockfile: true,
  },
  access: {
    name: "SF Companion",
    sessionDuration: "720h",
    policies: [
      { decision: "allow", include: [{ email: allowedEmail }] },
      ...(serviceTokenId === undefined || serviceTokenId === ""
        ? []
        : [
            {
              decision: "non_identity" as const,
              include: [{ serviceToken: serviceTokenId }],
            },
          ]),
    ],
  },
}) {}

export default Alchemy.Stack(
  "SfCompanion",
  {
    providers: Cloudflare.providers(),
    state: localState(),
  },
  Effect.gen(function* stack() {
    const website = yield* Website;

    return { websiteUrl: website.url };
  })
);
