/* API client and shared types.
 *
 * The browser talks only to Pool's own API. It never holds AWS credentials and never
 * calls an AWS service directly (AGENTS.md §4).
 */

export interface Member {
  household_id: string;
  display_name: string;
  neighborhood: string;
  units: number;
  cost_display: string;
  baseline_display: string;
  savings_pct: string;
  travel_minutes: number;
  state: "invited" | "committed" | "declined" | "withdrawn";
  path: "smart_join" | "human_approved" | "pending_approval";
}

export interface PoolView {
  pool_id: string;
  product_id: string;
  product_name: string;
  unit: string;
  supplier: string;
  status:
    | "candidate"
    | "inviting"
    | "threshold_met"
    | "confirmed"
    | "recovering"
    | "failed"
    | "expired"
    | "completed";
  pickup_site: string;
  pickup_is_public: boolean;
  deadline: string;
  threshold_units: number;
  committed_units: number;
  progress_pct: number;
  member_count: number;
  committed_count: number;
  baseline_cents: number;
  cost_cents: number;
  savings_cents: number;
  savings_display: string;
  savings_pct: string;
  avg_travel_minutes: number;
  members: Member[];
}

export interface PolicyCheck {
  rule: string;
  passed: boolean;
  detail: string;
}

export interface Decision {
  decision_id: string;
  household_id: string;
  household_name: string;
  pool_id: string;
  kind: string;
  state: string;
  created_at: string;
  expires_at: string;
  facts: {
    product?: string;
    units?: number;
    cost_display?: string;
    savings_bps?: number;
    travel_minutes?: number;
    pickup_site?: string;
    pickup_by?: string;
    is_exact_product?: boolean;
    blocking_rule?: string | null;
    context?: string;
    policy_checks?: PolicyCheck[];
  };
}

export interface ActivityItem {
  id: string;
  kind: string;
  summary: string;
  facts: Record<string, unknown>;
  pool_id: string | null;
  household_id: string | null;
  run_id: string | null;
  at: string;
}

export interface RunSummary {
  run_id: string;
  trigger: string;
  outcome: string;
  iterations: number;
  tool_calls: string[];
  termination_reason: string;
  model_provider: string;
  model_id: string;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  started_at: string;
}

export interface Metrics {
  households_participating: number;
  pools_total: number;
  pools_at_or_past_threshold: number;
  pools_recovered: number;
  estimated_retail_spend_cents: number;
  pool_spend_cents: number;
  collective_savings_cents: number;
  average_household_savings_cents: number;
  coordination_actions_automated: number;
  human_decisions_requested: number;
  commitments_without_asking: number;
  average_pickup_travel_minutes: number;
  is_demo_data: boolean;
}

export interface AppState {
  workspace: string;
  pools: PoolView[];
  decisions: Decision[];
  activity: ActivityItem[];
  metrics: Metrics;
  runs: RunSummary[];
  counts: { households: number; needs: number; products: number };
  is_demo_data: boolean;
}

export interface MapData {
  households: {
    id: string;
    lat: number;
    lon: number;
    neighborhood: string;
    active_needs: number;
    in_pool: boolean;
    pool_id: string | null;
  }[];
  sites: { id: string; name: string; lat: number; lon: number; is_public: boolean; kind: string }[];
  position_precision_m: number;
  note: string;
}

export interface Health {
  ok: boolean;
  repository: string;
  routing_provider: string;
  model_provider: string;
  model_id: string;
  schedules_enabled: boolean;
  bounds: Record<string, number>;
}

export interface RunResult {
  run_id: string;
  outcome: string;
  iterations: number;
  tool_calls: { name: string; ok: boolean; summary: string }[];
  termination_reason: string;
  model_provider: string;
  model_id: string;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  notes: string[];
}

export interface ScenarioStep {
  name: string;
  detail: string;
  facts: Record<string, unknown>;
}

export interface ScenarioResult {
  ok: boolean;
  failure: string;
  steps: ScenarioStep[];
}

export interface NeedRow {
  need_id: string;
  household_id: string;
  household_name: string;
  product_name: string;
  unit: string;
  quantity: number;
  cadence_days: number;
  needed_by: string;
  min_savings_pct: number;
  max_spend_display: string;
  accept_substitutes: boolean;
  active: boolean;
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

/** Each visitor gets an isolated workspace so two people cannot corrupt each other's demo. */
export function getWorkspace(): string {
  const KEY = "pool.workspace";
  let ws = localStorage.getItem(KEY);
  if (!ws) {
    ws = `w${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(KEY, ws);
  }
  return ws;
}

export function resetWorkspaceId(): string {
  localStorage.removeItem("pool.workspace");
  return getWorkspace();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const ws = getWorkspace();
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${BASE}${path}${sep}workspace=${encodeURIComponent(ws)}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* response had no JSON body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  state: () => request<AppState>("/api/state"),
  map: () => request<MapData>("/api/map"),
  needs: () => request<{ needs: NeedRow[] }>("/api/needs"),
  pool: (id: string) => request<PoolView>(`/api/pools/${id}`),
  runAgent: (trigger: string) =>
    request<RunResult>("/api/agent/run", {
      method: "POST",
      body: JSON.stringify({ trigger }),
    }),
  respond: (decisionId: string, approve: boolean) =>
    request<unknown>(`/api/decisions/${decisionId}/respond`, {
      method: "POST",
      body: JSON.stringify({ approve }),
    }),
  withdraw: (poolId: string, householdId: string) =>
    request<{ below_threshold: boolean; released_units: number }>(
      `/api/pools/${poolId}/withdraw/${householdId}`,
      { method: "POST" },
    ),
  reset: () => request<unknown>("/api/demo/reset", { method: "POST" }),
  scenario: () => request<ScenarioResult>("/api/demo/scenario", { method: "POST" }),
};

/* ---------------------------------------------------------------- formatting */

export function money(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const a = Math.abs(cents);
  return `${sign}$${Math.floor(a / 100)}.${String(a % 100).padStart(2, "0")}`;
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 45) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export const STATUS_LABEL: Record<PoolView["status"], string> = {
  candidate: "Forming",
  inviting: "Awaiting replies",
  threshold_met: "Ready",
  confirmed: "Confirmed",
  recovering: "Repairing",
  failed: "Did not form",
  expired: "Expired",
  completed: "Completed",
};

export function statusTone(status: PoolView["status"]): string {
  if (status === "threshold_met" || status === "confirmed" || status === "completed") return "chip-ok";
  if (status === "recovering" || status === "failed" || status === "expired") return "chip-warn";
  return "chip-info";
}
