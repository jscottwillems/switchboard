import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  resolve: {
    alias: {
      "@switchboard/schemas": fileURLToPath(
        new URL("../../packages/schemas/ts/index.ts", import.meta.url),
      ),
    },
  },
});
