import * as Cloudflare from "@alchemy.run/cloudflare";

export class Website extends Cloudflare.Website.Foldkit<Website>()("Website", {
  rootDir: "../web",
}) {}
