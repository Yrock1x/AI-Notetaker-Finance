import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  // tsconfig uses `jsx: "preserve"` (Next transforms it); tell esbuild to use
  // the automatic runtime so .tsx tests don't need `import React`.
  esbuild: { jsx: "automatic" },
  test: {
    globals: true,
    environment: "node",
    // macOS writes `._*` AppleDouble companions on non-HFS volumes (this repo
    // lives on an external drive); they match the test glob but aren't code.
    exclude: ["**/node_modules/**", "**/._*"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
