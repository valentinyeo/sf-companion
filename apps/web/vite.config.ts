import { foldkit } from "@foldkit/vite-plugin";
import { defineConfig } from "vite";

import { stylexPlugin } from "./stylex.js";

export default defineConfig({
  plugins: [
    stylexPlugin(),
    foldkit({
      ssr: {
        build: { prerender: true },
        clientEntry: "/src/client/entry.ts",
        serverEntry: "/src/entry.server.ts",
      },
    }),
  ],
});
