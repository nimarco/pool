/* Screens.
 *
 * Design intent: Pool exists so people can stop paying attention to a chore, so the
 * interface should feel like a well-kept community noticeboard — legible, unhurried,
 * trustworthy. Moss means Pool acted on its own; clay means a person is needed.
 *
 * Two rules run through every view:
 *   - Every number displayed came from the server. Nothing is recomputed here, because
 *     a figure the browser invented is a figure nobody can defend (AGENTS.md §5).
 *   - Nothing identifying is ever rendered. Members appear as display names; there is
 *     no address, phone, email, or payment reference in any payload to render.
 */

import { useEffect, useState } from "react";
import {
  ActivityEvent,
  AppState,
  Checklist,
  Credential,
  Decision,
  DemoConfig,
  Health,
  LiveAgentResult,
  MapData,
  NeedRow,
  OperatorView,
  PoolView,
  RunSummary,
  ScenarioResult,
  api,
  money,
  pct,
  shortDate,
  shortTime,
  statusCopy,
} from "./api";

/* ------------------------------------------------------------------ primitives */

export function Chip({ tone, children }: { tone: string; children: React.ReactNode }) {
  const cls = tone === "ok" ? "chip-ok" : tone === "warn" ? "chip-warn" : "chip-info";
  return <span className={`chip ${cls}`}>{children}</span>;
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  );
}

function Meter({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.min(100, Math.round((value * 100) / max)) : 0;
  return (
    <div className="meter" role="img" aria-label={`${value} of ${max} units`}>
      <div className="meter-fill" style={{ width: `${width}%` }} />
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="empty">{children}</p>;
}

/* ---------------------------------------------------------------------- landing */

export function Landing({
  onEnter,
  onScenario,
  onSeeAgent,
  running,
  health,
  demoConfig,
  memberCount,
}: {
  onEnter: () => void;
  onScenario: () => void;
  onSeeAgent: () => void;
  running: boolean;
  health: Health | null;
  demoConfig: DemoConfig | null;
  memberCount: number | null;
}) {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Good Neighbor Agents</p>
        <h1 className="serif">
          Ten people wanted the same thing.
          <br />
          Nobody organised anything.
          <br />
          Pool noticed.
        </h1>
        <p className="lede">
          Students already do this informally — <em>“I can buy 50 of these cheaper, DM me
          if you want one.”</em> Someone fronts the money, guesses the demand, answers
          thirty messages, and eats the leftovers. Pool runs that job in reverse: people
          say what they routinely need, and the agent finds the group, the supplier, and
          someone to collect it.
        </p>
        <div className="btn-row">
          <button className="btn btn-primary" onClick={onScenario} disabled={running}>
            {running ? "Running the lifecycle…" : "Run the full scenario"}
          </button>
          <button className="btn" onClick={onEnter}>
            Enter Demo University
          </button>
          {demoConfig?.live_agent_available ? (
            <button className="btn" onClick={onSeeAgent}>
              Run the agent live on AWS
            </button>
          ) : null}
        </div>
        <p className="tiny muted" style={{ marginTop: "1rem" }}>
          No account, no signup, no configuration.{" "}
          {memberCount ? `${memberCount} synthetic students · ` : ""}Every figure you
          will see was computed by deterministic code on the server and stored.
        </p>
        {health ? (
          <p className="tiny muted" style={{ marginTop: "0.4rem" }}>
            Payments: {health.payment_provider} ({health.payment_mode}) · Purchase:{" "}
            {health.purchase_simulated ? "simulated" : health.purchase_executor} · Model:{" "}
            {health.model_provider} · Background schedules:{" "}
            {health.schedules_enabled ? "on" : "off"}
          </p>
        ) : null}
      </section>

      <section className="pitch">
        {[
          {
            n: "1",
            t: "Latent demand, not a group chat",
            d: "Eight students separately need protein powder. None of them posted anything. Pool finds the overlap and works out whether a bulk order is genuinely worth it.",
          },
          {
            n: "2",
            t: "Somebody has to carry the box",
            d: "Pool recruits a fulfiller from standing hosts and from the pool's own members, ranks them on capacity, distance and their own minimum pay, and offers the job to the best fit.",
          },
          {
            n: "3",
            t: "The price includes everything",
            d: "Merchandise, host pay, card processing, and Pool's own fee. Smart Join is evaluated against savings that are net of all of it — never a headline number with the costs hidden.",
          },
        ].map((item) => (
          <article key={item.n} className="pitch-item card card-pad">
            <div className="pitch-num">{item.n}</div>
            <h3>{item.t}</h3>
            <p className="small muted">{item.d}</p>
          </article>
        ))}
      </section>

      <section className="card card-pad">
        <h3>What is real here, and what is not</h3>
        <div className="grid grid-2">
          <div>
            <p className="small">
              <strong>Real:</strong> the agent loop, the demand matching, the case
              arithmetic, the host ranking, the payment state machine, the pickup
              credentials, the recovery when an authorisation fails. Every number on
              every screen was computed by deterministic code and stored.
            </p>
            {demoConfig?.live_agent_available ? (
              <p className="small" style={{ marginTop: "0.6rem" }}>
                <strong>Also real:</strong> the <em>Agent</em> tab has one button that
                genuinely invokes Pool's coordinator deployed on Amazon Bedrock
                AgentCore Runtime in {demoConfig.region}. Everything else on this site
                runs deterministically, so the demo does not depend on a paid model
                call to work.
              </p>
            ) : null}
          </div>
          <div>
            <p className="small">
              <strong>Not real:</strong> the community, the students, the suppliers, and
              the money. Supplier prices, case sizes and minimums are invented demo
              data — no wholesale relationship exists. Payments are simulated; the
              supplier purchase is simulated and labelled as such; no goods move.
              Nothing here claims traction that does not exist.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}

/* -------------------------------------------------------------------- dashboard */

export function Dashboard({
  state,
  map,
  onOpenPool,
  onRespond,
  busyDecision,
}: {
  state: AppState;
  map: MapData | null;
  onOpenPool: (id: string) => void;
  onRespond: (decisionId: string, approve: boolean) => void;
  busyDecision: string | null;
}) {
  const m = state.metrics;
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">{state.community?.name ?? "Community"}</p>
          <h2 className="serif">This week</h2>
        </div>
      </div>

      <section className="grid grid-3">
        <Stat
          label="Declared needs"
          value={String(state.counts.needs)}
          sub={`${state.counts.members} members, nobody organising`}
        />
        <Stat
          label="Pools running"
          value={String(state.pools.length)}
          sub={`${m.pools_locked_or_beyond} locked or beyond`}
        />
        <Stat
          label="Collective savings"
          value={money(m.collective_savings_cents)}
          sub="after host pay, processing and Pool's fee"
        />
      </section>

      {state.decisions.length > 0 ? (
        <section className="card">
          <div className="card-head">
            <h3>Decision Inbox</h3>
            <span className="tiny muted">{state.decisions.length} waiting</span>
          </div>
          <div className="rows">
            {state.decisions.map((d) => (
              <DecisionCard
                key={d.decision_id}
                decision={d}
                busy={busyDecision === d.decision_id}
                onRespond={onRespond}
              />
            ))}
          </div>
        </section>
      ) : (
        <section className="card card-pad">
          <h3>Decision Inbox</h3>
          <Empty>
            Nothing needs you. Pool only asks when a decision genuinely requires a person.
          </Empty>
        </section>
      )}

      <section className="grid grid-main">
        <div className="card">
          <div className="card-head">
            <h3>Pools</h3>
          </div>
          {state.pools.length === 0 ? (
            <div className="card-pad">
              <Empty>
                No pool yet. Run a background scan and Pool will look for overlapping
                demand worth acting on.
              </Empty>
            </div>
          ) : (
            <div className="rows">
              {state.pools.map((p) => (
                <PoolRow key={p.pool_id} pool={p} onOpen={() => onOpenPool(p.pool_id)} />
              ))}
            </div>
          )}
        </div>
        <div className="card card-pad">
          <h3>Community</h3>
          <CommunityMap map={map} />
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>What Pool did</h3>
        </div>
        <Feed events={state.activity} />
      </section>
    </>
  );
}

function DecisionCard({
  decision,
  busy,
  onRespond,
}: {
  decision: Decision;
  busy: boolean;
  onRespond: (id: string, approve: boolean) => void;
}) {
  const f = decision.facts as Record<string, never>;
  const breakdown = (f.cost_breakdown ?? {}) as Record<string, number>;
  const isHostOffer = decision.kind === "host_offer";

  return (
    <div className="decision">
      <div className="decision-head">
        <div>
          <div className="row-title">{decision.household_name}</div>
          <div className="tiny muted">
            {isHostOffer ? "Fulfilment job offered" : "Final price ready to approve"}
          </div>
        </div>
        {decision.expires_at ? (
          <span className="tiny muted">by {shortTime(decision.expires_at)}</span>
        ) : null}
      </div>

      {isHostOffer ? (
        <>
          <p className="decision-q">
            Collect {String(f.units)} units for {String(f.orders)} people —{" "}
            {String(f.supplier_distance_km)} km round trip. Earn{" "}
            <strong>{String(f.estimated_earnings_display)}</strong>.
          </p>
          <div className="decision-facts">
            <Fact label="Pickup window" value={shortTime(String(f.distribution_starts_at))} />
            <Fact label="Orders" value={String(f.orders)} />
            <Fact label="Units" value={String(f.units)} />
          </div>
        </>
      ) : (
        <>
          <p className="decision-q">
            {String(f.units)} × {String(f.product)} for{" "}
            <strong>{String(f.final_cost_display)}</strong> instead of{" "}
            {String(f.baseline_display)} —{" "}
            {typeof f.savings_bps === "number" ? pct(f.savings_bps) : ""} less.
          </p>
          <div className="decision-facts">
            <Fact label="Merchandise" value={money(breakdown.merchandise ?? 0)} />
            <Fact label="Host pay" value={money(breakdown.host_compensation ?? 0)} />
            <Fact label="Pool fee" value={money(breakdown.pool_fee ?? 0)} />
            <Fact label="Processing" value={money(breakdown.payment_processing ?? 0)} />
            <Fact label="Pickup" value={String(f.pickup_site)} />
            <Fact label="Walk" value={`${String(f.travel_minutes)} min`} />
          </div>
          {f.blocking_rule ? (
            <p className="why tiny">
              Pool did not decide this on its own because your rule{" "}
              <code>{String(f.blocking_rule)}</code> did not pass.
            </p>
          ) : null}
        </>
      )}

      <div className="btn-row">
        <button
          className="btn btn-accept btn-sm"
          disabled={busy}
          onClick={() => onRespond(decision.decision_id, true)}
        >
          {busy ? "…" : isHostOffer ? "Accept the job" : "Approve"}
        </button>
        <button
          className="btn btn-sm"
          disabled={busy}
          onClick={() => onRespond(decision.decision_id, false)}
        >
          Decline
        </button>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="fact-label">{label}</div>
      <div className="fact-value">{value}</div>
    </div>
  );
}

function PoolRow({ pool, onOpen }: { pool: PoolView; onOpen: () => void }) {
  const s = statusCopy(pool.status);
  return (
    <button className="row row-main" onClick={onOpen}>
      <div>
        <div className="row-title">
          {pool.product_name} <Chip tone={s.tone}>{s.label}</Chip>
        </div>
        <div className="tiny muted">
          {pool.member_count} members · {pool.provisional_units}/{pool.threshold_units} units ·{" "}
          {pool.pickup_site}
          {pool.host ? ` · host ${pool.host.display_name}` : " · host needed"}
        </div>
        <Meter value={pool.provisional_units} max={pool.threshold_units} />
      </div>
      <div className="num">
        <div className="fact-value">{pool.savings_pct || "—"}</div>
        <div className="tiny muted">{pool.is_estimate ? "estimated" : "final"}</div>
      </div>
    </button>
  );
}

function CommunityMap({ map }: { map: MapData | null }) {
  if (!map || map.members.length === 0) return <Empty>No community data yet.</Empty>;

  const points = [...map.members, ...map.sites];
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const pad = 0.002;
  const minLat = Math.min(...lats) - pad;
  const maxLat = Math.max(...lats) + pad;
  const minLon = Math.min(...lons) - pad;
  const maxLon = Math.max(...lons) + pad;
  const x = (lon: number) => ((lon - minLon) / (maxLon - minLon || 1)) * 100;
  const y = (lat: number) => (1 - (lat - minLat) / (maxLat - minLat || 1)) * 100;

  return (
    <div className="map-wrap">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Community map">
        {map.sites.map((s) => (
          <g key={s.id}>
            <rect
              x={x(s.lon) - 1.6}
              y={y(s.lat) - 1.6}
              width="3.2"
              height="3.2"
              fill="var(--slate)"
              opacity="0.9"
            />
          </g>
        ))}
        {map.members.map((m) => (
          <circle
            key={m.id}
            cx={x(m.lon)}
            cy={y(m.lat)}
            r={m.in_pool ? 1.5 : 1}
            fill={m.in_pool ? "var(--moss)" : "var(--ink-faint)"}
            opacity={m.in_pool ? 0.95 : 0.5}
          />
        ))}
      </svg>
      <div className="map-legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--moss)" }} /> in a pool
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--ink-faint)" }} /> declared a
          need
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--slate)" }} /> pickup site
        </span>
      </div>
      <p className="tiny muted">{map.note}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ pool detail */

export function PoolDetail({
  pool,
  onBack,
  onRefresh,
}: {
  pool: PoolView;
  onBack: () => void;
  onRefresh: () => void;
}) {
  const s = statusCopy(pool.status);
  const e = pool.economics;
  const [credential, setCredential] = useState<Credential | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <div className="page-head">
        <div>
          <button className="btn btn-sm" onClick={onBack}>
            ← Back
          </button>
          <h2 className="serif" style={{ marginTop: "0.6rem" }}>
            {pool.product_name} <Chip tone={s.tone}>{s.label}</Chip>
          </h2>
          <p className="small muted">
            {pool.brand ? `${pool.brand} · ` : ""}
            {pool.supplier} · pickup at {pool.pickup_site}
            {pool.pickup_permission ? ` (${pool.pickup_permission})` : ""}
          </p>
        </div>
      </div>

      {pool.failure_reason ? (
        <div className="banner banner-warn">{pool.failure_reason}</div>
      ) : null}

      <section className="grid grid-3">
        <Stat
          label="Units"
          value={`${pool.provisional_units} / ${pool.threshold_units}`}
          sub={`${pool.funded_units} funded`}
        />
        <Stat
          label={pool.is_estimate ? "Estimated saving" : "Net saving"}
          value={pool.savings_pct || "—"}
          sub={pool.is_estimate ? "host pay not yet fixed" : "after every cost"}
        />
        <Stat
          label="Host"
          value={pool.host ? pool.host.display_name : "Recruiting"}
          sub={pool.host ? `${pool.host.reward_display} for ${pool.host.handled_orders} orders` : ""}
        />
      </section>

      {e ? (
        <section className="card card-pad">
          <h3>Where the money goes</h3>
          <p className="small muted">
            {e.host_is_estimated
              ? "Host pay is still an estimate — a candidate pool shows a range, not a precise-looking price."
              : "Every component is fixed. This is what buyers actually pay."}
          </p>
          <div className="rows">
            <CostLine label="Bulk merchandise" cents={e.merchandise_cents} />
            <CostLine label="Host / runner compensation" cents={e.host_compensation_cents} />
            <CostLine label="Payment processing" cents={e.payment_processing_cents} />
            <CostLine label="Pool platform fee" cents={e.platform_fee_cents} />
            <CostLine label="All-in Pool cost" cents={e.all_in_cents} strong />
            <CostLine label="Buying alone at retail" cents={e.retail_baseline_cents} />
            <CostLine label="Net saving" cents={e.net_savings_cents} strong accent />
          </div>
          <p className="tiny muted">
            {e.packages.cases} case(s) of {e.packages.case_units} ={" "}
            {e.packages.units_purchased} units for {e.packages.total_units} ordered.{" "}
            {e.packages.surplus_resolved
              ? "Nothing left over — Pool does not buy stock nobody ordered."
              : `${e.packages.surplus_units} unit(s) unallocated, which blocks the lock.`}
          </p>
        </section>
      ) : null}

      {pool.viability ? (
        <section className="card card-pad">
          <h3>Viability</h3>
          <p className="small muted">
            A pool only locks when it works for the buyers, the supplier, the host, and
            Pool itself.
          </p>
          <div className="rows">
            {pool.viability.checks.map((c) => (
              <div key={c.name} className="feed-line">
                <span className={`dot ${c.passed ? "chip-ok" : "chip-warn"}`} />
                <span className="small">
                  <strong>{c.name.replace(/_/g, " ")}</strong> — {c.detail}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {pool.host_candidates && pool.host_candidates.length > 0 ? (
        <section className="card card-pad">
          <h3>Host candidates</h3>
          <p className="small muted">
            Offering to host adds you to the candidate set. It does not claim the job —
            Pool ranks everyone and offers the work to the best fit.
          </p>
          <div className="rows">
            {pool.host_candidates.map((c) => (
              <div key={c.household_id} className="row">
                <div>
                  <div className="row-title">
                    {c.display_name}{" "}
                    <Chip tone={c.eligible ? "ok" : "warn"}>
                      {c.eligible ? c.state : "not eligible"}
                    </Chip>
                  </div>
                  <div className="tiny muted">
                    {c.source === "standing" ? "standing host" : "volunteered for this pool"} ·{" "}
                    {c.supplier_distance_km} km · {c.estimated_reward_display}
                  </div>
                  {c.ineligible_reasons.length > 0 ? (
                    <div className="tiny muted">{c.ineligible_reasons.join("; ")}</div>
                  ) : (
                    <div className="tiny mono muted">
                      {Object.entries(c.score_components)
                        .map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`)
                        .join("  ")}
                    </div>
                  )}
                </div>
                <div className="num">
                  <div className="fact-value">{c.score}</div>
                  <div className="tiny muted">score</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="card">
        <div className="card-head">
          <h3>Members</h3>
          <span className="tiny muted">display names only — no contact details</span>
        </div>
        <div className="rows">
          {(pool.members ?? []).map((m) => (
            <div key={m.household_id} className="row">
              <div>
                <div className="row-title">
                  {m.display_name}
                  {m.is_host ? <Chip tone="info">host</Chip> : null}
                  {m.path === "smart_join" ? <Chip tone="ok">Smart Join</Chip> : null}
                  {m.state === "authorization_failed" ? (
                    <Chip tone="warn">payment declined</Chip>
                  ) : null}
                </div>
                <div className="tiny muted">
                  {m.units} units · {m.travel_minutes} min walk · {m.state.replace(/_/g, " ")}
                </div>
              </div>
              <div className="num">
                <div className="fact-value">{m.final_cost_display || m.estimated_cost_display}</div>
                <div className="tiny muted">
                  {m.savings_pct ? `${m.savings_pct} off` : "estimated"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {pool.status === "distributing" || pool.status === "completed" ? (
        <section className="card card-pad">
          <h3>Pickup</h3>
          <p className="small muted">
            Each buyer gets a one-time credential bound to this pool. Only its hash is
            stored, and issuing a new one invalidates the old.
          </p>
          {(pool.members ?? []).slice(0, 1).map((m) => (
            <div key={m.household_id} className="btn-row">
              <button
                className="btn btn-sm"
                onClick={async () => {
                  try {
                    setCredential(await api.issueCredential(pool.pool_id, m.household_id));
                    setError(null);
                    onRefresh();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                Show {m.display_name}'s pickup code
              </button>
            </div>
          ))}
          {error ? <p className="tiny muted">{error}</p> : null}
          {credential ? (
            <div className="card-pad" style={{ background: "var(--paper-sunken)" }}>
              <div className="fact-label">One-time code</div>
              <div className="serif" style={{ fontSize: "1.8rem", letterSpacing: "0.15em" }}>
                {credential.code}
              </div>
              <p className="tiny muted">
                Works once. {credential.replaced_previous ? "The previous code is now void." : ""}
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {pool.announcements && pool.announcements.length > 0 ? (
        <section className="card card-pad">
          <h3>Updates</h3>
          <div className="rows">
            {pool.announcements.map((a) => (
              <div key={a.id} className="feed-line">
                <span className="small">{a.body}</span>
                <span className="tiny muted">{a.author}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}

function CostLine({
  label,
  cents,
  strong,
  accent,
}: {
  label: string;
  cents: number;
  strong?: boolean;
  accent?: boolean;
}) {
  return (
    <div className="row">
      <div className={strong ? "row-title" : "small"}>{label}</div>
      <div
        className="num fact-value"
        style={accent ? { color: "var(--moss)" } : undefined}
      >
        {money(cents)}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------ needs */

export function Needs({ needs }: { needs: NeedRow[] }) {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Recurring needs</p>
          <h2 className="serif">What people said they buy anyway</h2>
          <p className="small muted">
            This is the only thing a member has to do. Two timing numbers do different
            jobs: <strong>restock lead</strong> is when they normally buy;{" "}
            <strong>flexibility</strong> is how much earlier they authorised Pool to buy
            if it saves money. Only the second one lets Pool pull demand forward.
          </p>
        </div>
      </div>
      <section className="card">
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Member</th>
                <th>Product</th>
                <th className="r">Qty</th>
                <th>Needs it by</th>
                <th className="r">Restock lead</th>
                <th className="r">Will buy early</th>
                <th className="r">Min saving</th>
                <th className="r">Max spend</th>
              </tr>
            </thead>
            <tbody>
              {needs.map((n) => (
                <tr key={n.need_id}>
                  <td>{n.household_name}</td>
                  <td>{n.product_name}</td>
                  <td className="r">
                    {n.quantity} {n.unit}
                  </td>
                  <td>{shortDate(n.expected_next_need_date)}</td>
                  <td className="r">{n.routine_lead_days}d</td>
                  <td className="r">{n.flexibility_days}d</td>
                  <td className="r">{n.min_savings_pct}%</td>
                  <td className="r">{n.max_spend_display}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

/* --------------------------------------------------------------------- host view */

export function HostConsole({ poolId }: { poolId: string | null }) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [scan, setScan] = useState("");
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    if (!poolId) return;
    api.checklist(poolId).then(setChecklist).catch(() => setChecklist(null));
  }, [poolId]);

  if (!poolId || !checklist) {
    return (
      <>
        <div className="page-head">
          <div>
            <p className="eyebrow">Host</p>
            <h2 className="serif">Fulfilment job</h2>
          </div>
        </div>
        <Empty>No active fulfilment job. Run the scenario to see one end to end.</Empty>
      </>
    );
  }

  const earnings = checklist.earnings as Record<string, string>;
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Host</p>
          <h2 className="serif">{checklist.product_name}</h2>
          <p className="small muted">
            {shortTime(checklist.distribution_starts_at)} –{" "}
            {shortTime(checklist.distribution_ends_at)}
          </p>
        </div>
      </div>

      <section className="grid grid-3">
        <Stat
          label="Collected"
          value={`${checklist.picked_up} / ${checklist.total}`}
          sub={`${checklist.units_total} units`}
        />
        <Stat label="Your earnings" value={earnings.total_display ?? "—"} sub="buyer-funded" />
        <Stat
          label="Earned so far"
          value={money(Number(earnings.paid_cents ?? 0))}
          sub="a no-show does not erase the run"
        />
      </section>

      <section className="card card-pad">
        <h3>Confirm a handoff</h3>
        <p className="small muted">
          Type the buyer's one-time code. The server checks it — you cannot mark an order
          collected without one.
        </p>
        <div className="btn-row">
          <input
            className="btn"
            style={{ minWidth: "12rem", fontFamily: "var(--mono)" }}
            value={scan}
            placeholder="e.g. 4KQ7WMTX"
            onChange={(ev) => setScan(ev.target.value)}
          />
          <button
            className="btn btn-primary btn-sm"
            onClick={async () => {
              const outcome = await api.redeem(poolId, scan, true);
              setResult(outcome.ok ? "Handoff confirmed." : outcome.reason);
              setScan("");
              api.checklist(poolId).then(setChecklist).catch(() => undefined);
            }}
          >
            Confirm
          </button>
        </div>
        {result ? <p className="small">{result}</p> : null}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>Orders</h3>
        </div>
        <div className="rows">
          {checklist.orders.map((o) => (
            <div key={o.household_id} className="row">
              <div>
                <div className="row-title">
                  {o.state === "picked_up" ? "✓ " : "○ "}
                  {o.display_name}
                </div>
                <div className="tiny muted">
                  {o.units} units · {o.state.replace(/_/g, " ")}
                  {o.via ? ` · via ${o.via}` : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

/* ----------------------------------------------------------------- operator view */

export function Operator() {
  const [data, setData] = useState<OperatorView | null>(null);
  useEffect(() => {
    api.operator().then(setData).catch(() => setData(null));
  }, []);
  if (!data) return <Empty>Loading operator console…</Empty>;

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Operator</p>
          <h2 className="serif">Supply, money, and exceptions</h2>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h3>Supplier offers</h3>
          <span className="tiny muted">a final price may never rest on a stale quote</span>
        </div>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Offer</th>
                <th>Supplier</th>
                <th className="r">Unit</th>
                <th className="r">Case</th>
                <th>MOQ</th>
                <th className="r">Verified</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {data.offers.map((o) => (
                <tr key={o.offer_id}>
                  <td className="mono tiny">{o.offer_id}</td>
                  <td>{o.supplier}</td>
                  <td className="r">{o.unit_price_display}</td>
                  <td className="r">{o.case_units}</td>
                  <td>{o.moq}</td>
                  <td className="r">{o.age_hours}h ago</td>
                  <td>
                    <Chip tone={o.source === "manual_verified" ? "ok" : "info"}>{o.source}</Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.pools.map((p) => (
        <section key={p.pool_id} className="card card-pad">
          <h3>
            {p.product_name} <Chip tone={statusCopy(p.status).tone}>{p.status}</Chip>
          </h3>
          {p.payments.length > 0 ? (
            <div className="rows">
              {p.payments.map((pay) => (
                <div key={pay.payment_id} className="row">
                  <div>
                    <div className="row-title">{pay.household_name}</div>
                    <div className="tiny muted">
                      {pay.state.replace(/_/g, " ")} · {pay.provider} ({pay.provider_mode})
                      {pay.failure_code ? ` · ${pay.failure_code}` : ""}
                    </div>
                  </div>
                  <div className="num fact-value">{pay.amount_display}</div>
                </div>
              ))}
            </div>
          ) : (
            <Empty>No authorisations yet.</Empty>
          )}
          {p.purchase ? (
            <p className="tiny muted">
              Purchase {String(p.purchase.supplier_reference)} —{" "}
              {p.purchase.simulated ? "SIMULATED" : "real"},{" "}
              {String(p.purchase.cases_purchased)} case(s) ={" "}
              {String(p.purchase.units_purchased)} units,{" "}
              {money(Number(p.purchase.total_cents ?? 0))}
            </p>
          ) : null}
        </section>
      ))}

      {data.issues.length > 0 ? (
        <section className="card card-pad">
          <h3>Issue cases</h3>
          <div className="rows">
            {data.issues.map((i) => (
              <div key={String(i.id)} className="row">
                <div>
                  <div className="row-title">{String(i.kind).replace(/_/g, " ")}</div>
                  <div className="tiny muted">
                    {String(i.household_name)} · {String(i.state)} · {String(i.detail)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}

/* ---------------------------------------------------------------------- agent */

/* ------------------------------------------------------------------ live agent */

/** The one action on this site that leaves the browser's own demo behind.
 *
 * It is deliberately separate from everything else: the deterministic demo must not
 * depend on a paid cloud call to work, and a judge must be able to tell which is
 * which. There is no fallback that fabricates a run — if the invocation fails, this
 * says so (AGENTS.md §8).
 */
export function LiveAgent({
  config,
  result,
  busy,
  onRun,
}: {
  config: DemoConfig;
  result: LiveAgentResult | null;
  busy: boolean;
  onRun: () => void;
}) {
  if (!config.live_agent_available) return null;
  return (
    <section className="card">
      <div className="card-head">
        <h3>Run it live on AWS</h3>
        <span className="spacer" />
        <Chip tone="warn">live</Chip>
      </div>
      <div className="card-pad">
        <p className="small">
          Everything else here runs deterministically on the server. This button does
          something different: it invokes Pool's coordinator as deployed on{" "}
          <strong>Amazon Bedrock AgentCore Runtime</strong> in {config.region} — a real
          model, the real Strands loop, the real Pool tools, inside its own isolated
          runtime session.
        </p>
        <p className="small muted">
          The runtime seeds its own copy of Demo University, so this does not change
          anything on the pages around it. Limited to {config.max_live_per_session} runs
          per visitor, because it spends model tokens.
        </p>
        <div className="btn-row" style={{ marginTop: "0.9rem" }}>
          <button className="btn btn-primary" onClick={onRun} disabled={busy}>
            {busy ? "Invoking AgentCore…" : "Run the deployed agent"}
          </button>
        </div>

        {result && !result.ok ? (
          <div className="banner banner-warn" style={{ marginTop: "1rem" }}>
            {result.reason}
          </div>
        ) : null}
      </div>

      {result && result.ok ? (
        <>
          <div className="card-head">
            <h3>
              {result.service} <Chip tone="ok">{result.run.outcome}</Chip>
            </h3>
          </div>
          <div className="card-pad">
            <div className="decision-facts">
              <div>
                <div className="fact-label">Runtime</div>
                <div className="fact-value mono">{result.runtime}</div>
              </div>
              <div>
                <div className="fact-label">Region</div>
                <div className="fact-value mono">{result.region}</div>
              </div>
              <div>
                <div className="fact-label">Model</div>
                <div className="fact-value mono">{result.run.model_id}</div>
              </div>
              <div>
                <div className="fact-label">Iterations</div>
                <div className="fact-value num">{result.run.iterations}</div>
              </div>
              <div>
                <div className="fact-label">Tokens in / out</div>
                <div className="fact-value num">
                  {result.run.input_tokens ?? 0} / {result.run.output_tokens ?? 0}
                </div>
              </div>
              <div>
                <div className="fact-label">Agent time</div>
                <div className="fact-value num">{result.run.duration_ms ?? 0} ms</div>
              </div>
              <div>
                <div className="fact-label">Round trip</div>
                <div className="fact-value num">{result.wall_ms} ms</div>
              </div>
              <div>
                <div className="fact-label">Stopped because</div>
                <div className="fact-value mono">{result.run.termination_reason}</div>
              </div>
            </div>
          </div>
          <div className="trace">
            {result.run.tool_calls.length === 0 ? (
              <div className="card-pad">
                <Empty>The agent called no tools on this run.</Empty>
              </div>
            ) : (
              result.run.tool_calls.map((t, i) => (
                <span key={`${result.run.run_id}-${i}`} className="trace-step">
                  <span className="trace-idx">{i + 1}</span>
                  <span className="trace-name mono">{t.name}</span>
                  <span className="trace-summary">
                    {t.ok ? t.summary : `refused — ${t.summary}`}
                  </span>
                  {t.ok ? null : <Chip tone="warn">refused</Chip>}
                </span>
              ))
            )}
          </div>
          <div className="card-pad">
            <p className="tiny muted">{result.note}</p>
          </div>
        </>
      ) : null}
    </section>
  );
}

export function AgentRuns({
  runs,
  activity,
  live,
}: {
  runs: RunSummary[];
  activity: ActivityEvent[];
  live?: React.ReactNode;
}) {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Agent</p>
          <h2 className="serif">Every run, and why it stopped</h2>
          <p className="small muted">
            Tool names, counters, and a termination reason. No model reasoning text is
            stored — the trace shows what the agent <em>did</em>, and every value it acted
            on came from a deterministic tool.
          </p>
        </div>
      </div>

      {live}

      <section className="card">
        <div className="card-head">
          <h3>Runs</h3>
        </div>
        {runs.length === 0 ? (
          <div className="card-pad">
            <Empty>No runs yet.</Empty>
          </div>
        ) : (
          <div className="rows">
            {runs.map((r) => (
              <div key={r.run_id} className="row">
                <div>
                  <div className="row-title">
                    {r.trigger}{" "}
                    <Chip tone={r.outcome.startsWith("pool") ? "ok" : "info"}>{r.outcome}</Chip>
                  </div>
                  <div className="tiny muted">
                    {r.iterations} iterations · {r.tool_calls.length} tool calls ·{" "}
                    {r.termination_reason} · {r.model_provider}
                    {r.duration_ms !== null ? ` · ${r.duration_ms} ms` : ""} ·{" "}
                    {r.input_tokens ?? 0}/{r.output_tokens ?? 0} tokens
                  </div>
                  <div className="trace">
                    {r.tool_calls.map((name, i) => (
                      <span key={`${r.run_id}-${i}`} className="trace-step">
                        <span className="trace-idx">{i + 1}</span>
                        <span className="trace-name mono">{name}</span>
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>Activity</h3>
        </div>
        <Feed events={activity} />
      </section>
    </>
  );
}

function Feed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="card-pad">
        <Empty>Nothing has happened yet.</Empty>
      </div>
    );
  }
  return (
    <div className="feed">
      {events.map((e) => (
        <div key={e.id} className="feed-item">
          <div className="feed-rail">
            <span className="feed-node" />
          </div>
          <div className="feed-body">
            <div className="feed-text">{e.summary}</div>
            <div className="feed-meta tiny muted">
              {e.kind.replace(/_/g, " ")} · {shortTime(e.at)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------------- impact */

export function Impact({ state }: { state: AppState }) {
  const m = state.metrics;
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Impact</p>
          <h2 className="serif">Computed from records, not claimed</h2>
          <p className="small muted">
            Every figure below is a sum over stored rows in this synthetic demo. None of
            it is traction, a projection, or a marketing number.
          </p>
        </div>
      </div>

      <section className="grid grid-3">
        <Stat
          label="Buying alone"
          value={money(m.estimated_retail_spend_cents)}
          sub="what these members would have paid individually"
        />
        <Stat
          label="All-in Pool cost"
          value={money(m.pool_spend_cents)}
          sub="merchandise, host pay, processing, Pool fee"
        />
        <Stat
          label="Collective saving"
          value={money(m.collective_savings_cents)}
          sub={`${money(m.average_buyer_savings_cents)} each on average`}
        />
      </section>

      <section className="grid grid-2">
        <div className="card card-pad">
          <h3>Where the money went</h3>
          <div className="rows">
            <CostLine label="Merchandise to the supplier" cents={m.merchandise_cents} />
            <CostLine label="Compensation to hosts" cents={m.host_compensation_cents} />
            <CostLine label="Card processing" cents={m.payment_processing_cents} />
            <CostLine label="Pool's transparent fee" cents={m.platform_fee_cents} />
          </div>
        </div>
        <div className="card card-pad">
          <h3>Coordination</h3>
          <div className="rows">
            <div className="row">
              <div className="small">Actions Pool took on its own</div>
              <div className="num fact-value">{m.coordination_actions_automated}</div>
            </div>
            <div className="row">
              <div className="small">Times a human was asked</div>
              <div className="num fact-value">{m.human_decisions_requested}</div>
            </div>
            <div className="row">
              <div className="small">Commitments made without asking</div>
              <div className="num fact-value">{m.commitments_without_asking}</div>
            </div>
            <div className="row">
              <div className="small">Pools repaired after a failure</div>
              <div className="num fact-value">{m.pools_recovered}</div>
            </div>
            <div className="row">
              <div className="small">Handoffs confirmed</div>
              <div className="num fact-value">
                {m.pickups_completed}/{m.pickups_expected}
              </div>
            </div>
          </div>
        </div>
      </section>

      <p className="tiny muted">
        Synthetic demo data. Bulk pricing normally favours whoever can afford a larger
        upfront purchase and has somewhere to put it; the point of pooling is to reach
        that pricing without each person carrying the capital, quantity, storage, and
        coordination alone.
      </p>
    </>
  );
}

/* -------------------------------------------------------------------- scenario */

/** One readable line of evidence per step.
 *
 * Deliberately drops nested structures rather than dumping them: the panel is meant to
 * let someone *follow* the run, and a wall of JSON is the opposite of that. The full
 * detail is still on the pool and agent screens.
 */
function scenarioFacts(facts: Record<string, unknown>): string {
  return Object.entries(facts)
    .filter(([, v]) => v !== null && v !== "" && typeof v !== "object")
    .slice(0, 7)
    .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`)
    .join("  ·  ");
}

export function ScenarioPanel({
  scenario,
  onClose,
}: {
  scenario: ScenarioResult;
  onClose: () => void;
}) {
  return (
    <section className="card card-pad">
      <div className="card-head">
        <h3>
          Full scenario{" "}
          <Chip tone={scenario.ok ? "ok" : "warn"}>{scenario.ok ? "completed" : "failed"}</Chip>
        </h3>
        <button className="btn btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      {!scenario.ok ? <div className="banner banner-warn">{scenario.failure}</div> : null}
      <div className="feed">
        {scenario.steps.map((step, i) => (
          <div key={`${step.name}-${i}`} className="feed-item">
            <div className="feed-rail">
              <span className="feed-node" />
            </div>
            <div className="feed-body">
              <div className="feed-text">{step.detail}</div>
              <div className="feed-meta tiny mono muted">{scenarioFacts(step.facts)}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
