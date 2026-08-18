/* ESLint, flat config.
 *
 * `npm run lint` referenced ESLint from the first commit and ESLint was never a
 * dependency, so the frontend's quality gate has always failed the moment anyone ran
 * it — including `make qa`, which does not call it at all. This restores the promise
 * rather than deleting it: the script now runs, and CI-shaped checks can rely on it.
 *
 * Deliberately close to the recommended sets. The point is a working gate before the
 * AWS freeze, not a style migration across a codebase that already typechecks cleanly
 * and reads consistently — a hundred formatting findings would bury the two or three
 * that matter.
 */

import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "coverage", "*.config.js"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      // The app is browser-only; `window`, `document`, `fetch` and friends are ambient.
      // Listed explicitly rather than pulled from `globals` so the gate needs one fewer
      // dependency than it saves.
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        fetch: "readonly",
        console: "readonly",
        localStorage: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        crypto: "readonly",
        HTMLSelectElement: "readonly",
        HTMLInputElement: "readonly",
        RequestInit: "readonly",
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Fast Refresh needs a module to export components only. A warning, not an error:
      // it is a development-experience rule, and failing the build over it would make
      // the gate about the dev server rather than about the code.
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // `_`-prefixed names are the established convention here for a value that must be
      // destructured but not used.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Tests reach for DOM globals and expect-style assertions of their own.
    files: ["**/*.test.{ts,tsx}"],
    languageOptions: {
      globals: { globalThis: "readonly" },
    },
  },
);
