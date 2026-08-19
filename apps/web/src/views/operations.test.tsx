/* The operator's supplier-quote control.
 *
 * Two things are being asserted, and the second matters more than it looks. First, that
 * the panel says what an operator needs in order to understand the act: which product,
 * how much demand is already standing behind it, what the terms are, and that the
 * supplier is invented. Second, that recording a quote sends a *key* — because a control
 * that could send a price would turn the whole changing-world demonstration into a
 * presenter typing numbers until Pool agreed.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SupplierUpdates, api } from "../api";
import { OperationsView } from "./operations";

const updates: SupplierUpdates = {
  product_id: "prod_rice_jasmine",
  product_name: "Jasmine rice, 5 lb",
  unit: "bag",
  declared_members: 6,
  declared_units: 22,
  has_bulk_offer: false,
  quotes: [
    {
      key: "rice_split_case",
      offer_id: "off_rice_bulk_split",
      label: "Split-case quote",
      summary: "Riverbend will break cases: four bags to a case, twelve bags minimum.",
      product_id: "prod_rice_jasmine",
      unit_price_cents: 975,
      case_units: 4,
      min_units: 12,
      supplier_reference: "QUOTE-RICE-SPLIT",
      synthetic: true,
      recorded: false,
    },
    {
      key: "rice_case_program",
      offer_id: "off_rice_bulk_case",
      label: "Case-programme quote",
      summary: "Riverbend's standing programme rate: eight bags to a case.",
      product_id: "prod_rice_jasmine",
      unit_price_cents: 625,
      case_units: 8,
      min_units: 16,
      supplier_reference: "QUOTE-RICE-CASE",
      synthetic: true,
      recorded: false,
    },
  ],
};

function renderOperations(overrides: Partial<SupplierUpdates> = {}) {
  vi.spyOn(api, "operator").mockImplementation(() => new Promise(() => undefined));
  vi.spyOn(api, "checklist").mockImplementation(() => new Promise(() => undefined));
  vi.spyOn(api, "supplierUpdates").mockResolvedValue({ ...updates, ...overrides });
  render(<OperationsView hostPoolId={null} onBack={() => {}} />);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("recording a supplier quote", () => {
  it("leads with the demand that is already standing, not with the button", async () => {
    renderOperations();
    expect(await screen.findByText(/Jasmine rice, 5 lb/)).toBeTruthy();
    expect(
      screen.getByText(/already declared this independently — 22 bags standing/),
    ).toBeTruthy();
    expect(screen.getByText("no bulk quote")).toBeTruthy();
  });

  it("shows each quote's terms and says the supplier is synthetic", async () => {
    renderOperations();
    expect(await screen.findByText("Split-case quote")).toBeTruthy();
    expect(screen.getByText(/\$9\.75 per bag · 4 to a case · minimum 12 bags/)).toBeTruthy();
    expect(screen.getByText(/\$6\.25 per bag · 8 to a case · minimum 16 bags/)).toBeTruthy();
    expect(screen.getAllByText("synthetic").length).toBe(2);
    expect(
      screen.getByText(/invented for this demo and are stored as\s+synthetic, not as verified quotes/),
    ).toBeTruthy();
  });

  it("does not present itself as a way to make the demo succeed", async () => {
    renderOperations();
    await screen.findByText("Split-case quote");
    // Nothing here promises an outcome; the evaluator is named as the thing that decides.
    expect(screen.getByText(/Whether an order works is still the evaluator/)).toBeTruthy();
    expect(screen.getByText(/no run happens/)).toBeTruthy();
  });

  it("sends only a key — there is no field in which to send a price", async () => {
    const record = vi.spyOn(api, "recordSupplierQuote").mockResolvedValue({
      recorded: true,
      quote: "rice_split_case",
      offer_id: "off_rice_bulk_split",
      unit_price_display: "$9.75",
      case_units: 4,
      min_units: 12,
      verified_at: "2026-08-19T00:00:00Z",
      source: "synthetic",
      synthetic: true,
    });
    renderOperations();
    const user = userEvent.setup();

    await user.click((await screen.findAllByRole("button", { name: "Record quote" }))[0]);

    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0]).toEqual(["rice_split_case"]);
    // One argument, and it is the key. No price, minimum, case size or product reaches
    // the server from here.
    expect(record.mock.calls[0]).toHaveLength(1);
  });

  it("says which quotes are already on file, and does not offer them twice", async () => {
    renderOperations({
      has_bulk_offer: true,
      quotes: [
        { ...updates.quotes[0], recorded: true },
        { ...updates.quotes[1], recorded: false },
      ],
    });
    expect(await screen.findByText("recorded")).toBeTruthy();
    expect(screen.getByText("bulk quote on file")).toBeTruthy();
    const onFile = screen.getByRole("button", { name: "On file" }) as HTMLButtonElement;
    expect(onFile.disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Record quote" })).toBeTruthy();
  });
});
