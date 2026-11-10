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
    // Lets a debugger map the bundle back to the .ts source.
    sourcemap: true,
  },
  server: {
    // Reachable from outside the devcontainer (the port is forwarded).
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Home Assistant (port 8123) loads the module from this server, so
    // allow its origin and say where relative imports resolve.
    cors: true,
    origin: "http://localhost:5173",
  },
  test: {
    environment: "happy-dom",
    include: ["test/**/*.test.ts"],
  },
});
