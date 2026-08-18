/* Home — what a member of Demo University sees when they open Pool.
 *
 * This is the product, not an explanation of the product. Everything on it is either
 * something this member has to do, something Pool has found for them, or something
 * they told Pool once and have not thought about since.
 *
 * Every figure comes off the server. The timing split, the buyer and membership counts,
 * the economics and the lifecycle state are all read from the same values the product
 * used to act; nothing here recomputes domain truth in React.
 */

import { useEffect, useState } from "react";
import {
  AppState,
  Decision,
  HostOpportunities,
  MemberView,
  NeedRow,
  PoolView,
  RunResult,
  api,
  money,
  pct,
  shortDateOnly,
  shortTime,
  statusCopy,
} from "../api";
import { ConvergenceFigure } from "../brand";
import {
  ActorTag,
  Block,
  Chip,
  CoordinatorWait,
  Empty,
  IconArrowRight,
  IconCheck,
  IconDot,
  Meter,
  TracePills,
} from "../ui";

/* ------------------------------------------------------------------ greeting */

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/* ------------------------------------------------------ waiting on this member */

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
  const isHostOffer = decision.kind === "host_offer";
  return (
    <div className="panel-pad stack-sm">
      {isHostOffer ? (
        <p style={{ fontSize: 16 }}>
          Collect <strong>{String(f.units)} units</strong> for {String(f.orders)} people —{" "}
          {String(f.supplier_distance_km)} km round trip, and you would earn{" "}
          <strong>{String(f.estimated_earnings_display)}</strong>.
        </p>
      ) : (
        <p style={{ fontSize: 16 }}>
          <strong>
            {String(f.units)} × {String(f.product)}
          </strong>{" "}
          for <strong>{String(f.final_cost_display)}</strong> instead of{" "}
          {String(f.baseline_display)} —{" "}
          {typeof f.savings_bps === "number" ? pct(f.savings_bps) : ""} less. Collect from{" "}
          {String(f.pickup_site)}, {String(f.travel_minutes)} minutes' walk.
        </p>
      )}
      {f.blocking_rule ? (
        <p className="tiny muted">
          Pool did not decide this for you because your rule{" "}
          <span className="mono">{String(f.blocking_rule)}</span> did not pass.
        </p>
      ) : null}
      <div className="btn-row">
        <button
          className="btn btn-accept"
          disabled={busy}
          onClick={() => onRespond(decision.decision_id, true)}
        >
          {busy ? "…" : isHostOffer ? "Accept the job" : "Yes, buy it"}
        </button>
        <button
          className="btn"
          disabled={busy}
          onClick={() => onRespond(decision.decision_id, false)}
        >
          Not this time
        </button>
        {decision.expires_at ? (
          <span className="tiny faint">answer by {shortTime(decision.expires_at)}</span>
        ) : null}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- opportunity */

function OpportunityCard({
  pool,
  onOpen,
  onShowAgent,
}: {
  pool: PoolView;
  onOpen: () => void;
  /* Takes the pool id rather than firing a bare signal: the card is the only thing that
     knows which pool it drew, and the proof it offers has to be that pool's proof. */
  onShowAgent: (poolId: string) => void;
}) {
  const s = statusCopy(pool.status);
  const settled = pool.status === "completed" || pool.status === "purchased";
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{settled ? "Your order" : "Pool found overlapping demand"}</h2>
        <Chip tone={s.tone}>{s.label}</Chip>
      </div>
      <div className="panel-pad stack-sm">
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="display" style={{ fontSize: 30, lineHeight: 1.1 }}>
              {pool.product_name}
            </div>
            <p className="small muted" style={{ marginTop: 6 }}>
              {pool.buyer_count} members · {pool.provisional_units} units · collect from{" "}
              {pool.pickup_site}
              {pool.host ? ` · ${pool.host.display_name} is carrying it` : ""}
            </p>
          </div>
          {pool.savings_pct ? (
            <div className="figure-tail">
              <div className="figure-value sm figure-accent">{pool.savings_pct}</div>
              <div className="tiny faint">{pool.is_estimate ? "estimated" : "less than retail"}</div>
            </div>
          ) : null}
        </div>

        <Meter value={pool.provisional_units} max={pool.threshold_units} />
        <p className="tiny muted">
          {pool.provisional_units} of the {pool.threshold_units} units this supplier will
          sell.
          {pool.funded_units > 0
            ? ` ${pool.funded_units} units have exact-amount authorizations.`
            : ""}
        </p>

        <div className="btn-row" style={{ marginTop: 4 }}>
          <button className="btn btn-primary" onClick={onOpen}>
            Open the pool
            <IconArrowRight />
          </button>
          {pool.execution_proof ? (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onShowAgent(pool.pool_id)}
            >
              <ActorTag actor="agent" label="Technical proof for this run" />
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function WatchingCard({
  running,
  onFind,
  memberCount,
  needCount,
  liveDiscovery,
}: {
  running: boolean;
  onFind: () => void;
  memberCount: number;
  needCount: number;
  liveDiscovery: boolean;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Pool is watching</h2>
      </div>
      <div className="grid grid-side" style={{ gap: 0, alignItems: "stretch" }}>
        <div className="panel-pad stack-sm" style={{ justifyContent: "center" }}>
          <p className="small muted prose">
            {memberCount} members declared {needCount} standing needs independently. Pool
            watches for overlaps worth buying together; nobody has to organise a group.
          </p>
          <div className="btn-row">
            <button className="btn btn-primary btn-lg" onClick={onFind} disabled={running}>
              {running ? <span className="spinner" /> : null}
              {running ? "Coordinator running" : "Find opportunities"}
            </button>
          </div>
          {running ? <CoordinatorWait live={liveDiscovery} /> : null}
        </div>
        <div className="panel-pad" style={{ borderLeft: "1px solid var(--rule)" }}>
          <ConvergenceFigure />
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------------- view */

export function Home({
  state,
  identity,
  lastRun,
  running,
  busyDecision,
  onFind,
  onOpenPool,
  onRespond,
  onShowAgent,
  onGoNeeds,
  liveDiscovery,
}: {
  state: AppState;
  identity: { id: string; display_name: string };
  lastRun: RunResult | null;
  running: boolean;
  busyDecision: string | null;
  onFind: () => void;
  onOpenPool: (id: string) => void;
  onRespond: (id: string, approve: boolean) => void;
  onShowAgent: (poolId: string) => void;
  onGoNeeds: () => void;
  liveDiscovery: boolean;
}) {
  const [needs, setNeeds] = useState<NeedRow[]>([]);
  const [me, setMe] = useState<MemberView | null>(null);
  const [hosting, setHosting] = useState<HostOpportunities | null>(null);

  useEffect(() => {
    api.needs().then((view) => setNeeds(view.needs)).catch(() => setNeeds([]));
  }, [state.workspace]);

  useEffect(() => {
    api.member(identity.id).then(setMe).catch(() => setMe(null));
    // Pool is three-sided, and one of those sides is this same person on a different
    // day. If they are carrying an order, that is the most important thing on their
    // home screen.
    api.hostOpportunities(identity.id).then(setHosting).catch(() => setHosting(null));
  }, [identity.id, state.workspace, state.pools.length, state.decisions.length]);

  const mine = needs
    .filter((n) => n.household_id === identity.id)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  const forMe = state.decisions.filter((d) => d.household_id === identity.id);
  const forOthers = state.decisions.length - forMe.length;
  const pool = state.pools[0] ?? null;

  return (
    <div className="stack">
      <header className="row-between">
        <div>
          <h1 className="title">
            {greeting()}, {identity.display_name.split(" ")[0]}
          </h1>
          <p className="small muted" style={{ marginTop: 4 }}>
            {state.community?.name ?? "Demo University"}
            {me?.community_membership
              ? ` · verified by ${me.community_membership.verification_method.replace(/_/g, " ")}`
              : ""}
          </p>
        </div>
      </header>

      {forMe.length > 0 ? (
        <section className="panel" style={{ borderColor: "var(--clay-line)" }}>
          <div className="panel-head" style={{ background: "var(--clay-soft)", borderColor: "var(--clay-line)" }}>
            <h2>Pool needs your answer</h2>
            <span className="spacer" />
            <ActorTag actor="human" />
          </div>
          <div className="rows">
            {forMe.map((d) => (
              <DecisionCard
                key={d.decision_id}
                decision={d}
                busy={busyDecision === d.decision_id}
                onRespond={onRespond}
              />
            ))}
          </div>
        </section>
      ) : null}

      {(hosting?.active_jobs ?? []).map((job) => (
        <section key={job.pool_id} className="panel">
          <div className="panel-head">
            <h2>You are carrying this order</h2>
            <span className="spacer" />
            <ActorTag actor="human" label="Your job" />
          </div>
          <div className="panel-pad stack-sm">
            <div className="row-between" style={{ alignItems: "flex-start" }}>
              <div>
                <div className="display" style={{ fontSize: 26 }}>
                  {job.product_name}
                </div>
                <p className="small muted" style={{ marginTop: 6 }}>
                  {job.picked_up} of {job.total} orders collected · {job.units_total} units ·{" "}
                  {shortTime(job.distribution_starts_at)} to{" "}
                  {shortTime(job.distribution_ends_at)}
                </p>
              </div>
              <div className="figure-tail">
                <div className="figure-value sm figure-accent">
                  {String((job.earnings as Record<string, string>).total_display ?? "—")}
                </div>
                <div className="tiny faint">you earn</div>
              </div>
            </div>
            <Meter value={job.picked_up} max={job.total} />
            <div className="btn-row">
              <button className="btn btn-sm" onClick={() => onOpenPool(job.pool_id)}>
                Open the pool
                <IconArrowRight />
              </button>
            </div>
          </div>
        </section>
      ))}

      {pool ? (
        <OpportunityCard
          pool={pool}
          onOpen={() => onOpenPool(pool.pool_id)}
          onShowAgent={onShowAgent}
        />
      ) : (
        <WatchingCard
          running={running}
          onFind={onFind}
          memberCount={state.counts.members}
          needCount={state.counts.needs}
          liveDiscovery={liveDiscovery}
        />
      )}

      {forOthers > 0 ? (
        <p className="tiny muted">
          {forOthers} other {forOthers === 1 ? "person is" : "people are"} being asked
          something too. In the real product they answer on their own phone; here you can
          answer for them from <strong>Demo controls</strong>.
        </p>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h2>What you buy anyway</h2>
          <span className="spacer" />
          <button className="btn btn-sm btn-ghost" onClick={onGoNeeds}>
            All needs
            <IconArrowRight />
          </button>
        </div>
        {mine.length === 0 ? (
          <Empty>You have not told Pool about anything you buy regularly yet.</Empty>
        ) : (
          <div className="rows">
            {mine.map((n) => (
              <div key={n.need_id} className="row">
                <div className="row-body">
                  <div className="row-title">{n.product_name}</div>
                  <div className="tiny muted">
                    {n.quantity} {n.unit} · about every {n.cadence_days} days
                    {n.flexibility_days > 0
                      ? ` · happy to buy up to ${n.flexibility_days} days early if it saves money`
                      : " · not willing to buy early"}
                  </div>
                </div>
                <div className="row-tail">
                  <div className="fact-value">{shortDateOnly(n.expected_next_need_date)}</div>
                  <div className="tiny faint">next needed</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {me ? (
        <Block title="What Pool may decide for you">
          <div className="grid grid-lede">
            <p className="small muted prose">
              Pool acts only when every stored limit passes; otherwise it asks you.
            </p>
            <div className="ledger">
              <LedgerRow label="Minimum saving before it acts" value={me.autonomy_display.min_savings} />
              <LedgerRow label="Most it may ever spend" value={me.autonomy_display.max_spend} />
              <LedgerRow label="Furthest you will walk" value={me.autonomy_display.max_travel} />
              <LedgerRow
                label="Substitutions"
                value={me.autonomy_display.substitution.replace(/_/g, " ")}
              />
              <LedgerRow
                label="Payment method saved"
                value={me.has_payment_method ? "yes" : "no"}
              />
            </div>
          </div>
        </Block>
      ) : null}

      <Block title={`Around ${state.community?.name ?? "your community"}`}>
        <div className="grid grid-3">
          <SmallStat label="Members" value={String(state.counts.members)} />
          <SmallStat label="Standing needs" value={String(state.counts.needs)} />
          <SmallStat
            label="Kept in the community"
            value={money(state.metrics.collective_savings_cents)}
            accent
          />
        </div>
        {state.activity.length > 0 ? (
          <div className="rows" style={{ marginTop: 16, borderTop: "1px solid var(--rule)" }}>
            {state.activity.slice(0, 4).map((e) => (
              <div key={e.id} className="row" style={{ paddingInline: 0 }}>
                <span style={{ color: "var(--moss)", display: "flex" }}>
                  {e.kind.includes("completed") ? <IconCheck /> : <IconDot />}
                </span>
                <div className="row-body">
                  <div className="small">{e.summary}</div>
                  <div className="tiny faint">{shortTime(e.at)}</div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </Block>

      {lastRun && lastRun.tool_calls.length > 0 ? (
        <details>
          <summary className="tiny faint">
            Last coordination run · {lastRun.tool_calls.length} tools · {lastRun.iterations}{" "}
            iterations · {lastRun.termination_reason}
          </summary>
          <div style={{ marginTop: 8 }}>
            <TracePills names={lastRun.tool_calls.map((t) => t.name)} />
          </div>
        </details>
      ) : null}
    </div>
  );
}

function LedgerRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="ledger-line">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

function SmallStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div>
      <div className="figure-label">{label}</div>
      <div className={`figure-value sm${accent ? " figure-accent" : ""}`}>{value}</div>
    </div>
  );
}
