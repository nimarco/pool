import { useMemo, useState } from "react";
import {
  ActivityItem,
  AppState,
  Decision,
  Health,
  MapData,
  Metrics,
  NeedRow,
  PoolView,
  RunSummary,
  STATUS_LABEL,
  api,
  money,
  relativeTime,
  statusTone,
} from "./api";

/* ------------------------------------------------------------------ primitives */

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      <span className="small">{body}</span>
    </div>
  );
}

function Meter({ value, threshold }: { value: number; threshold: number }) {
  const pct = threshold > 0 ? Math.min(100, (value / threshold) * 100) : 0;
  const short = value < threshold;
  return (
    <div
      className="meter"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={threshold}
      aria-label={`${value} of ${threshold} units committed`}
    >
      <div className={`meter-fill${short ? " short" : ""}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ------------------------------------------------------------------ landing */

export function Landing({ onStart, health }: { onStart: () => void; health: Health | null }) {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Good Neighbor Agents</p>
        <h1>Seven neighbours needed the same thing. None of them knew.</h1>
        <p className="lede">
          Buying in bulk is cheaper. Organising a group to do it is work — recruiting people,
          splitting quantities, comparing prices, arranging pickup, chasing replies, and
          starting over when someone drops out. That work is why neighbourhood buying clubs
          mostly don't exist.
        </p>
        <p className="lede">
          Pool removes the organiser. Households say what they routinely buy, once. Pool
          watches for overlap in the background, works out whether a bulk purchase is
          actually worth it, solves the logistics, forms the group, and repairs it when
          things go wrong — surfacing only the decisions that genuinely need a person.
        </p>
        <div className="btn-row">
          <button className="btn btn-primary" onClick={onStart}>
            Open the neighbourhood
          </button>
        </div>
      </section>

      <section className="pitch">
        <div className="pitch-item">
          <div className="pitch-num">1</div>
          <h3>You declare, once</h3>
          <p>
            “About 15 lb of rice every six weeks. At least 25% cheaper than retail. Nothing
            over $30. Pickup within 10 minutes.” Then you close the app.
          </p>
        </div>
        <div className="pitch-item">
          <div className="pitch-num">2</div>
          <h3>Pool finds the overlap</h3>
          <p>
            Nobody posted a listing. Pool notices that several nearby households have
            compatible demand, checks whether aggregating it clears a supplier's minimum, and
            prices the result exactly.
          </p>
        </div>
        <div className="pitch-item">
          <div className="pitch-num">3</div>
          <h3>It only asks when it must</h3>
          <p>
            Within the limits you set, Pool commits on your behalf. Outside them, it asks —
            once, with the numbers already worked out. When someone drops out, it tries to
            repair the group before disturbing anyone.
          </p>
        </div>
      </section>

      <div className="banner" style={{ marginTop: 34 }}>
        <div>
          <strong>This is a demonstration.</strong> Every household, supplier, price, and
          pickup site below is synthetic. No real purchase is made and no payment is taken.
          {health && (
            <>
              {" "}
              The coordinator currently runs on <code className="mono">{health.model_provider}</code>
              {health.model_provider === "offline" &&
                " — a deterministic planner that exercises the real agent loop without spending model tokens."}
            </>
          )}
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ decisions */

function decisionQuestion(d: Decision): string {
  const f = d.facts;
  const pct = f.savings_bps != null ? (f.savings_bps / 100).toFixed(1) : "—";
  if (f.is_exact_product === false) {
    return `A substitute ${f.product ?? "item"} would save ${pct}% — but it isn't your usual choice.`;
  }
  if (f.context === "replacement_for_dropout") {
    return `A ${f.product ?? "group"} pool has room after a dropout — ${pct}% below retail.`;
  }
  return `Pool found a ${f.product ?? "group"} buy that saves you ${pct}%.`;
}

export function DecisionInbox({
  decisions,
  onRespond,
  busy,
}: {
  decisions: Decision[];
  onRespond: (id: string, approve: boolean) => void;
  busy: string | null;
}) {
  return (
    <section className="card" aria-labelledby="inbox-h">
      <div className="card-head">
        <h2 id="inbox-h">Decision inbox</h2>
        <span className="chip chip-warn">
          <span className="dot" />
          {decisions.length} need{decisions.length === 1 ? "s" : ""} you
        </span>
      </div>
      {decisions.length === 0 ? (
        <Empty
          title="Nothing needs you"
          body="Pool is working in the background. It will only appear here when a decision genuinely requires a person."
        />
      ) : (
        decisions.map((d) => {
          const failed = (d.facts.policy_checks ?? []).filter((c) => !c.passed);
          return (
            <article className="decision" key={d.decision_id}>
              <div className="decision-head">
                <span className="chip chip-info">{d.household_name}</span>
                <span className="tiny faint">{relativeTime(d.created_at)}</span>
              </div>
              <p className="decision-q">{decisionQuestion(d)}</p>

              <div className="decision-facts">
                <div>
                  <div className="fact-label">Your share</div>
                  <div className="fact-value">{d.facts.cost_display ?? "—"}</div>
                </div>
                <div>
                  <div className="fact-label">Quantity</div>
                  <div className="fact-value">{d.facts.units ?? "—"}</div>
                </div>
                <div>
                  <div className="fact-label">Pickup</div>
                  <div className="fact-value">{d.facts.travel_minutes ?? "—"} min</div>
                </div>
                <div>
                  <div className="fact-label">By</div>
                  <div className="fact-value">{d.facts.pickup_by ?? "—"}</div>
                </div>
              </div>

              <p className="tiny muted">
                Pickup at {d.facts.pickup_site ?? "a public site"}.
              </p>

              {failed.length > 0 && (
                <p className="why">
                  <strong>Why you're being asked: </strong>
                  {failed.map((c) => c.detail).join("; ")}.
                </p>
              )}

              <div className="btn-row" style={{ marginTop: 14 }}>
                <button
                  className="btn btn-accept btn-sm"
                  disabled={busy === d.decision_id}
                  onClick={() => onRespond(d.decision_id, true)}
                >
                  {busy === d.decision_id && <span className="spin" />}
                  Join
                </button>
                <button
                  className="btn btn-sm"
                  disabled={busy === d.decision_id}
                  onClick={() => onRespond(d.decision_id, false)}
                >
                  Skip
                </button>
              </div>
            </article>
          );
        })
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ pools */

export function PoolCard({ pool, onOpen }: { pool: PoolView; onOpen: () => void }) {
  return (
    <article className="card">
      <div className="card-head">
        <h2>{pool.product_name}</h2>
        <span className={`chip ${statusTone(pool.status)}`}>
          <span className="dot" />
          {STATUS_LABEL[pool.status]}
        </span>
        <span className="spacer" />
        <button className="btn btn-sm" onClick={onOpen}>
          Details
        </button>
      </div>
      <div className="card-pad">
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 14 }}>
          <div>
            <div className="stat-label">Group saves</div>
            <div className="serif num" style={{ fontSize: 24, fontWeight: 600 }}>
              {pool.savings_display}
            </div>
            <div className="tiny muted">{pool.savings_pct} below retail</div>
          </div>
          <div>
            <div className="stat-label">Households</div>
            <div className="serif num" style={{ fontSize: 24, fontWeight: 600 }}>
              {pool.committed_count}
            </div>
            <div className="tiny muted">{pool.member_count} involved</div>
          </div>
          <div>
            <div className="stat-label">Pickup</div>
            <div className="serif num" style={{ fontSize: 24, fontWeight: 600 }}>
              {pool.avg_travel_minutes}m
            </div>
            <div className="tiny muted">average travel</div>
          </div>
        </div>

        <Meter value={pool.committed_units} threshold={pool.threshold_units} />
        <div
          className="tiny muted"
          style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}
        >
          <span className="num">
            {pool.committed_units} / {pool.threshold_units} {pool.unit} toward the supplier minimum
          </span>
          <span>{pool.pickup_site}</span>
        </div>
      </div>
    </article>
  );
}

export function PoolDetail({
  pool,
  onBack,
  onWithdraw,
  busy,
}: {
  pool: PoolView;
  onBack: () => void;
  onWithdraw: (householdId: string) => void;
  busy: boolean;
}) {
  const committed = pool.members.filter((m) => m.state === "committed");
  const largest = committed.reduce<typeof committed[number] | null>(
    (best, m) => (best === null || m.units > best.units ? m : best),
    null,
  );

  return (
    <>
      <div className="page-head">
        <button className="btn btn-sm" onClick={onBack} style={{ marginBottom: 12 }}>
          ← All pools
        </button>
        <h1>{pool.product_name}</h1>
        <p>
          {pool.supplier} · pickup at {pool.pickup_site} by {pool.deadline} ·{" "}
          <span className={`chip ${statusTone(pool.status)}`}>{STATUS_LABEL[pool.status]}</span>
        </p>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <Stat
          label="Group savings"
          value={pool.savings_display}
          sub={`${pool.savings_pct} below buying alone`}
        />
        <Stat
          label="Committed"
          value={`${pool.committed_units}/${pool.threshold_units}`}
          sub={`${pool.unit} against the supplier minimum`}
        />
        <Stat
          label="Average travel"
          value={`${pool.avg_travel_minutes} min`}
          sub={pool.pickup_is_public ? "public pickup site" : "private pickup site"}
        />
      </div>

      <section className="card" style={{ marginBottom: 18 }}>
        <div className="card-head">
          <h2>Why this pool exists</h2>
        </div>
        <div className="card-pad small muted">
          <p>
            {pool.member_count} households had separately declared a need for{" "}
            {pool.product_name.toLowerCase()} within reach of {pool.pickup_site}. Individually
            they would pay {money(pool.baseline_cents)} in total at retail. Aggregated, their
            demand clears {pool.supplier}'s {pool.threshold_units}-{pool.unit} minimum, bringing
            the group cost to {money(pool.cost_cents)}.
          </p>
          <p style={{ marginTop: 8 }}>
            Every figure on this page is computed by Pool's pricing tools from the stored offer
            and the committed quantities — none of it is generated text.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Participants</h2>
          <span className="spacer" />
          <span className="tiny faint">
            Names only — Pool never shows a household's address
          </span>
        </div>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Household</th>
                <th className="r">Qty</th>
                <th className="r">Share</th>
                <th className="r">Alone</th>
                <th className="r">Saves</th>
                <th className="r">Travel</th>
                <th>How they joined</th>
              </tr>
            </thead>
            <tbody>
              {pool.members.map((m) => (
                <tr key={m.household_id} style={{ opacity: m.state === "withdrawn" ? 0.45 : 1 }}>
                  <td>
                    <div className="row-title">{m.display_name}</div>
                    <div className="tiny faint">{m.neighborhood}</div>
                  </td>
                  <td className="r num">{m.units}</td>
                  <td className="r num">{m.cost_display}</td>
                  <td className="r num faint">{m.baseline_display}</td>
                  <td className="r num">{m.savings_pct}</td>
                  <td className="r num">{m.travel_minutes}m</td>
                  <td>
                    {m.state === "withdrawn" ? (
                      <span className="chip">Withdrew</span>
                    ) : m.state === "declined" ? (
                      <span className="chip">Declined</span>
                    ) : m.path === "smart_join" ? (
                      <span className="chip chip-ok">
                        <span className="dot" />
                        Smart Join
                      </span>
                    ) : m.path === "human_approved" ? (
                      <span className="chip chip-info">Approved</span>
                    ) : (
                      <span className="chip chip-warn">
                        <span className="dot" />
                        Awaiting reply
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {largest && (
        <section className="card" style={{ marginTop: 18 }}>
          <div className="card-head">
            <h2>Demo control</h2>
          </div>
          <div className="card-pad">
            <p className="small muted" style={{ marginBottom: 12 }}>
              Simulate the failure this product exists to survive: remove the largest
              participant and drop the pool below the supplier minimum. Then run the
              coordinator and watch it repair the group.
            </p>
            <button
              className="btn btn-sm"
              disabled={busy}
              onClick={() => onWithdraw(largest.household_id)}
            >
              {busy && <span className="spin" />}
              Withdraw {largest.display_name} ({largest.units} {pool.unit})
            </button>
          </div>
        </section>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ map */

export function NeighborhoodMap({ data }: { data: MapData }) {
  const geometry = useMemo(() => {
    const pts = [
      ...data.households.map((h) => ({ lat: h.lat, lon: h.lon })),
      ...data.sites.map((s) => ({ lat: s.lat, lon: s.lon })),
    ];
    if (pts.length === 0) return null;
    const pad = 0.006;
    const minLat = Math.min(...pts.map((p) => p.lat)) - pad;
    const maxLat = Math.max(...pts.map((p) => p.lat)) + pad;
    const minLon = Math.min(...pts.map((p) => p.lon)) - pad;
    const maxLon = Math.max(...pts.map((p) => p.lon)) + pad;
    const W = 800;
    const H = 520;
    const project = (lat: number, lon: number) => ({
      x: ((lon - minLon) / (maxLon - minLon)) * W,
      // Latitude increases northward; SVG y increases downward.
      y: H - ((lat - minLat) / (maxLat - minLat)) * H,
    });
    return { W, H, project };
  }, [data]);

  if (!geometry) return <Empty title="No map data" body="Seed the demo to see the neighbourhood." />;
  const { W, H, project } = geometry;

  return (
    <section className="card" aria-labelledby="map-h">
      <div className="card-head">
        <h2 id="map-h">Neighbourhood</h2>
        <span className="spacer" />
        <span className="tiny faint">
          Positions approximate to ~{data.position_precision_m} m
        </span>
      </div>
      <div className="map-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Approximate neighbourhood demand map">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--rule)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width={W} height={H} fill="url(#grid)" />

          {/* Catchment rings around each pickup site */}
          {data.sites.map((s) => {
            const p = project(s.lat, s.lon);
            return (
              <circle
                key={`ring-${s.id}`}
                cx={p.x}
                cy={p.y}
                r={64}
                fill="var(--moss)"
                opacity={0.055}
                stroke="var(--moss-line)"
                strokeDasharray="4 5"
                strokeWidth={1}
              />
            );
          })}

          {/* Households — anonymous markers, never labelled with a name */}
          {data.households.map((h) => {
            const p = project(h.lat, h.lon);
            const r = 4 + Math.min(4, h.active_needs * 1.6);
            return (
              <g key={h.id}>
                {h.in_pool && (
                  <circle cx={p.x} cy={p.y} r={r + 5} fill="var(--moss)" opacity={0.16} />
                )}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={h.in_pool ? "var(--moss)" : "var(--ink-faint)"}
                  opacity={h.in_pool ? 0.95 : 0.5}
                />
              </g>
            );
          })}

          {/* Pickup sites */}
          {data.sites.map((s) => {
            const p = project(s.lat, s.lon);
            return (
              <g key={s.id}>
                <rect
                  x={p.x - 6}
                  y={p.y - 6}
                  width={12}
                  height={12}
                  rx={2.5}
                  fill="var(--clay)"
                  transform={`rotate(45 ${p.x} ${p.y})`}
                />
                <text
                  x={p.x}
                  y={p.y - 14}
                  textAnchor="middle"
                  fontSize="11"
                  fill="var(--ink-muted)"
                  fontFamily="var(--sans)"
                >
                  {s.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="map-legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--moss)" }} /> In a pool
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--ink-faint)" }} /> Declared
          need, unserved
        </span>
        <span className="legend-item">
          <span
            className="legend-swatch"
            style={{ background: "var(--clay)", borderRadius: 2, transform: "rotate(45deg)" }}
          />{" "}
          Public pickup site
        </span>
        <span className="legend-item faint">Marker size reflects how many needs a household declared.</span>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ activity */

const HUMAN_KINDS = new Set(["decision_answered", "participant_withdrew"]);
const ALERT_KINDS = new Set(["recovery_failed"]);

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <section className="card" aria-labelledby="act-h">
      <div className="card-head">
        <h2 id="act-h">What Pool has been doing</h2>
      </div>
      {items.length === 0 ? (
        <Empty title="Nothing yet" body="Run the coordinator to see its activity here." />
      ) : (
        <div className="feed">
          {items.map((e) => (
            <div className="feed-item" key={e.id}>
              <div className="feed-rail">
                <span
                  className={`feed-node${
                    ALERT_KINDS.has(e.kind) ? " alert" : HUMAN_KINDS.has(e.kind) ? " human" : ""
                  }`}
                />
                <span className="feed-line" />
              </div>
              <div className="feed-body">
                <div className="feed-text">{e.summary}</div>
                <div className="feed-meta">
                  {relativeTime(e.at)} · <span className="mono">{e.kind}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ agent trace */

export function AgentRuns({ runs, health }: { runs: RunSummary[]; health: Health | null }) {
  const [open, setOpen] = useState<string | null>(runs[0]?.run_id ?? null);
  return (
    <>
      <div className="page-head">
        <h1>Agent activity</h1>
        <p>
          Every coordinator run, with the tools it called and why it stopped. This is the
          evidence that what the rest of the interface shows was actually computed — not an
          animation. Model reasoning is deliberately not recorded or displayed.
        </p>
      </div>

      {health && (
        <div className="banner" style={{ marginBottom: 18 }}>
          <div>
            Model provider <code className="mono">{health.model_provider}</code>
            {" · "}bounds: {health.bounds.max_iterations} iterations,{" "}
            {health.bounds.max_tool_calls} tool calls,{" "}
            {health.bounds.workflow_timeout_seconds}s wall clock
            {" · "}background schedules{" "}
            {health.schedules_enabled ? "enabled" : "disabled"}
          </div>
        </div>
      )}

      {runs.length === 0 ? (
        <section className="card">
          <Empty title="No runs yet" body="Trigger a background scan to produce a trace." />
        </section>
      ) : (
        <div className="rows" style={{ gap: 14, display: "flex", flexDirection: "column" }}>
          {runs.map((r) => (
            <section className="card" key={r.run_id}>
              <div className="card-head">
                <h2 className="mono">{r.run_id}</h2>
                <span
                  className={`chip ${
                    r.outcome === "loop_fault" || r.outcome === "error"
                      ? "chip-warn"
                      : r.outcome === "no_action"
                        ? ""
                        : "chip-ok"
                  }`}
                >
                  {r.outcome.replace(/_/g, " ")}
                </span>
                <span className="spacer" />
                <span className="tiny faint">{relativeTime(r.started_at)}</span>
                <button
                  className="btn btn-sm"
                  aria-expanded={open === r.run_id}
                  onClick={() => setOpen(open === r.run_id ? null : r.run_id)}
                >
                  {open === r.run_id ? "Hide" : "Trace"}
                </button>
              </div>
              <div className="card-pad small muted" style={{ paddingBottom: 12 }}>
                trigger <code className="mono">{r.trigger}</code> · {r.iterations} model
                iteration{r.iterations === 1 ? "" : "s"} · {r.tool_calls.length} tool calls ·{" "}
                {r.duration_ms ?? "—"} ms · terminated:{" "}
                <code className="mono">{r.termination_reason}</code> · tokens in/out:{" "}
                <span className="num">
                  {r.input_tokens ?? 0}/{r.output_tokens ?? 0}
                </span>
              </div>
              {open === r.run_id && (
                <div className="trace">
                  {r.tool_calls.map((name, i) => (
                    <div className="trace-step" key={`${r.run_id}-${i}`}>
                      <span className="trace-idx">{i + 1}</span>
                      <span className="trace-name">{name}</span>
                    </div>
                  ))}
                  {r.tool_calls.length === 0 && (
                    <div className="trace-step">
                      <span className="trace-summary">no tools were called</span>
                    </div>
                  )}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ impact */

export function Impact({ metrics }: { metrics: Metrics }) {
  return (
    <>
      <div className="page-head">
        <h1>Impact</h1>
        <p>
          Computed from stored demo state, not asserted. Every figure below is derived from
          the commitments and activity records this workspace actually contains.
        </p>
      </div>
      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <Stat
          label="Collective savings"
          value={money(metrics.collective_savings_cents)}
          sub={`vs ${money(metrics.estimated_retail_spend_cents)} buying alone`}
        />
        <Stat
          label="Per household"
          value={money(metrics.average_household_savings_cents)}
          sub={`across ${metrics.households_participating} households`}
        />
        <Stat
          label="Average pickup"
          value={`${metrics.average_pickup_travel_minutes} min`}
          sub="travel burden per committed household"
        />
        <Stat
          label="Committed without asking"
          value={String(metrics.commitments_without_asking)}
          sub="within each household's own Smart Join limits"
        />
        <Stat
          label="Decisions requested"
          value={String(metrics.human_decisions_requested)}
          sub="times Pool needed a person"
        />
        <Stat
          label="Pools repaired"
          value={String(metrics.pools_recovered)}
          sub="recovered after a dropout"
        />
      </div>
      <div className="banner banner-warn">
        <div>
          These numbers describe synthetic demonstration data. They are not customers, not
          traction, and not real transactions.
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ needs */

export function Needs({ rows }: { rows: NeedRow[] }) {
  const [filter, setFilter] = useState("");
  const shown = rows.filter(
    (r) =>
      !filter ||
      r.product_name.toLowerCase().includes(filter.toLowerCase()) ||
      r.household_name.toLowerCase().includes(filter.toLowerCase()),
  );
  return (
    <>
      <div className="page-head">
        <h1>Declared needs</h1>
        <p>
          The only thing a household ever has to do. Each row is a standing statement of what
          someone routinely buys and the limits they set — not a request to organise anything.
        </p>
      </div>
      <section className="card">
        <div className="card-head">
          <h2>{shown.length} standing declarations</h2>
          <span className="spacer" />
          <input
            className="btn btn-sm"
            style={{ minWidth: 200 }}
            placeholder="Filter by product or household"
            aria-label="Filter needs"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="table-scroll">
          <table className="data">
            <thead>
              <tr>
                <th>Household</th>
                <th>Product</th>
                <th className="r">Quantity</th>
                <th className="r">Every</th>
                <th className="r">Needed by</th>
                <th className="r">Min saving</th>
                <th className="r">Max spend</th>
                <th>Substitutes</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.need_id}>
                  <td>{r.household_name}</td>
                  <td>{r.product_name}</td>
                  <td className="r num">
                    {r.quantity} {r.unit}
                  </td>
                  <td className="r num">{r.cadence_days}d</td>
                  <td className="r num">{r.needed_by}</td>
                  <td className="r num">{r.min_savings_pct}%</td>
                  <td className="r num">{r.max_spend_display}</td>
                  <td>{r.accept_substitutes ? "Accepted" : "Exact only"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ dashboard */

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
  onRespond: (id: string, approve: boolean) => void;
  busyDecision: string | null;
}) {
  const m = state.metrics;
  return (
    <>
      <div className="page-head">
        <h1>Your neighbourhood</h1>
        <p>
          {state.counts.households} households have declared {state.counts.needs} recurring
          needs. Pool is watching for overlap.
        </p>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <Stat
          label="Saved so far"
          value={money(m.collective_savings_cents)}
          sub={`${m.households_participating} households in pools`}
        />
        <Stat
          label="Handled without you"
          value={String(m.coordination_actions_automated)}
          sub="coordination actions Pool did on its own"
        />
        <Stat
          label="Times Pool asked"
          value={String(m.human_decisions_requested)}
          sub="decisions that genuinely needed a person"
        />
      </div>

      <div className="grid grid-main">
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {state.pools.length === 0 ? (
            <section className="card">
              <Empty
                title="No pools yet"
                body="Run a background scan and Pool will look for overlapping demand."
              />
            </section>
          ) : (
            state.pools.map((p) => (
              <PoolCard key={p.pool_id} pool={p} onOpen={() => onOpenPool(p.pool_id)} />
            ))
          )}
          {map && <NeighborhoodMap data={map} />}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <DecisionInbox
            decisions={state.decisions}
            onRespond={onRespond}
            busy={busyDecision}
          />
          <ActivityFeed items={state.activity.slice(0, 14)} />
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ scenario */

export function ScenarioPanel({
  onRun,
  running,
  result,
}: {
  onRun: () => void;
  running: boolean;
  result: { ok: boolean; failure: string; steps: { name: string; detail: string; facts: Record<string, unknown> }[] } | null;
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Guided scenario</h2>
        <span className="spacer" />
        <button className="btn btn-primary btn-sm" onClick={onRun} disabled={running}>
          {running && <span className="spin" />}
          Run the full story
        </button>
      </div>
      <div className="card-pad small muted">
        Resets this workspace, then runs the whole thing end to end: discover overlapping
        demand, form the pool, answer the decisions that need a human, drop a participant, and
        watch Pool repair the group. Every step executes the real code path.
      </div>
      {result && (
        <div className="rows">
          {result.steps.map((s, i) => (
            <div className="row" key={`${s.name}-${i}`}>
              <span className="chip chip-info">{i + 1}</span>
              <div className="row-main">
                <div className="row-title">{s.detail}</div>
                <div className="tiny faint mono">
                  {Object.entries(s.facts)
                    .slice(0, 6)
                    .map(([k, v]) => `${k}=${Array.isArray(v) ? `[${v.join(",")}]` : String(v)}`)
                    .join("  ")}
                </div>
              </div>
            </div>
          ))}
          {!result.ok && (
            <div className="row">
              <span className="chip chip-warn">Failed</span>
              <div className="row-main small">{result.failure}</div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export { api };
