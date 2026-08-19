/* Showcase mode addresses the showcase's partition, and only ever that one.
 *
 * The scripted lifecycle replays a whole community — a declaration, a host, a declined
 * card, a recovery, a lock, a purchase and ten handoffs. None of it may land in the
 * account the person at the screen set up for themselves, and the server keeps that
 * promise by giving the showcase its own workspace (`public_demo.showcase_workspace`).
 *
 * The half the server cannot keep is *which* partition the browser asks for. Every
 * request this app makes carries a workspace, chosen by one module-level flag, so
 * entering showcase mode is not a change of screen — it is a change of world, and the
 * flag has to move at the same moment the screen does. When it did not, the showcase's
 * front page read the visitor's own community and reported its member and need counts as
 * the showcase's; and leaving again asked the visitor's partition for a pool id that only
 * exists in the showcase.
 *
 * So these tests are at the fetch boundary rather than on a component's props: the thing
 * under test is the URL, and the only honest way to assert a URL is to watch the one that
 * was actually requested.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { resetWorkspaceId, setShowcaseScope } from "./api";

/** The two partitions, and a pool that exists in each. Deliberately different ids: a
 *  request that mixes one partition's pool with the other partition's workspace is the
 *  bug, and it is only visible if the two can be told apart. */
const VISITOR_POOL = "pool_visitor_whey";
const SHOWCASE_POOL = "pool_showcase_whey";

let requested: string[] = [];

function poolView(workspace: string) {
  const showcase = workspace.endsWith("-showcase");
  return {
    pool_id: showcase ? SHOWCASE_POOL : VISITOR_POOL,
    status: "forming",
    product_id: "prod_whey_vanilla",
    product_name: "100% Whey Protein",
    brand: "Optimum Nutrition",
    image_ref: "",
    unit: "tub",
    buyer_count: 10,
    units: 24,
    threshold_units: 24,
    pickup_site: "North Hall lobby",
    savings_display: "",
    savings_pct: "",
    is_estimate: true,
    members: [],
    execution_proof: null,
  };
}

function appState(workspace: string) {
  return {
    workspace,
    consumer: {
      household_id: "hh_navarro",
      display_name: workspace.endsWith("-showcase") ? "You" : "Marco",
      onboarded: true,
      has_payment_method: true,
      autonomy_mode: "ask_me",
      place: {
        community_id: "comm_demo_university",
        community_name: "Demo University",
        member_count: 24,
        pickup_site_count: 4,
        synthetic: true,
      },
    },
    community: { id: "comm_demo_university", name: "Demo University", kind: "university" },
    pools: [poolView(workspace)],
    decisions: [],
    activity: [],
    metrics: {},
    runs: [],
    counts: {
      // The number the showcase's front page used to borrow from the visitor.
      members: 24,
      needs: workspace.endsWith("-showcase") ? 31 : 34,
      products: 6,
      standing_hosts: 3,
      open_issues: 0,
    },
    is_demo_data: true,
  };
}

function memberView(workspace: string) {
  return {
    id: "hh_navarro",
    display_name: "Marco",
    zone: "North",
    opportunity: {
      pool_id: poolView(workspace).pool_id,
      status: "forming",
      product_id: "prod_whey_vanilla",
      participation_state: "provisional",
      units: 2,
      need_id: "need_whey",
      declared_product_id: "prod_whey_vanilla",
      is_exact_product: true,
      declared_product_name: "",
    },
    other_pool_ids: [],
    standing_demand: [],
    needs_outlook: [],
    community_membership: null,
    autonomy_display: {
      mode: "ask_me",
      min_savings: "15%",
      max_spend: "$120.00",
      max_travel: "20 min",
      substitution: "exact_only",
    },
    has_payment_method: true,
    host_profile: null,
  };
}

/** Answers every read the shell makes, keyed on the path, and records the URL. */
function stubFetch() {
  requested = [];
  const handler = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    const workspace = new URL(url, "http://localhost").searchParams.get("workspace") ?? "";
    const path = new URL(url, "http://localhost").pathname;
    const body = (payload: unknown) =>
      ({ ok: true, status: 200, json: async () => payload }) as unknown as Response;

    if (path === "/api/state") return body(appState(workspace));
    if (path === "/api/map") return body({ members: [], sites: [], community: null });
    if (path === "/api/health") return body({ ok: true, bounds: {}, agent_tools: [] });
    if (path === "/api/demo/config") {
      return body({
        public_demo: true,
        live_agent_available: false,
        live_agent_runtime: "",
        region: "",
        max_live_per_session: 3,
        payments: "simulated",
        purchase: "simulated",
      });
    }
    if (path === "/api/needs") return body({ needs: [], products: [], limits: {} });
    if (path.startsWith("/api/members/")) return body(memberView(workspace));
    if (path === "/api/hosting/opportunities") {
      return body({ household_id: "hh_navarro", offers: [], accepted: [] });
    }
    if (path.startsWith("/api/pools/")) {
      const id = path.split("/")[3];
      // A partition only holds its own pool. Asking the wrong one is a 404 in the real
      // API, and it has to be a 404 here or the bug would pass unnoticed.
      if (id !== poolView(workspace).pool_id) {
        return { ok: false, status: 404, json: async () => ({ detail: "not found" }) } as
          unknown as Response;
      }
      return body(poolView(workspace));
    }
    if (path === "/api/demo/scenario") {
      return body({ ok: true, failure: "", pool_id: SHOWCASE_POOL, workspace, steps: [] });
    }
    return body({});
  });
  vi.stubGlobal("fetch", handler);
}

/** Requests that carry a workspace, as (workspace, path) pairs. */
function addressed(): { workspace: string; path: string }[] {
  return requested
    .map((url) => new URL(url, "http://localhost"))
    .filter((u) => u.searchParams.has("workspace"))
    .map((u) => ({ workspace: u.searchParams.get("workspace") as string, path: u.pathname }));
}

function visitorWorkspace(): string {
  const first = addressed()[0];
  return first.workspace;
}

beforeEach(() => {
  // Both are module state that outlives a test: a leaked scope would make the next test
  // pass for the wrong reason, which is the one failure mode this file cannot afford.
  setShowcaseScope(false);
  resetWorkspaceId();
  stubFetch();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setShowcaseScope(false);
  resetWorkspaceId();
});

async function openShowcaseFromTheDrawer() {
  const user = userEvent.setup();
  render(<App />);
  await waitFor(() => expect(screen.getByText(/Good \w+, Marco/)).toBeTruthy());
  // The drawer's opener is labelled with the community name and titled with what it
  // contains; the title is the stable half.
  await user.click(screen.getByTitle("Demo environment, controls, and what is real here"));
  await user.click(screen.getByRole("button", { name: "Open Showcase mode" }));
  return user;
}

describe("showcase mode is a different world, not a different screen", () => {
  it("points every request at the showcase partition when entered from Demo controls", async () => {
    await openShowcaseFromTheDrawer();

    const visitor = visitorWorkspace();
    const showcase = `${visitor}-showcase`;
    await waitFor(() =>
      expect(
        addressed().some((r) => r.workspace === showcase && r.path === "/api/state"),
      ).toBe(true),
    );

    // And the showcase's own front page is read from the showcase, so the community
    // counts it prints are that community's rather than the visitor's.
    const afterEntry = addressed().slice(
      addressed().findIndex((r) => r.workspace === showcase),
    );
    expect(afterEntry.every((r) => r.workspace === showcase)).toBe(true);
  });

  it("never asks one partition for the other partition's pool", async () => {
    const user = await openShowcaseFromTheDrawer();

    const visitor = visitorWorkspace();
    const showcase = `${visitor}-showcase`;
    await waitFor(() =>
      expect(addressed().some((r) => r.workspace === showcase)).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Leave showcase" }));
    await waitFor(() => expect(screen.getByText(/Good \w+, Marco/)).toBeTruthy());

    const crossed = addressed().filter(
      (r) =>
        (r.workspace === visitor && r.path === `/api/pools/${SHOWCASE_POOL}`) ||
        (r.workspace === showcase && r.path === `/api/pools/${VISITOR_POOL}`),
    );
    expect(crossed).toEqual([]);
  });
});
