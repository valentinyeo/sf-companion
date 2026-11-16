import * as Cloudflare from "@alchemy.run/cloudflare";

export const sfCompanionStateStoreName =
  "alchemy-state-store-sf-companion-state-store";

export const sfCompanionState = (state = Cloudflare.state) =>
  state({ workerName: sfCompanionStateStoreName });
