import * as Cloudflare from "@alchemy.run/cloudflare";
import * as Alchemy from "alchemy";
import { localState } from "alchemy/State";
import { Redacted } from "effect";
import * as Effect from "effect/Effect";

const allowedEmail = process.env.SF_ACCESS_EMAIL;

if (allowedEmail === undefined || allowedEmail === "") {
  throw new Error(
    "Set SF_ACCESS_EMAIL to the one email allowed to open the site."
  );
}

const serviceTokenId = process.env.SF_ACCESS_SERVICE_TOKEN_ID;

const shareToken = process.env.SF_SHARE_TOKEN;

if (shareToken === undefined || shareToken === "") {
  throw new Error(
    "Set SF_SHARE_TOKEN to the yeoshare upload token, or publishing breaks."
  );
}

const hubRoutes = [
  "yeoux.net/",
  "yeoux.net/explorations*",
  "yeoux.net/reports*",
  "yeoux.net/factory*",
  "yeoux.net/assets/*",
].map((pattern) => ({ pattern, zoneName: "yeoux.net" }));

const content = Cloudflare.R2.Bucket.lookup({ name: "yeoux-site-content" });

const shareBindings = {
  CONTENT: content,
  SHARE_TOKEN: Redacted.make(shareToken),
};

const excludeListThatAlsoRebuildsOnGitignoredHourlyFeed = [
  "**/node_modules/**",
  "**/dist/**",
];

class Website extends Cloudflare.Website.Foldkit<Website>()("Website", {
  name: "sf-companion",
  rootDir: "../web",
  routes: hubRoutes,
  env: shareBindings,
  memo: {
    include: [
      "src/**",
      "content/**",
      "public/**",
      "index.html",
      "package.json",
      "vite.config.ts",
    ],
    exclude: excludeListThatAlsoRebuildsOnGitignoredHourlyFeed,
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
