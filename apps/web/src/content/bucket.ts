export interface BucketEntry {
  readonly customMetadata: Readonly<Record<string, string>> | undefined;
  readonly key: string;
  readonly uploaded: Date;
}

export interface BucketListing {
  readonly cursor: string | undefined;
  readonly objects: readonly BucketEntry[];
  readonly truncated: boolean;
}

export interface BucketObject {
  readonly arrayBuffer: () => Promise<ArrayBuffer>;
  readonly httpMetadata: { readonly contentType?: string } | undefined;
}

export interface BucketPutOptions {
  readonly customMetadata: Readonly<Record<string, string>>;
  readonly httpMetadata: { readonly contentType: string };
}

export interface ContentBucket {
  readonly delete: (key: string) => Promise<void>;
  readonly get: (key: string) => Promise<BucketObject | null>;
  readonly head: (key: string) => Promise<{ readonly key: string } | null>;
  readonly list: (options: {
    readonly cursor?: string;
    readonly include?: readonly string[];
    readonly prefix: string;
  }) => Promise<BucketListing>;
  readonly put: (
    key: string,
    body: ArrayBuffer,
    options: BucketPutOptions
  ) => Promise<{ readonly key: string } | null>;
}
