/* Demo University — the dataset a judge can inspect, and the result of what happened
 * to it.
 *
 * Every figure is a sum over stored rows, labelled as synthetic. Nothing here is a
 * projection, a target, or traction.
 */

import {
  ActivityEvent,
  AppState,
  Decision,
  MapData,
  PoolView,
  money,
  pct,
  shortTime,
  statusCopy,
} from "../api";
import {
  ActorGlyph,
  Block,
  Chip,
  Empty,
  Fact,
  Figure,
  IconArrowRight,
  LedgerLine,
  Meter,
} from "../ui";

/* --------------------------------------------------------------------- map */

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
      <svg viewBox="0 0 100 70" preserveAspectRatio="none" role="img" aria-label="Community map">
        {map.sites.map((s) => (
          <rect
            key={s.id}
            x={x(s.lon) - 1.1}
            y={(y(s.lat) * 70) / 100 - 1.1}
            width="2.2"
            height="2.2"
            fill="var(--graphite)"
          />
        ))}
        {map.members.map((m) => (
          <circle
            key={m.id}
            cx={x(m.lon)}
            cy={(y(m.lat) * 70) / 100}
            r={m.in_pool ? 1.1 : 0.7}
            fill={m.in_pool ? "var(--moss)" : "var(--ink-faint)"}
            opacity={m.in_pool ? 1 : 0.5}
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
          <span
            className="legend-swatch"
            style={{ background: "var(--graphite)", borderRadius: 0 }}
          />{" "}
          pickup site
        </span>
      </div>
      <p className="tiny muted" style={{ padding: "0 14px 12px" }}>
        {map.note}
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- decisions */

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
    <div style={{ padding: "18px 22px" }}>
      <div className="row-between" style={{ marginBottom: 10 }}>
        <div>
          <div className="row-title">{decision.household_name}</div>
          <div className="tiny muted">
            {isHostOffer ? "Offered a fulfilment job" : "Asked to approve their final price"}
          </div>
        </div>
        {decision.expires_at ? (
          <span className="tiny faint">answer by {shortTime(decision.expires_at)}</span>
        ) : null}
      </div>

      {isHostOffer ? (
        <>
          <p className="small">
            Collect {String(f.units)} units for {String(f.orders)} people —{" "}
            {String(f.supplier_distance_km)} km round trip. Earns{" "}
            <strong>{String(f.estimated_earnings_display)}</strong>.
          </p>
          <div className="inset facts" style={{ marginTop: 12 }}>
            <Fact label="Pickup window" value={shortTime(String(f.distribution_starts_at))} />
            <Fact label="Orders" value={String(f.orders)} />
            <Fact label="Units" value={String(f.units)} />
          </div>
        </>
      ) : (
        <>
          <p className="small">
            {String(f.units)} × {String(f.product)} for{" "}
            <strong>{String(f.final_cost_display)}</strong> instead of{" "}
            {String(f.baseline_display)} —{" "}
            {typeof f.savings_bps === "number" ? pct(f.savings_bps) : ""} less.
          </p>
          <div className="inset facts" style={{ marginTop: 12 }}>
            <Fact label="Merchandise" value={money(breakdown.merchandise ?? 0)} />
            <Fact label="Host compensation" value={money(breakdown.host_compensation ?? 0)} />
            <Fact label="Pool fee" value={money(breakdown.pool_fee ?? 0)} />
            <Fact label="Processing" value={money(breakdown.payment_processing ?? 0)} />
            <Fact label="Pickup" value={String(f.pickup_site)} />
            <Fact label="Walk" value={`${String(f.travel_minutes)} min`} />
          </div>
          {f.blocking_rule ? (
            <p className="tiny muted" style={{ marginTop: 10 }}>
              Pool did not decide this alone because the rule{" "}
              <span className="mono">{String(f.blocking_rule)}</span> did not pass.
            </p>
          ) : null}
        </>
      )}

      <div className="btn-row" style={{ marginTop: 14 }}>
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

/* --------------------------------------------------------------------- feed */

const HUMAN_KINDS = /decision|approval|host_offer|response|exception|issue/;

/** Consecutive events of the same kind, folded into one line.
 *
 * Ten confirmed handoffs are ten stored rows and all ten really happened, but ten
 * near-identical lines bury the entries that carry the story — the pool forming, the
 * recovery, the lock. Only the count is derived here, and it is a count of rows.
 */
function fold(events: ActivityEvent[]): { lead: ActivityEvent; count: number }[] {
  const groups: { lead: ActivityEvent; count: number }[] = [];
  for (const event of events) {
    const last = groups[groups.length - 1];
    if (last && last.lead.kind === event.kind) last.count += 1;
    else groups.push({ lead: event, count: 1 });
  }
  return groups;
}

function activityKindLabel(event: ActivityEvent): string {
  if (event.kind === "payment_captured") {
    const mode = String(event.facts.provider_mode ?? "");
    if (mode === "simulated") return "simulated capture recorded";
    if (mode === "test") return "test-mode capture recorded";
  }
  return event.kind.replace(/_/g, " ");
}

export function Feed({ events, limit }: { events: ActivityEvent[]; limit?: number }) {
  if (events.length === 0) {
    return <Empty>Nothing has happened yet.</Empty>;
  }
  const groups = fold(events);
  const shown = limit ? groups.slice(0, limit) : groups;
  return (
    <div className="timeline" style={{ padding: "14px 22px" }}>
      {shown.map(({ lead, count }) => {
        const human = HUMAN_KINDS.test(lead.kind);
        return (
          <div key={lead.id} className="tl-item">
            <div className="tl-rail">
              <span className={`tl-node${human ? " human" : ""}`} />
              <span className="tl-line" />
            </div>
            <div className="tl-body">
              <div className="tl-text">{lead.summary}</div>
              <div className="tl-meta">
                {activityKindLabel(lead)} · {shortTime(lead.at)}
                {count > 1 ? ` · and ${count - 1} more like it` : ""}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------------------------------------------------- pools */

function PoolRow({ pool, onOpen }: { pool: PoolView; onOpen: () => void }) {
  const s = statusCopy(pool.status);
  return (
    <button className="row" onClick={onOpen}>
      <div className="row-body">
        <div className="row-title">
          {pool.product_name}
          <Chip tone={s.tone}>{s.label}</Chip>
        </div>
        <div className="tiny muted" style={{ marginBottom: 6 }}>
          {pool.buyer_count} buyers
          {/* Named only when it differs, which happens exactly when an authorisation
              failed and a replacement joined. Otherwise it is noise. */}
          {pool.member_count > pool.buyer_count
            ? ` (${pool.member_count} on record — ${pool.member_count - pool.buyer_count} declined)`
            : ""}{" "}
          · {pool.provisional_units}/{pool.threshold_units} units · {pool.pickup_site}
          {pool.host ? ` · host ${pool.host.display_name}` : " · host needed"}
        </div>
        <Meter value={pool.provisional_units} max={pool.threshold_units} />
      </div>
      <div className="row-tail">
        <div className="fact-value num">{pool.savings_pct || "—"}</div>
        <div className="tiny faint">{pool.is_estimate ? "estimated" : "final"}</div>
      </div>
      <IconArrowRight />
    </button>
  );
}

/* ---------------------------------------------------------------------- view */

export function CommunityView({
  state,
  map,
  onOpenPool,
  onRespond,
  busyDecision,
  onOperations,
}: {
  state: AppState;
  map: MapData | null;
  onOpenPool: (id: string) => void;
  onRespond: (decisionId: string, approve: boolean) => void;
  busyDecision: string | null;
  onOperations: () => void;
}) {
  const m = state.metrics;
  const enablement = state.community?.enablement;


  return (
    <div className="stack">
      <header className="row-between">
        <div>
          <h1 className="title">{state.community?.name ?? "Community"}</h1>
          <p className="small muted" style={{ marginTop: 6 }}>
            {state.counts.members} members · {state.counts.needs} standing needs ·{" "}
            {state.counts.standing_hosts} people willing to host · entirely synthetic
          </p>
        </div>
      </header>

      {enablement ? (
        <section className="panel">
          <div className="panel-head">
            <h3>How this Community enables Pool</h3>
            <span className="spacer" />
            <Chip>synthetic fixture</Chip>
          </div>
          <div className="panel-pad stack-sm">
            <p className="small muted prose">
              Existing communities provide a bounded membership, independent demand and
              possible pickup sites; Pool discovers and coordinates each viable transaction.
            </p>
            <div className="grid grid-3">
              <Fact
                label="Membership boundary"
                value={`${enablement.verified_members} of ${enablement.total_memberships} fixture memberships verified`}
              />
              <Fact
                label="Independent demand"
                value={`${enablement.independent_need_declarers} members declared needs separately`}
              />
              <Fact
                label="Designated pickup"
                value={`${enablement.designated_pickup_sites.length} fixture sites · ${[...new Set(enablement.designated_pickup_sites.map((site) => site.permission))].join(", ")}`}
              />
            </div>
            <div className="banner">
              <strong>Community enables</strong>
              <span>→</span>
              <strong>Pool coordinates</strong>
              <span>→</span>
              <strong>Members choose and collect</strong>
            </div>
            <details className="inset">
              <summary className="small" style={{ cursor: "pointer" }}>
                <strong>Who is responsible for what</strong>
              </summary>
              <ul className="small muted prose" style={{ marginTop: 10, paddingLeft: 20 }}>
                <li>
                  <strong>Community:</strong> verifies membership, permits sites or windows,
                  sets site rules and tells members the service exists.
                </li>
                <li>
                  <strong>Pool:</strong> handles matching, economics, hosts, commitments,
                  recovery, records and pickup coordination.
                </li>
                <li>
                  <strong>Members:</strong> set needs and constraints, approve and fund their
                  allocations, and collect them.
                </li>
                <li>
                  The Community does not buy or front inventory, choose products, create or
                  invite the group, collect money, or chase payment failures.
                </li>
              </ul>
            </details>
            <p className="tiny faint">
              Synthetic records only — no institutional partnership, endorsement or
              real-world permission is implied.
            </p>
          </div>
        </section>
      ) : null}

      <section className="grid grid-3">
        <Figure
          label="If everyone bought alone"
          value={money(m.estimated_retail_spend_cents)}
          sub="recorded retail baseline"
        />
        <Figure
          label="All-in through Pool"
          value={money(m.pool_spend_cents)}
          sub="merchandise + host + processing + Pool fee"
        />
        <Figure
          label="Kept in the community"
          value={money(m.collective_savings_cents)}
          accent
          sub={`${money(m.average_buyer_savings_cents)} average after every buyer-funded cost`}
        />
      </section>

      <section className="grid grid-side">
        <div className="panel">
          <div className="panel-head">
            <h3>Pools</h3>
            <span className="spacer" />
            <span className="tiny faint">{m.pools_locked_or_beyond} locked or beyond</span>
          </div>
          {state.pools.length === 0 ? (
            <Empty>
              No pool yet. Use <strong>Find opportunities</strong> on Home to scan the
              community's standing needs.
            </Empty>
          ) : (
            <div className="rows">
              {state.pools.map((p) => (
                <PoolRow key={p.pool_id} pool={p} onOpen={() => onOpenPool(p.pool_id)} />
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Where everyone is</h3>
          </div>
          <CommunityMap map={map} />
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Decisions waiting on a person</h3>
          <span className="spacer" />
          <span className="tiny faint">
            {state.decisions.length === 0 ? "empty, as usual" : `${state.decisions.length} waiting`}
          </span>
        </div>
        {state.decisions.length === 0 ? (
          <Empty>
            Nobody is waiting. Pool asks only when a person's stored rule does not pass.
          </Empty>
        ) : (
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
        )}
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <div className="panel-head">
            <h3>Where the money went</h3>
          </div>
          <div className="panel-pad">
            <div className="ledger">
              <LedgerLine label="Merchandise to the supplier" value={money(m.merchandise_cents)} />
              <LedgerLine label="Compensation to hosts" value={money(m.host_compensation_cents)} />
              <LedgerLine label="Card processing" value={money(m.payment_processing_cents)} />
              <LedgerLine label="Pool's share of the saving" value={money(m.platform_fee_cents)} />
              <LedgerLine
                label="Recorded all-in buyer cost"
                value={money(m.pool_spend_cents)}
                kind="total"
              />
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>How much attention it cost anyone</h3>
          </div>
          <div className="panel-pad">
            <div className="ledger">
              <LedgerLine
                label="Actions Pool took on its own"
                value={String(m.coordination_actions_automated)}
              />
              <LedgerLine
                label="Times a person was asked"
                value={String(m.human_decisions_requested)}
              />
              <LedgerLine
                label="Commitments made without asking"
                value={String(m.commitments_without_asking)}
              />
              <LedgerLine label="Pools repaired after a failure" value={String(m.pools_recovered)} />
              <LedgerLine
                label="Handoffs confirmed"
                value={`${m.pickups_completed} / ${m.pickups_expected}`}
              />
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>What Pool did</h3>
          <span className="spacer" />
          <span className="actor-key">
            <span className="actor actor-agent">
              <ActorGlyph actor="agent" />
              Pool acted
            </span>
            <span className="actor actor-human">
              <ActorGlyph actor="human" />A person was involved
            </span>
          </span>
        </div>
        <Feed events={state.activity} limit={14} />
      </section>

      <Block title="Behind the counter">
        <p className="small muted prose">
          Inspect the host job, supplier-quote freshness, and every authorization, capture
          and failure code.
        </p>
        <div className="btn-row" style={{ marginTop: 14 }}>
          <button className="btn btn-sm" onClick={onOperations}>
            Open operations
            <IconArrowRight />
          </button>
        </div>
      </Block>
    </div>
  );
}
