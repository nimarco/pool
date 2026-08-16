/* API client and shared types.
 *
 * The browser talks only to Pool's own API. It never holds AWS credentials, never holds
 * a payment secret, and never calls an AWS service directly (AGENTS.md §4).
 *
 * These types mirror the server's serializers deliberately: no field here exists that
 * the server does not send, so a privacy leak would have to be introduced in two places.
 */

export type PoolStatus =
  | "forming"
  | "host_recruiting"
  | "host_selected"
  | "final_offer"
  | "funding"
  | "recovering"
  | "locked"
  | "purchase_ready"
  | "purchased"
  | "distributing"
  | "completed"
  | "failed"
  | "expired";

export type ParticipationState =
  | "eligible"
  | "provisional"
  | "final_offered"
  | "authorized"
  | "locked"
  | "declined"
  | "withdrawn"
  | "authorization_failed";

export interface PoolMember {
  household_id: string;
  display_name: string;
  units: number;
  state: ParticipationState;
  path: "smart_join" | "human_approved" | "pending_approval";
  estimated_cost_display: string;
  final_cost_display: string;
  baseline_display: string;
  savings_pct: string;
  travel_minutes: number;
  is_host: boolean;
}

export interface HostCandidateView {
  household_id: string;
  display_name: string;
  source: "standing" | "pool_member_volunteer";
  state: string;
  eligible: boolean;
  ineligible_reasons: string[];
  score: number;
  score_components: Record<string, number>;
  estimated_reward_display: string;
  supplier_distance_km: number;
}

export interface Economics {
  merchandise_cents: number;
  host_compensation_cents: number;
  other_fulfillment_cents: number;
  platform_fee_cents: number;
  payment_processing_cents: number;
  all_in_cents: number;
  retail_baseline_cents: number;
  gross_savings_cents: number;
  net_savings_cents: number;
  net_savings_bps: number;
  host_is_estimated: boolean;
  packages: {
    total_units: number;
    case_units: number;
    cases: number;
    units_purchased: number;
    surplus_units: number;
    moq_units: number;
    moq_met: boolean;
    surplus_resolved: boolean;
  };
}

export interface ViabilityCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface PoolView {
  pool_id: string;
  community_id: string;
  product_id: string;
  product_name: string;
  unit: string;
  brand: string;
  supplier: string;
  status: PoolStatus;
  pickup_site: string;
  pickup_is_public: boolean;
  pickup_permission: string;
  threshold_units: number;
  provisional_units: number;
  funded_units: number;
  member_count: number;
  progress_pct: number;
  has_final_offer: boolean;
  quote_verified_at: string;
  failure_reason: string;
  timing: Record<string, string>;
  host: {
    household_id: string;
    display_name: string;
    reward_display: string;
    handled_orders: number;
    supplier_distance_km: number;
  } | null;
  economics: Economics | null;
  savings_display: string;
  savings_pct: string;
  is_estimate: boolean;
  members?: PoolMember[];
  host_candidates?: HostCandidateView[];
  announcements?: { id: string; kind: string; body: string; author: string; created_at: string }[];
  viability?: {
    stage: string;
    viable: boolean;
    failed: string[];
    blocking_reason: string;
    checks: ViabilityCheck[];
  };
}

export interface Decision {
  decision_id: string;
  household_id: string;
  household_name: string;
  pool_id: string;
  kind: "join_pool" | "approve_final_offer" | "accept_substitute" | "host_offer" | "price_changed";
  state: string;
  facts: Record<string, unknown>;
  created_at: string;
  expires_at: string;
}

export interface ActivityEvent {
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
  members_participating: number;
  pools_total: number;
  pools_locked_or_beyond: number;
  pools_recovered: number;
  estimated_retail_spend_cents: number;
  pool_spend_cents: number;
  collective_savings_cents: number;
  average_buyer_savings_cents: number;
  merchandise_cents: number;
  host_compensation_cents: number;
  payment_processing_cents: number;
  platform_fee_cents: number;
  host_jobs: number;
  host_earnings_cents: number;
  host_handled_orders: number;
  pickups_completed: number;
  pickups_expected: number;
  no_shows: number;
  coordination_actions_automated: number;
  human_decisions_requested: number;
  commitments_without_asking: number;
  is_demo_data: boolean;
}

export interface CommunityView {
  id: string;
  name: string;
  kind: string;
  schedule: Record<string, number>;
  platform_fee: { mode: string; bps: number; fixed_cents_per_buyer: number };
  quote_max_age_hours: number;
  synthetic: boolean;
}

export interface AppState {
  workspace: string;
  community: CommunityView | null;
  pools: PoolView[];
  decisions: Decision[];
  activity: ActivityEvent[];
  metrics: Metrics;
  runs: RunSummary[];
  counts: {
    members: number;
    needs: number;
    products: number;
    standing_hosts: number;
    open_issues: number;
  };
  is_demo_data: boolean;
}

export interface MapData {
  members: {
    id: string;
    lat: number;
    lon: number;
    zone: string;
    active_needs: number;
    in_pool: boolean;
    pool_id: string | null;
  }[];
  sites: {
    id: string;
    name: string;
    lat: number;
    lon: number;
    is_public: boolean;
    kind: string;
    permission: string;
  }[];
  suppliers: { id: string; name: string; lat: number; lon: number }[];
  position_precision_m: number;
  note: string;
}

export interface NeedRow {
  need_id: string;
  household_id: string;
  household_name: string;
  product_id: string;
  product_name: string;
  unit: string;
  quantity: number;
  cadence_days: number;
  expected_next_need_date: string;
  earliest_purchase_date: string;
  latest_purchase_date: string;
  flexibility_days: number;
  routine_lead_days: number;
  min_savings_pct: number;
  max_spend_display: string;
  substitution: string;
  active: boolean;
}

export interface Health {
  ok: boolean;
  repository: string;
  routing_provider: string;
  model_provider: string;
  model_id: string;
  payment_provider: string;
  payment_mode: string;
  purchase_executor: string;
  purchase_simulated: boolean;
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
  pool_id: string;
  steps: ScenarioStep[];
}

export interface Checklist {
  pool_id: string;
  product_name: string;
  status: string;
  picked_up: number;
  total: number;
  units_total: number;
  distribution_starts_at: string;
  distribution_ends_at: string;
  earnings: Record<string, unknown>;
  orders: {
    household_id: string;
    display_name: string;
    units: number;
    state: string;
    picked_up_at: string;
    via: string;
  }[];
}

export interface OperatorView {
  offers: {
    offer_id: string;
    supplier: string;
    product_id: string;
    kind: string;
    unit_price_display: string;
    case_units: number;
    moq: string;
    min_units: number;
    verified_at: string;
    age_hours: number;
    source: string;
    active: boolean;
    expired: boolean;
  }[];
  pools: (PoolView & {
    payments: {
      payment_id: string;
      household_name: string;
      amount_display: string;
      state: string;
      provider: string;
      provider_mode: string;
      failure_code: string;
    }[];
    purchase: Record<string, unknown> | null;
  })[];
  issues: Record<string, unknown>[];
  failed_runs: { run_id: string; outcome: string; termination_reason: string; notes: string[] }[];
  metrics: Metrics;
}

export interface Credential {
  pool_id: string;
  household_id: string;
  token: string;
  code: string;
  replaced_previous: boolean;
}

/* ------------------------------------------------------------------ workspace */

const WORKSPACE_KEY = "pool.workspace";

/** Each visitor gets an isolated dataset, so two judges cannot corrupt each other. */
function workspaceId(): string {
  const existing = localStorage.getItem(WORKSPACE_KEY);
  if (existing) return existing;
  const fresh = `w${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem(WORKSPACE_KEY, fresh);
  return fresh;
}

export function resetWorkspaceId(): void {
  localStorage.removeItem(WORKSPACE_KEY);
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const response = await fetch(`${BASE}${path}${sep}workspace=${workspaceId()}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* keep the status line */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/health"),
  state: () => request<AppState>("/api/state"),
  map: () => request<MapData>("/api/map"),
  needs: () => request<{ needs: NeedRow[] }>("/api/needs").then((r) => r.needs),
  pool: (id: string) => request<PoolView>(`/api/pools/${id}`),
  checklist: (id: string) => request<Checklist>(`/api/pools/${id}/checklist`),
  operator: () => request<OperatorView>("/api/operator"),

  run: (trigger: string, instruction?: string) =>
    post<RunResult>("/api/agent/run", { trigger, instruction }),
  respond: (decisionId: string, approve: boolean) =>
    post<Record<string, unknown>>(`/api/decisions/${decisionId}/respond`, { approve }),
  volunteerHost: (poolId: string, householdId: string, body: Record<string, unknown>) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/host-offer/${householdId}`, body),
  respondHost: (poolId: string, householdId: string, accept: boolean) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/host-response/${householdId}`, { accept }),
  withdraw: (poolId: string, householdId: string) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/withdraw/${householdId}`),
  issueCredential: (poolId: string, householdId: string) =>
    post<Credential>(`/api/pools/${poolId}/pickup-credential/${householdId}`),
  redeem: (poolId: string, value: string, isCode: boolean) =>
    post<{ ok: boolean; reason: string; household_id: string; units: number }>(
      `/api/pools/${poolId}/redeem`,
      { value, is_code: isCode },
    ),
  announce: (poolId: string, householdId: string, kind: string, body: string) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/announce/${householdId}`, { kind, body }),
  reportException: (poolId: string, householdId: string, kind: string, detail: string) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/exception/${householdId}`, {
      kind,
      detail,
    }),
  reset: () => post<Record<string, unknown>>("/api/demo/reset"),
  scenario: () => post<ScenarioResult>("/api/demo/scenario"),
};

/* ------------------------------------------------------------------ formatting */

export function money(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

export function pct(bps: number): string {
  return `${(bps / 100).toFixed(1)}%`;
}

const STATUS_COPY: Record<PoolStatus, { label: string; tone: "ok" | "warn" | "info" | "stop" }> = {
  forming: { label: "Forming", tone: "info" },
  host_recruiting: { label: "Finding a host", tone: "warn" },
  host_selected: { label: "Host confirmed", tone: "info" },
  final_offer: { label: "Final price ready", tone: "warn" },
  funding: { label: "Collecting payment", tone: "warn" },
  recovering: { label: "Repairing", tone: "warn" },
  locked: { label: "Locked", tone: "ok" },
  purchase_ready: { label: "Paid — ordering", tone: "ok" },
  purchased: { label: "Ordered", tone: "ok" },
  distributing: { label: "Pickup open", tone: "ok" },
  completed: { label: "Completed", tone: "ok" },
  failed: { label: "Did not go ahead", tone: "stop" },
  expired: { label: "Expired", tone: "stop" },
};

export function statusCopy(status: PoolStatus) {
  return STATUS_COPY[status] ?? { label: status, tone: "info" as const };
}

/** Timestamps are ISO; the UI only ever needs a short, local, human form. */
export function shortTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function shortDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
