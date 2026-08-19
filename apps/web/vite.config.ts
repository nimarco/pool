import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // Emit every product photograph as its own file rather than base64 in the bundle.
    //
    // Vite inlines assets under 4 kB by default, which turned a dozen small packshots
    // into `data:` URIs. Two reasons not to: they would be downloaded by every visitor
    // inside the JS bundle when a search shows six images at a time, and the deployed
    // CSP allows `data:` for exactly one thing — the hand-written SVG favicon in
    // index.html. A security header whose comment has quietly stopped being true is
    // worse than a slightly larger asset directory.
    assetsInlineLimit: 0,
  },
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
