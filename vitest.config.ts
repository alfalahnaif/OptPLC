import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.tsx"],
    css: true,
    // Headroom for findBy* waits under cold starts (D-021, temporary).
    testTimeout: 20000
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src")
    }
  }
});
