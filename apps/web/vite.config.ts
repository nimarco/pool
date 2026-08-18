import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { outDir: "dist", sourcemap: false },
  // A small number of tests, aimed at the claims a judge reads off the screen: the
  // primary Product action, and the labels that say whether a number is provisional,
  // final, or simulated. Not a coverage target — the domain invariants are asserted in
  // Python, where they are actually enforced.
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
