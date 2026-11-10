import { defineConfig } from "vitest/config";

// The panel is built as one ES module that Home Assistant imports. It is
// written to the integration's frontend/dist folder (gitignored) and served
// at /com_system_static/.
export default defineConfig({
  build: {
    lib: {
      entry: "src/com-system-panel.ts",
      formats: ["es"],
      fileName: () => "com-system-panel.js",
    },
    outDir: "../custom_components/com_system/frontend/dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
    // Home Assistant imports the module from its own origin, so the dev
    // server must tell the browser where relative imports resolve.
    origin: "http://localhost:5173",
  },
  test: {
    environment: "happy-dom",
    include: ["test/**/*.test.ts"],
  },
});
