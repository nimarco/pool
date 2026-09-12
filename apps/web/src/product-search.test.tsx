/* The empty state, when the thing somebody typed is real but lives somewhere else.
 *
 * The submission film shows Pool refusing *Kestrel Roastworks* and forming
 * *Harbourstone*. Both are invented — they exist so a refusal can be demonstrated
 * against verified bulk quotes, and they are installed into the verification
 * partition and nowhere else. So a viewer who watches the film and types the brand
 * into the ordinary product is told, truthfully, that Pool has never heard of it,
 * and has no way to tell that from the product being broken.
 *
 * The server answers the *class* of question with a boolean; these pin what the
 * screen does with it, including that it still says the ordinary thing for a
 * product that genuinely does not exist anywhere.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import * as apiModule from "./api";
import { ProductSearch } from "./product-search";

const ATTRIBUTION: apiModule.CatalogAttribution = {
  source: "Open Food Facts",
  source_url: "https://openfoodfacts.org",
  data_license: "ODbL-1.0",
  image_license: "CC-BY-SA-4.0",
  credit: "Open Food Facts contributors",
  snapshot: "2026-08-19",
};

function answer(verificationOnly: boolean) {
  vi.spyOn(apiModule.api, "searchProducts").mockResolvedValue({
    query: "kestrel",
    groups: [],
    results: [],
    attribution: ATTRIBUTION,
    verification_only: verificationOnly,
  });
}

beforeEach(() => vi.restoreAllMocks());
afterEach(cleanup);

it("signposts the verification world instead of denying the product exists", async () => {
  answer(true);
  render(<ProductSearch onSelect={() => {}} onUnresolved={() => {}} />);
  await userEvent.type(screen.getByLabelText(/what do you buy/i), "kestrel");

  const link = await screen.findByRole("link", { name: /Open verification demo/i });
  expect(link.getAttribute("href")).toBe("/verify");
  expect(document.body.textContent).toMatch(/verification walkthrough/i);
  expect(document.body.textContent).toMatch(/synthetic coffee community/i);
  // It must not claim Pool has never heard of something it demonstrably has.
  expect(document.body.textContent).not.toMatch(/does not have .* in its catalogue yet/i);
});

it("keeps the ordinary empty state for a product that really is unknown", async () => {
  answer(false);
  render(<ProductSearch onSelect={() => {}} onUnresolved={() => {}} />);
  await userEvent.type(screen.getByLabelText(/what do you buy/i), "flurbleglorp");

  await waitFor(() =>
    expect(document.body.textContent).toMatch(/in its catalogue yet/i),
  );
  expect(screen.queryByRole("link", { name: /Open verification demo/i })).toBeNull();
  expect(screen.getByRole("button", { name: /Tell Pool anyway/i })).toBeTruthy();
});
