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
  /** The run id written on the pool record by the coordinator that created it. */
  created_by_run: string;
  /** Server-verified causal link to that exact run, or null when no such proof exists. */
  execution_proof: PoolExecutionProof | null;
  community_id: string;
  product_id: string;
  product_name: string;
  unit: string;
  brand: string;
  variant: string;
  image_ref: string;
  supplier: string;
  /** Provenance of the *quote*, not of the product identity. `synthetic` means Pool
   *  invented these terms for the demo; nobody quoted them. */
  offer_source: string;
  status: PoolStatus;
  pickup_site: string;
  pickup_is_public: boolean;
  pickup_permission: string;
  threshold_units: number;
  provisional_units: number;
  funded_units: number;
  /** Every membership still on the record, including any whose payment failed. */
  member_count: number;
  /** How many of those are actually going to receive something. Differs from
   *  `member_count` exactly when an authorisation failed and a replacement joined. */
  buyer_count: number;
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

export interface PoolExecutionProof {
  pool_id: string;
  created_by_run: string;
  run_id: string;
  relation_verified: true;
  execution: {
    service: string;
    live: boolean;
    region: string;
  };
  workspace_readback: {
    run_recorded: true;
    pool_recorded: true;
    same_workspace: true;
  };
  run: RunSummary;
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
  enablement: {
    verified_members: number;
    total_memberships: number;
    verification_methods: string[];
    independent_need_declarers: number;
    designated_pickup_sites: {
      id: string;
      name: string;
      is_public: boolean;
      permission: string;
    }[];
  };
}

/** The local network a member coordinates inside, as onboarding presents it.
 *
 *  No coordinates: Pool never asks the browser for a position, and this demo's community
 *  is invented, so the honest thing to show is the network's name and size rather than a
 *  place on Earth. */
export interface Place {
  community_id: string;
  community_name: string;
  member_count: number;
  pickup_site_count: number;
  synthetic: boolean;
}

/** Who the app should present as "you", and what setup is outstanding.
 *
 *  Authoritative server state, not a browser preference: a reset has to be able to clear
 *  it, and the name it carries is the one the activity feed and decision inbox use. */
export interface Consumer {
  household_id: string;
  display_name: string;
  onboarded: boolean;
  has_payment_method: boolean;
  autonomy_mode: string;
  place: Place;
}

export interface AppState {
  workspace: string;
  consumer: Consumer;
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
  /** Enough identity to render the same card the search showed. */
  brand: string;
  variant: string;
  category: string;
  image_ref: string;
  quantity: number;
  cadence_days: number;
  expected_next_need_date: string;
  earliest_purchase_date: string;
  latest_purchase_date: string;
  flexibility_days: number;
  routine_lead_days: number;
  min_savings_pct: number;
  max_spend_display: string;
  max_spend_cents: number;
  substitution: string;
  active: boolean;
}

/** The catalogue a member can declare a need against, served alongside their needs. */
export interface ProductRow {
  product_id: string;
  name: string;
  unit: string;
  brand: string;
}

/** One product a member might mean, as a card renders it.
 *
 *  `product_id` is here because the form has to send it back, and is never displayed:
 *  a member should not learn that Pool keeps internal identifiers. `image_ref` names a
 *  *bundled* asset rather than a URL — the demo may not depend on a third-party image
 *  host, and the deployed CSP is `img-src 'self'`. */
export interface ProductCandidate {
  product_id: string;
  name: string;
  brand: string;
  variant: string;
  display_size: string;
  unit: string;
  category: string;
  image_ref: string;
  /** Pool currently holds a verified bulk quote it could buy this against. A fact about
   *  this deployment, not about the product — and never a reason to change what somebody
   *  declared. Absent on a candidate that came from somewhere other than search. */
  sourceable?: boolean;
}

/** Licence obligations that travel with the bundled catalogue snapshot. */
export interface CatalogAttribution {
  source: string;
  source_url: string;
  data_license: string;
  image_license: string;
  credit: string;
  snapshot: string;
}

export interface ProductSearchResult {
  query: string;
  results: ProductCandidate[];
  attribution: CatalogAttribution;
}

export interface NeedLimits {
  max_quantity: number;
  max_cadence_days: number;
  max_min_savings_pct: number;
  max_spend_cents: number;
  max_horizon_days: number;
}

export interface NeedsView {
  needs: NeedRow[];
  products: ProductRow[];
  limits: NeedLimits;
}

/** One standing declaration, as the member states it.
 *
 *  `flexibility_days` rather than a raw earliest-purchase date: "how far ahead of
 *  myself am I willing to buy" is the question a person can answer, and the server
 *  derives the date the timing engine needs. Nothing here names another member — a
 *  need is a statement about one household, never about a group. */
export interface NeedDraft {
  household_id: string;
  product_id: string;
  quantity: number;
  cadence_days: number;
  expected_next_need_date: string;
  flexibility_days: number;
  routine_lead_days: number;
  min_savings_pct: number;
  max_spend_cents: number;
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
  bounds: {
    max_iterations: number;
    max_tool_calls: number;
    max_duplicate_tool_calls: number;
    workflow_timeout_seconds: number;
  };
  /** The exact tool surface the running agent was given, served from its own
   *  definition so the UI cannot display a catalogue that has drifted. */
  agent_tools: { name: string; kind: "read" | "record" | "act" | "end" }[];
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
  /** The partition the scripted lifecycle ran in — never the visitor's own. */
  workspace: string;
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

/** Why one of this member's standing declarations has not produced a pool.
 *
 *  Server-computed by the same deterministic evaluator the coordinator's own tool
 *  calls, so the sentence a member reads and the verdict the agent acts on come from
 *  one implementation. */
export interface NeedOutlook {
  need_id: string;
  product_id: string;
  product_name: string;
  state:
    | "in_pool"
    | "ready"
    | "short"
    | "no_supply"
    | "not_matched"
    | "not_worth_it"
    | "not_in_round"
    | "retired";
  reason: string;
  pool_id: string;
  units_needed: number;
  units_available: number;
}

/** The pool this member is genuinely in, and the declaration that put them there.
 *
 *  `null` when they are in none — which is a real answer. A consumer surface must never
 *  fill that gap with whichever pool happens to exist in the workspace. */
export interface PersonalOpportunity {
  pool_id: string;
  status: PoolStatus;
  product_id: string;
  participation_state: ParticipationState;
  units: number;
  /** Lineage: the stored `Membership.need_id`, not an inference from product names. */
  need_id: string;
  declared_product_id: string;
  /** False when the pool is buying an authorised substitute rather than the exact
   *  product this member typed. The card must say so; the photograph will not. */
  is_exact_product: boolean;
  /** What they typed, when it differs from what the pool buys. */
  declared_product_name: string;
}

/** What already exists around one declaration, before Pool has evaluated anything.
 *
 *  Inputs, deliberately without a verdict: how much compatible demand accumulated on its
 *  own, and the smallest quantity the supplier will sell. Whether those people can reach
 *  one pickup point, whether their timing overlaps, whether the units fill a case and
 *  whether it beats retail are what a run decides — and a screen that answered them in
 *  advance would be telling somebody the result before Pool had done the work. */
export interface StandingDemand {
  need_id: string;
  product_id: string;
  product_name: string;
  unit: string;
  my_units: number;
  compatible_members: number;
  compatible_units: number;
  minimum_units: number;
  has_supplier: boolean;
  /** Set when the order Pool could form would buy an authorised substitute rather than
   *  the exact product declared. Never silent. */
  sourceable_product_id: string;
  sourceable_product_name: string;
}

/** One declaration's outcome in one run, as the server assembled it from what that run
 *  actually established. Never recomputed here, and never shown for another run. */
export interface RunReportResult {
  need_id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit: string;
  result:
    | "formed_included"
    | "formed_excluded"
    | "declined"
    | "viable_not_acted"
    | "not_investigated"
    | "already_coordinated";
  pool_id: string;
  units: number;
  reason_code: string;
  is_exact_product: boolean;
  declared_product_name: string;
  headline: string;
  facts: string[];
  participation_state?: string;
  status?: string;
}

export interface RunReport {
  run_id: string;
  trigger: string;
  objective_kind: string;
  outcome: string;
  at: string;
  model_provider: string;
  /** False when this run was not anchored to this member — a community-wide scan, or
   *  somebody else's. The report is then empty by construction. */
  is_mine: boolean;
  results: RunReportResult[];
  evaluated_product_ids: string[];
  also_evaluated?: { product_id: string; product_name: string; viable: boolean; reason_code: string }[];
  elsewhere?: { pool_id: string; product_name: string; status: string; buyer_count: number }[];
}

export interface MemberView {
  id: string;
  display_name: string;
  zone: string;
  opportunity: PersonalOpportunity | null;
  other_pool_ids: string[];
  standing_demand: StandingDemand[];
  needs_outlook: NeedOutlook[];
  community_membership: {
    community_id: string;
    status: string;
    verification_method: string;
    verified_at: string;
  } | null;
  has_payment_method: boolean;
  autonomy_display: {
    mode: string;
    min_savings: string;
    max_spend: string;
    max_travel: string;
    substitution: string;
    public_pickup_only: boolean;
  };
  host_profile: Record<string, unknown> | null;
}

export interface HostOpportunities {
  household_id: string;
  offers: {
    pool_id: string;
    product_name: string;
    orders: number;
    units: number;
    supplier_distance_km: number;
    estimated_earnings_display: string;
    pickup_site: string;
    distribution_starts_at: string;
    distribution_ends_at: string;
    expires_at: string;
  }[];
  active_jobs: Checklist[];
}

export interface Credential {
  pool_id: string;
  household_id: string;
  token: string;
  code: string;
  replaced_previous: boolean;
}

export interface DemoConfig {
  public_demo: boolean;
  live_agent_available: boolean;
  live_agent_runtime: string;
  region: string;
  max_live_per_session: number;
  payments: string;
  purchase: string;
}

export interface LiveAgentRun {
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
  hitl_decisions_created: number;
}

/** What the authoritative store held after a live run, read back by the server from the
 *  same table it serves `/api/state` from. Not the agent's account of what it did. */
export interface LiveAgentObserved {
  /** Whether the run the runtime reported is present in this session's own data. The
   *  proof that both halves are writing and reading one table. */
  run_recorded: boolean;
  pools: number;
  /** Pool ids whose stored `created_by_run` is this exact run id. */
  created_pool_ids: string[];
  run_pool_links_verified: boolean;
  pending_decisions: number;
}

export type LiveAgentClassification =
  | "success"
  | "safe_refusal"
  | "safe_pre_execution_failure"
  | "ambiguous_remote_execution"
  | "workspace_busy";

/** Either a real invocation of the deployed runtime, or an honest failure. Never a
 *  fabricated run — the server has no code path that invents one.
 *
 *  `refresh_state` appears on both branches, because a failure is not evidence that
 *  nothing happened: the invocation can time out after the agent has already written to
 *  the shared workspace. Re-reading is how the page tells the truth either way. */
export type LiveAgentResult =
  | {
      ok: true;
      live: true;
      service: string;
      runtime: string;
      region: string;
      wall_ms: number;
      run: LiveAgentRun;
      observed: LiveAgentObserved;
      refresh_state: true;
      classification: "success";
      remote_may_still_write: false;
      allow_local_fallback: false;
      note: string;
    }
  | {
      ok: false;
      live: false;
      reason: string;
      classification: Exclude<LiveAgentClassification, "success">;
      remote_may_still_write: boolean;
      allow_local_fallback: boolean;
      refresh_state: boolean;
    };

/* ------------------------------------------------------------------ workspace */

const WORKSPACE_KEY = "pool.workspace";

/** The shape the deployed demo accepts. Anything else is refused server-side, so a
 *  value left over from an older build is replaced rather than sent. */
const WORKSPACE_RE = /^w[a-z0-9]{8,32}$/;

function freshWorkspaceId(): string {
  const bytes = new Uint8Array(10);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  const body = Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("");
  return `w${body.slice(0, 16)}`;
}

/** Held in the module too, so a browser with storage disabled still gets *one*
 *  stable session for the tab rather than a new one on every request. */
let cachedWorkspace: string | null = null;

/** The suffix the server derives the canonical showcase's own partition with.
 *  Mirrors `public_demo.SHOWCASE_SUFFIX`; a session id can never contain a hyphen, so
 *  the two can never collide. */
const SHOWCASE_SUFFIX = "-showcase";

/** Showcase mode is a different world, not a different screen.
 *
 *  The scripted lifecycle declares a flagship need, drives a payment failure, a
 *  recovery, a lock and ten pickups. None of that may land in the account the person at
 *  the screen set up for themselves — so while showcase mode is on, every request this
 *  module makes addresses the showcase partition instead. Turning it off restores the
 *  visitor's own session exactly, because nothing about it was ever written. */
let showcaseScope = false;

export function setShowcaseScope(on: boolean): void {
  showcaseScope = on;
}

export function inShowcaseScope(): boolean {
  return showcaseScope;
}

/** Each visitor gets an isolated dataset, so two judges cannot corrupt each other. */
function workspaceId(): string {
  if (cachedWorkspace) return cachedWorkspace;
  let existing: string | null = null;
  try {
    existing = localStorage.getItem(WORKSPACE_KEY);
  } catch {
    /* private browsing with storage disabled — fall through to a per-tab id */
  }
  if (existing && WORKSPACE_RE.test(existing)) {
    cachedWorkspace = existing;
    return existing;
  }
  const fresh = freshWorkspaceId();
  try {
    localStorage.setItem(WORKSPACE_KEY, fresh);
  } catch {
    /* nothing to do: the cache below still isolates this tab */
  }
  cachedWorkspace = fresh;
  return fresh;
}

/** The workspace this request should address: the visitor's own, or the showcase's. */
function activeWorkspace(): string {
  const base = workspaceId();
  return showcaseScope ? `${base}${SHOWCASE_SUFFIX}` : base;
}

export function resetWorkspaceId(): void {
  cachedWorkspace = null;
  try {
    localStorage.removeItem(WORKSPACE_KEY);
  } catch {
    /* nothing stored, nothing to clear */
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const response = await fetch(`${BASE}${path}${sep}workspace=${activeWorkspace()}`, {
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
  needs: () => request<NeedsView>("/api/needs"),
  /** Finish account setup. The household id is a server constant, so this can only ever
   *  write the caller's own account. */
  completeOnboarding: (displayName: string, autonomyMode: string) =>
    post<Consumer>("/api/onboarding", {
      display_name: displayName,
      autonomy_mode: autonomyMode,
    }),
  /** Save a simulated payment method for this account. Creates no charge and no hold.
   *
   *  Takes no id on purpose: the server picks the consumer household, so there is no
   *  field a caller could point at somebody else — including the synthetic member whose
   *  card is seeded to decline. */
  saveOwnPaymentMethod: () =>
    post<{ ok: boolean; has_payment_method: boolean }>("/api/onboarding/payment-method"),
  /** Resolve free text into products a member might mean.
   *
   *  Ranked server-side against a bundled snapshot by a pure function: no model call,
   *  no third-party request, same answer every time. That is what lets the first
   *  interaction in the product work with the network unplugged. */
  searchProducts: (q: string, limit = 6) =>
    request<ProductSearchResult>(
      `/api/products/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
  /** Record something the catalogue does not have. The member may declare a need for
   *  it; Pool simply cannot form a group order until a supplier has been verified. */
  customProduct: (name: string) =>
    post<ProductCandidate & { sourceable: boolean; note: string }>(
      "/api/products/custom",
      { name },
    ),
  declareNeed: (draft: NeedDraft) => post<NeedRow>("/api/needs", draft),
  amendNeed: (needId: string, draft: NeedDraft) =>
    post<NeedRow>(`/api/needs/${needId}`, draft),
  pool: (id: string) => request<PoolView>(`/api/pools/${id}`),
  checklist: (id: string) => request<Checklist>(`/api/pools/${id}/checklist`),
  operator: () => request<OperatorView>("/api/operator"),
  member: (householdId: string) => request<MemberView>(`/api/members/${householdId}`),
  hostOpportunities: (householdId: string) =>
    request<HostOpportunities>(`/api/hosting/opportunities?household_id=${householdId}`),

  // The client picks an action *name*; the server owns the prompt. `instruction`
  // replaces the coordinator's entire run prompt, so a browser that could set it
  // would be writing the agent's instructions (see api/public_demo.py).
  /** Start one coordination run. A trigger name from the server's own allowlist is the
   *  entire client surface: `member_scan` asks Pool about this member's own standing
   *  declarations, `manual_scan` is the community-wide scan a scheduled pool-day
   *  invocation performs, and `manual_advance` moves blocked pools along. Which
   *  declarations, whose, and what the model is told are all derived server-side. */
  run: (trigger: "member_scan" | "manual_scan" | "manual_advance") =>
    post<RunResult>("/api/agent/run", { trigger }),
  respond: (decisionId: string, approve: boolean) =>
    post<Record<string, unknown>>(`/api/decisions/${decisionId}/respond`, { approve }),
  /** Offer to host this pool. Adds you to the candidate set; the deterministic
   *  evaluator still ranks everyone and offers the job to the best fit. */
  volunteerHost: (poolId: string, householdId: string, body: Record<string, unknown> = {}) =>
    post<{ candidates: unknown[]; note: string }>(
      `/api/pools/${poolId}/host-offer/${householdId}`,
      body,
    ),
  withdraw: (poolId: string, householdId: string) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/withdraw/${householdId}`),
  /** Open the pickup window once the order has been purchased. */
  openDistribution: (poolId: string) =>
    post<Record<string, unknown>>(`/api/pools/${poolId}/open-distribution`),
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
  /** Point every subsequent request at the showcase's own partition, or back at the
   *  visitor's. The scripted lifecycle is a different world, not a different screen. */
  setShowcaseScope,
  inShowcaseScope,

  /** What this deployment can do. Answers everywhere; `live_agent_available` is false
   *  when no AgentCore runtime is configured, so the UI describes the action rather
   *  than offering a button that cannot work. It is also what decides whether the
   *  product's discovery action goes to AWS or runs here. */
  /** What one run did about this member's own declarations. Server-assembled from the
   *  evaluation records that run wrote; the browser renders and decides nothing. */
  runReport: (runId: string, householdId: string) =>
    request<RunReport>(`/api/runs/${runId}/report?household_id=${householdId}`),

  demoConfig: () => request<DemoConfig>("/api/demo/config"),
  /** Run the deployed coordinator against *this session's* workspace. The workspace is
   *  the query parameter every request already carries; the server re-validates it and
   *  builds the runtime payload itself, so the browser names a session it already has,
   *  never one it does not. */
  /** Invoke the deployed coordinator, once, against this session.
   *
   *  `action` is a key from the server's own map, never an objective: `member` asks
   *  about this member's own declarations, `community` runs the scan a scheduled
   *  pool-day invocation performs. The server turns it into a trigger the runtime's own
   *  allowlist accepts, and builds every other field of the payload itself. */
  liveAgent: (action: "member" | "community" = "member") =>
    post<LiveAgentResult>(`/api/demo/agentcore?action=${action}`),
};

/* ------------------------------------------------------------------ formatting */

export function money(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** Basis points as a percentage, formatted exactly the way the server formats them.
 *
 *  `bps_to_pct_str` in `pool/domain/money.py` truncates the tenth digit; `toFixed(1)`
 *  rounds it. Same stored number, two formatters, and a decision card and a pool card
 *  sitting six lines apart on Home disagreeing about one purchase by 0.1 point. The
 *  arithmetic is the server's either way — this only stops the client from rendering
 *  it differently. */
export function pct(bps: number): string {
  const sign = bps < 0 ? "-" : "";
  const abs = Math.abs(bps);
  return `${sign}${Math.floor(abs / 100)}.${Math.floor((abs % 100) / 10)}%`;
}

const STATUS_COPY: Record<PoolStatus, { label: string; tone: "ok" | "warn" | "info" | "stop" }> = {
  forming: { label: "Forming", tone: "info" },
  host_recruiting: { label: "Finding a host", tone: "warn" },
  host_selected: { label: "Host confirmed", tone: "info" },
  final_offer: { label: "Final price ready", tone: "warn" },
  funding: { label: "Collecting payment", tone: "warn" },
  recovering: { label: "Repairing", tone: "warn" },
  locked: { label: "Locked", tone: "ok" },
  purchase_ready: { label: "Ready to order", tone: "ok" },
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

/** Format a calendar date without treating it as a UTC instant.
 *
 * `new Date("2026-08-28")` means midnight UTC, which is August 27 in US time zones.
 * Need dates are semantic calendar dates, so validate and format their own components
 * in UTC; no locale offset is allowed to change the day the member declared. */
export function shortDateOnly(value: string, locale?: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}
