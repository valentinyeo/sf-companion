declare module "cloudflare:workers" {
  import type { ContentBucket } from "./content/bucket.js";

  export const env: {
    readonly CONTENT?: ContentBucket;
    readonly SHARE_TOKEN?: string;
  };
}
