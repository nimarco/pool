/* Behind Pool — one door to everything a judge or an operator needs, and nothing a
 * member does.
 *
 * This was the `Community` tab in the primary nav, and it could not finish the sentence
 * "this page exists so a member can ___". For a new account it was 3.45 viewport-heights
 * of eight sections in which nearly every figure read $0.00: community-wide economics, an
 * attention ledger, a responsibility-boundary explanation, a money ledger, other people's
 * pending decisions, a scatter of dots, and a link to the Operations console.
 *
 * None of that was wrong. It was in the wrong place. Every one of those is either proof
 * that the thing is real or capability for driving a demo alone, and both belong to an
 * audience that arrives on purpose. So this is now reached from the footer, it opens with
 * the index of what can be inspected, and a member can use Pool without ever seeing it.
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
import { blockingRuleExplanation } from "../labels";
import {
  ActorGlyph,
  ActorTag,
  Chip,
  Empty,
  Fact,
  Figure,
  IconArrowRight,
  LedgerLine,
  Meter,
  TracePills,
} from "../ui";

/* --------------------------------------------------------------------- map */

/** Where the people are, and whether they could actually share a pickup point.
 *
 * The previous version was dots on a grey rectangle with `preserveAspectRatio="none"`,
 * which stretched the geography to fill the box — so the one thing a map is for, how far
 * apart things are, was the thing it got wrong. And it answered no question: a reader
 * could see that there were dots and learn nothing from them.
 *
 * This draws the constraint the matcher applies. `haversine_km(household, site) <=
 * radius` is what decides whether somebody can be in an order, and the ring around each
 * pickup point is that number — read from the server, which reads it from
 * `coordination.WALKABLE_PICKUP_KM`, so the picture cannot drift from the rule. The
 * question it answers is the one the demo keeps asserting: *these people are close
 * enough to collect from one place.*
 *
 * **No tile service, no key, no new dependency, and that is a decision rather than a
 * shortcut.** Demo University does not exist. Putting invented households on a real
 * street map of a real city would be a more convincing lie, not a better map — and it
 * would add a network request, a third-party dependency and a CSP surface for the
 * privilege. The coordinates here are the fixtures' own, projected honestly.
 *
 * Privacy: the server rounds positions to roughly 110 m before they leave it and sends no
 * address, so what is plotted is a neighbourhood rather than a doorstep. This component
 * makes nothing more precise than what it was given.
 */
/** A pickup point's name, short enough to sit on a drawing.
 *
 *  Trims the qualifier after a dash and the words that are true of every site here.
 *  "Student Union — north entrance" is the right name on an order, where somebody has to
 *  find the door; on a map of four points it is a label that overlaps the next one. */
function shortSite(name: string): string {
  return name
    .replace(/\s+—.*$/, "")
    .replace(/\s+(common room|lobby|pavilion)$/i, "")
    .trim();
}

function CommunityMap({ map }: { map: MapData | null }) {
  if (!map || map.members.length === 0) return <Empty>No community data yet.</Empty>;

  const points = [...map.members, ...map.sites];
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const pad = 0.0016;
  const minLat = Math.min(...lats) - pad;
  const maxLat = Math.max(...lats) + pad;
  const minLon = Math.min(...lons) - pad;
  const maxLon = Math.max(...lons) + pad;

  /* An equirectangular projection with the longitude scale corrected for latitude, so a
     kilometre north and a kilometre east are the same length on screen. Without the
     cos(lat) term — and without a fixed aspect ratio — every distance the ring is meant
     to communicate is wrong by about 22% at this latitude. */
  const midLat = (minLat + maxLat) / 2;
  const cos = Math.cos((midLat * Math.PI) / 180);
  const spanLat = maxLat - minLat || 1;
  const spanLon = (maxLon - minLon || 1) * cos;
  const KM_PER_DEG_LAT = 110.574;

  const H = 100;
  const W = Math.max(60, Math.min(220, (spanLon / spanLat) * H));
  const x = (lon: number) => (((lon - minLon) * cos) / spanLon) * W;
  const y = (lat: number) => (1 - (lat - minLat) / spanLat) * H;
  /** The walkable radius, in the same units the projection uses. */
  const ring = ((map.walkable_km ?? 0) / (spanLat * KM_PER_DEG_LAT)) * H;

  const inPool = map.members.filter((m) => m.in_pool).length;

  return (
    <div className="map-wrap">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="map-svg"
        role="img"
        aria-label={
          `${map.members.length} members across ${
            new Set(map.members.map((m) => m.zone)).size
          } zones, ` +
          `${map.sites.length} pickup points, each within ${map.walkable_km} km walking ` +
          `of the members around it. ${inPool} currently in an order.`
        }
      >
        {/* Walking range first, underneath everything, because it is context rather than
            a thing on the map. One ring per pickup point: the overlap is exactly where a
            member could be served by either. */}
        {ring > 0
          ? map.sites.map((s) => (
              <circle
                key={`ring-${s.id}`}
                className="map-ring"
                cx={x(s.lon)}
                cy={y(s.lat)}
                r={ring}
              />
            ))
          : null}

        {map.members.map((m) => (
          <circle
            key={m.id}
            className={`map-member${m.in_pool ? " is-pooled" : ""}`}
            cx={x(m.lon)}
            cy={y(m.lat)}
            r={m.in_pool ? 1.5 : 1.1}
          />
        ))}

        {map.sites.map((s) => {
          /* Labels flip to the inside when a marker sits in the right-hand third,
             because a name running off the edge of the drawing is worse than no name
             and this is a fixed-width box rather than a pannable canvas. */
          const cx = x(s.lon);
          const flip = cx > W * 0.62;
          return (
            <g key={s.id}>
              <rect className="map-site" x={cx - 1.4} y={y(s.lat) - 1.4} width="2.8" height="2.8" />
              {/* Named, because "a pickup point somewhere here" is not the same claim as
                  "North Hall lobby", and the second one is the one Pool makes. */}
              <text
                className="map-label"
                x={flip ? cx - 2.6 : cx + 2.6}
                y={y(s.lat) + 1.1}
                textAnchor={flip ? "end" : "start"}
              >
                {shortSite(s.name)}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="map-legend">
        <span className="legend-item">
          <span className="legend-swatch swatch-pooled" /> in an order
        </span>
        <span className="legend-item">
          <span className="legend-swatch swatch-member" /> declared something
        </span>
        <span className="legend-item">
          <span className="legend-swatch swatch-site" /> pickup point
        </span>
        <span className="legend-item">
          <span className="legend-swatch swatch-ring" /> {map.walkable_km} km walk
        </span>
      </div>

      {/* The list is the map, for anybody the map is not for. Same numbers, no SVG. */}
      <details className="map-fallback">
        <summary className="tiny muted">Read this as a list</summary>
        <ul className="tiny muted">
          {[...new Set(map.members.map((m) => m.zone))].sort().map((zone) => (
            <li key={zone}>
              {zone}: {map.members.filter((m) => m.zone === zone).length} members
            </li>
          ))}
          {map.sites.map((s) => (
            <li key={s.id}>
              {s.name} — pickup point, permission: {s.permission}
            </li>
          ))}
        </ul>
      </details>

      <p className="tiny muted" style={{ padding: "0 14px 12px" }}>
        {map.note} Positions are rounded to about {map.position_precision_m} m before they
        leave the server. The ring is the distance the matcher actually allows, so a
        member outside every ring is one no order at these sites can include.
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
  /* The policy engine's own sentence. The rule name stays too: this is the surface a
     judge cross-references against `policy_checks`, unlike the member's own card. */
  const why = blockingRuleExplanation(decision.facts);

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
          {why ? (
            <p className="small muted" style={{ marginTop: 10 }}>
              Pool did not decide this alone: {why} (
              <span className="mono">{String(f.blocking_rule)}</span>).
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
  onTechnical,
  onLifecycle,
  onAbout,
}: {
  state: AppState;
  map: MapData | null;
  onOpenPool: (id: string) => void;
  onRespond: (decisionId: string, approve: boolean) => void;
  busyDecision: string | null;
  /** Null inside showcase mode, where the console must not be reachable — it writes
   *  supplier facts to whichever partition the client is addressing. */
  onOperations: (() => void) | null;
  onTechnical?: () => void;
  onLifecycle?: () => void;
  onAbout?: () => void;
}) {
  const m = state.metrics;
  const enablement = state.community?.enablement;
  /* The order a judge can actually check, and the proof stored beside it. First pool
     with a stored execution proof, or the first pool at all — never fabricated, and the
     whole section is absent when no run has formed anything yet. */
  const proven = state.pools.find((pool) => pool.execution_proof) ?? state.pools[0] ?? null;
  const proof = proven?.execution_proof ?? null;


  return (
    <div className="stack">
      <header className="row-between">
        <div>
          <h1 className="title">Behind Pool</h1>
          <p className="small muted" style={{ marginTop: 6 }}>
            {state.community?.name ?? "This community"} — {state.counts.members} members ·{" "}
            {state.counts.needs} standing needs · {state.counts.standing_hosts} people
            willing to host · entirely synthetic
          </p>
        </div>
      </header>

      {/* The index, first, because somebody who came here came to check something. Each
          of these used to be reachable only from a different accordion, drawer or tab —
          five labels led to the same technical proof — and a judge had to already know
          the app to find any of them. */}
      <section className="panel">
        <div className="panel-head">
          <h2>Start here</h2>
        </div>
        <div className="panel-pad">
          <div className="proof-index">
            {onTechnical ? (
              <button className="proof-link" onClick={onTechnical}>
                <span className="proof-link-title">Technical proof</span>
                <span className="proof-link-sub">
                  The run that formed an order, its stored tool sequence, the pool&apos;s
                  own <code>created_by_run</code>, and the AgentCore identifiers — read
                  back from the same workspace.
                </span>
              </button>
            ) : null}
            {onLifecycle ? (
              <button className="proof-link" onClick={onLifecycle}>
                <span className="proof-link-title">One order, stage by stage</span>
                <span className="proof-link-sub">
                  The recorded lifecycle in its own copy of the community: demand, host,
                  commitment, an authorisation failure, a replacement, purchase, pickup,
                  reconciliation.
                </span>
              </button>
            ) : null}
            {onOperations ? (
              <button className="proof-link" onClick={onOperations}>
                <span className="proof-link-title">Operations console</span>
                <span className="proof-link-sub">
                  The operator side: supplier-quote freshness, the fulfilment job, and
                  every authorization, capture and failure code intact.
                </span>
              </button>
            ) : null}
            {onAbout ? (
              <button className="proof-link" onClick={onAbout}>
                <span className="proof-link-title">What is real here</span>
                <span className="proof-link-sub">
                  Which parts are live software, which data is synthetic, and which
                  payments are simulated — stated rather than implied.
                </span>
              </button>
            ) : null}
          </div>
        </div>
      </section>

      {/* The second currency. Money saved is half the argument; the other half is that
          organising this cost nobody an evening, and that half has a number too. Both
          are sums over stored rows for this Community, and neither is a projection. */}
      <section className="panel">
        <div className="panel-head">
          <h2>What Pool did on its own</h2>
          <span className="spacer" />
          <ActorTag actor="engine" label="Counted from stored rows" />
        </div>
        <div className="panel-pad stack-sm">
          <p className="small muted prose">
            In the informal version of this, one person does all of it. Here nobody did.
          </p>
          <div className="grid grid-3">
            <Figure
              label="Actions Pool took on its own"
              value={String(m.coordination_actions_automated)}
              accent
              sub="discovery, pricing, recruiting, recovery, lock, order"
            />
            <Figure
              label="Times it had to ask a person"
              value={String(m.human_decisions_requested)}
              sub="one question each, with the price already worked out"
            />
            <Figure
              label="Commitments made without asking"
              value={String(m.commitments_without_asking)}
              sub="each one inside limits that member had already stored"
            />
          </div>
          <p className="small muted">
            {m.pools_recovered} order{m.pools_recovered === 1 ? "" : "s"} repaired after a
            payment failed · {m.pickups_completed} of {m.pickups_expected} handoffs
            confirmed against a one-time credential.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Decisions waiting on a person</h2>
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

      <section className="panel">
        <div className="panel-head">
          <h2>Every action, and who took it</h2>
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

      {/* The four questions a judge has after "did it really do that", answered here
          rather than only behind a link: what deterministic code established, what the
          agent chose, what survived the process, and where it ran. Every value is read
          off the pool the run actually created — `execution_proof` is assembled
          server-side and re-read from the same workspace, so nothing here is inferred
          from the pool list. Absent until a run has formed something, because before
          that there is genuinely nothing to prove. */}
      {proven ? (
        <section className="panel">
          <div className="panel-head">
            <h2>What proves it</h2>
            <span className="spacer" />
            <ActorTag actor="engine" label="Read back from storage" />
          </div>
          <div className="panel-pad stack-sm">
            <div className="grid grid-2">
              <div className="proof-claim">
                <span className="section-title">Deterministic code established</span>
                <p className="small" style={{ marginTop: 6 }}>
                  {/* Only what this payload actually carries. `viability` and the case
                      breakdown are detail-only fields, absent until a final offer
                      exists, and inventing either of them here would be exactly the
                      kind of number this section exists to disprove. */}
                  {proven.provisional_units} compatible units against a{" "}
                  {proven.threshold_units}-unit supplier minimum, from{" "}
                  {proven.buyer_count} {proven.buyer_count === 1 ? "buyer" : "buyers"}
                  {proven.economics
                    ? ` — ${proven.economics.packages.cases} whole ${proven.economics.packages.cases === 1 ? "case" : "cases"} of ${proven.economics.packages.case_units}, ${proven.economics.packages.surplus_units} surplus.`
                    : ". The case fit and the full check list are on the order itself."}
                </p>
                <p className="tiny faint" style={{ marginTop: 6 }}>
                  Money, quantities and thresholds are computed here and never by the
                  model.
                </p>
              </div>
              <div className="proof-claim">
                <span className="section-title">The agent chose</span>
                <p className="small" style={{ marginTop: 6 }}>
                  {proof?.run.tool_calls.length ?? 0} tool{" "}
                  {(proof?.run.tool_calls.length ?? 0) === 1 ? "call" : "calls"} over{" "}
                  {proof?.run.iterations ?? 0} iterations, ending{" "}
                  {(proof?.run.termination_reason ?? "").replace(/_/g, " ") || "cleanly"}.
                </p>
                {proof ? <TracePills names={proof.run.tool_calls} ordered /> : null}
              </div>
              <div className="proof-claim">
                <span className="section-title">What persisted</span>
                <p className="small" style={{ marginTop: 6 }}>
                  The order carries <code>created_by_run</code>{" "}
                  {proof && proof.created_by_run === proof.run_id
                    ? "equal to the run that made it"
                    : "from the run that made it"}
                  , and both rows read back from this same workspace.
                </p>
                <p className="tiny faint" style={{ marginTop: 6 }}>
                  <code>{proof?.created_by_run ?? ""}</code>
                </p>
              </div>
              <div className="proof-claim">
                <span className="section-title">Where it ran, and on whose terms</span>
                <p className="small" style={{ marginTop: 6 }}>
                  {proof?.execution.service ?? "the deployed coordinator"}
                  {proof?.execution.region ? ` · ${proof.execution.region}` : ""} ·{" "}
                  {proof?.run.model_provider ?? ""}{" "}
                  {proof?.run.model_id ? `(${proof.run.model_id})` : ""}
                </p>
                <p className="tiny faint" style={{ marginTop: 6 }}>
                  Supplier terms came from {proven.supplier}, stored as{" "}
                  {proven.offer_source || "synthetic"} — operator-imported from a
                  committed sheet, never scraped and never negotiated. Riverbend
                  Wholesale does not exist.
                </p>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {/* The money, once there is any. Three $0.00 figures above the fold on a page whose
          job is to be inspected says "nothing here" about a page that is full of things —
          and the honest version of "no money has moved" is one sentence, not a ledger of
          zeroes. Both readings are true; only one of them is useful. */}
      {m.pools_locked_or_beyond > 0 ? (
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
      ) : (
        <p className="small muted">
          No money has moved in this community yet. Every figure below is a sum over
          stored rows, so they read zero until an order locks.
        </p>
      )}

      <section className="grid grid-side">
        <div className="panel">
          <div className="panel-head">
            <h2>What it produced</h2>
            <span className="spacer" />
            <span className="tiny faint">{m.pools_locked_or_beyond} locked or beyond</span>
          </div>
          {state.pools.length === 0 ? (
            <Empty>
              No order yet. Use <strong>Ask Pool to check now</strong> on Home to scan the
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
            <h2>Where everyone is</h2>
          </div>
          <CommunityMap map={map} />
        </div>
      </section>

      {/* Same rule the three figures above already follow, which this ledger did not:
          before an order locks every one of these rows is $0.00, and five zeroes in a
          column on a page built to be inspected reads as broken rather than as empty. */}
      {m.pools_locked_or_beyond > 0 ? (
      <section className="panel">
        <div className="panel-head">
          <h2>Where the money went</h2>
          <span className="spacer" />
          <ActorTag actor="engine" label="Every figure computed" />
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
      </section>
      ) : null}

      {enablement ? (
        <section className="panel">
          <div className="panel-head">
            <h2>The community it ran inside</h2>
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
              <summary className="small">
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
    </div>
  );
}
