import { describe, expect, it } from "vitest";

import { shortDateOnly } from "./api";

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
