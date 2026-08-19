import { describe, expect, it } from "vitest";

import { pct, shortDateOnly } from "./api";

describe("semantic calendar dates", () => {
  it("does not move a YYYY-MM-DD need date into the previous local day", () => {
    const naive = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "America/Chicago",
    }).format(new Date("2026-08-28"));

    expect(naive).toBe("Aug 27");
    expect(shortDateOnly("2026-08-28", "en-US")).toBe("Aug 28");
  });

  it("leaves malformed and impossible dates visible rather than normalizing them", () => {
    expect(shortDateOnly("2026-02-30", "en-US")).toBe("2026-02-30");
    expect(shortDateOnly("not-a-date", "en-US")).toBe("not-a-date");
  });
});

describe("percentages agree with the server's own formatter", () => {
  it("truncates the tenth digit exactly as bps_to_pct_str does", () => {
    // 2357 bps is one purchase. Rounding here and truncating on the server put "23.6%"
    // and "23.5%" on the same screen for the same money.
    expect(pct(2357)).toBe("23.5%");
    expect(pct(2360)).toBe("23.6%");
    expect(pct(0)).toBe("0.0%");
    expect(pct(-1299)).toBe("-12.9%");
  });
});
