/* Home — what a member of Demo University sees when they open Pool.
 *
 * This is the product, not an explanation of the product. It is composed as a short
 * narrative rather than as an inventory of everything the system can show:
 *
 *   what Pool needs from me → what Pool found for me → what Pool handled on its own
 *   → what I buy anyway → what Pool may decide for me
 *
 * Each section appears only when it has something to say, so the passive state is one
 * card and the busiest state is five. Anything a member does not need in order to act
 * — run ids, tool sequences, lifecycle internals — hangs off the pool record instead.
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
  PoolMember,
  PoolStatus,
  PoolView,
  ProductCandidate,
  api,
  money,
  pct,
  shortDateOnly,
  shortTime,
  statusCopy,
} from "../api";
import { autonomyModeCopy, blockingRuleExplanation } from "../labels";
import { ConvergenceFigure } from "../brand";
import { ProductSearch } from "../product-search";
import { productImage, productInitials } from "../products";
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
  /* The deterministic policy engine's own sentence, passed through. The rule's machine
     name is an identifier; this is the answer to "why are you asking me?". */
  const why = blockingRuleExplanation(decision.facts);
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
      {why ? (
        <p className="small muted">Pool asked instead of deciding: {why}.</p>
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
          <span className="small faint">answer by {shortTime(decision.expires_at)}</span>
        ) : null}
      </div>
    </div>
  );
}

/** The photograph the member picked from, carried through to the finished order.
 *  Falls back to a category tile, which is the ordinary state for curated goods. */
function PoolThumb({ pool }: { pool: PoolView }) {
  const src = productImage(pool.image_ref ?? "");
  return (
    <span className="pool-thumb" aria-hidden="true">
      {src ? (
        <img src={src} alt="" loading="lazy" decoding="async" />
      ) : (
        <span className="product-thumb-fallback">
          {productInitials(pool.brand ?? "", pool.product_name)}
        </span>
      )}
    </span>
  );
}

/* --------------------------------------------------------------- opportunity */

/** What to call this pool on *this* member's home screen.
 *
 *  A pool is one object with one lifecycle, but it is a different thing to somebody who
 *  is in it than to somebody who is not, and it is a different thing again once the
 *  money has moved. The record keeps the canonical status chip; this only decides the
 *  sentence above it. */
function poolHeading(status: PoolStatus, mine: boolean): string {
  if (status === "completed") return mine ? "Your order" : "The community's order";
  if (status === "distributing") return mine ? "Ready to collect" : "Pickup is open";
  if (status === "locked" || status === "purchase_ready" || status === "purchased") {
    return mine ? "Your order is on the way" : "The order is on its way";
  }
  if (status === "failed" || status === "expired") return "This one did not go ahead";
  return mine ? "Pool found something for you" : "Pool found overlapping demand";
}

function OpportunityCard({
  pool,
  mine,
  onOpen,
  onShowAgent,
}: {
  pool: PoolView;
  /** This member's own membership row, when the server says they have one. */
  mine: PoolMember | null;
  onOpen: () => void;
  /* Takes the pool id rather than firing a bare signal: the card is the only thing that
     knows which pool it drew, and the proof it offers has to be that pool's proof. */
  onShowAgent: (poolId: string) => void;
}) {
  const s = statusCopy(pool.status);
  /* The member's own figures when they are in the pool, the group's otherwise. Both are
     server strings; this only chooses which of the two to lead with.

     Before a fulfiller accepts there is no exact price — their pay is part of it — but
     there *is* a stored estimate, written when the pool was formed. Showing it labelled
     is better than showing nothing, and better than deriving a second one here. */
  const finalCost = mine?.final_cost_display ?? "";
  const estimatedCost = mine?.estimated_cost_display ?? "";
  const myCost = finalCost || estimatedCost;
  const provisional = Boolean(mine) && !finalCost;
  const savings = mine ? mine.savings_pct : pool.savings_pct;
  const others = Math.max(0, pool.buyer_count - (mine ? 1 : 0));
  const startsAt = pool.timing?.distribution_starts_at ?? "";

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{poolHeading(pool.status, Boolean(mine))}</h2>
        <Chip tone={s.tone}>{s.label}</Chip>
      </div>
      <div className="panel-pad stack-sm">
        <div className="row-between" style={{ alignItems: "flex-start", gap: 18 }}>
          <div className="pool-product">
            {/* The same photograph the member picked from. Small, because the product is
                settled by now and the money is what they came back for. */}
            <PoolThumb pool={pool} />
            <div>
            <div className="display" style={{ fontSize: 30, lineHeight: 1.1 }}>
              {pool.brand ? <span className="pool-brand">{pool.brand}</span> : null}
              {pool.product_name}
            </div>
            {mine ? (
              <p className="small" style={{ marginTop: 8 }}>
                <strong>
                  Your {mine.units} {pool.unit}
                  {mine.units === 1 ? "" : "s"}
                  {myCost ? ` · ${provisional ? "about " : ""}${myCost}` : ""}
                </strong>
                {myCost && mine.baseline_display
                  ? ` instead of ${mine.baseline_display} buying alone`
                  : ""}
              </p>
            ) : null}
            <p className="small muted" style={{ marginTop: mine ? 4 : 6 }}>
              {mine
                ? `With ${others} ${others === 1 ? "other" : "others"} · collect from ${pool.pickup_site}`
                : `${pool.buyer_count} members · ${pool.provisional_units} units · collect from ${pool.pickup_site}`}
              {pool.host ? ` · ${pool.host.display_name} is carrying it` : ""}
              {startsAt && (pool.status === "distributing" || pool.status === "purchased")
                ? ` · ${shortTime(startsAt)}`
                : ""}
            </p>
            </div>
          </div>
          {savings ? (
            <div className="figure-tail">
              <div className="figure-value sm figure-accent">{savings}</div>
              <div className="small faint">
                {mine ? "you save" : pool.is_estimate ? "estimated" : "less than retail"}
              </div>
            </div>
          ) : (
            /* Not a dash. Before a fulfiller accepts there is no exact price, because
               their pay is part of it — so the slot names the invariant that is holding
               rather than leaving an empty figure, and it never contradicts the
               estimate shown on the line above it. */
            <div className="figure-tail">
              <div className="fact-value">{provisional ? "Not final yet" : "Not priced yet"}</div>
              <div className="small faint" style={{ maxWidth: "20ch" }}>
                {provisional
                  ? "a fulfiller's pay is part of the price"
                  : "fixed once a fulfiller accepts"}
              </div>
            </div>
          )}
        </div>

        {/* A pool that did not go ahead has to say so where the member is, not only on
            its own record. The server writes the reason; this only shows it. */}
        {pool.failure_reason ? (
          <div className="banner banner-warn">
            <span>{pool.failure_reason}</span>
          </div>
        ) : null}

        <Meter value={pool.provisional_units} max={pool.threshold_units} />
        <p className="small muted">
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
            <button className="btn btn-sm" onClick={() => onShowAgent(pool.pool_id)}>
              <ActorTag actor="agent" label="Technical proof for this run" />
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

/** The first screen of a product nobody has used before.
 *
 *  A cold visitor was previously shown "24 members declared 33 standing needs" above a
 *  button marked *Find opportunities*, and had to infer from a convergence diagram what
 *  they were supposed to do. That is backwards: the member's job comes first, and the
 *  agent's job is what happens as a result. So when this account has declared nothing,
 *  Home is one instruction and one box.
 *
 *  The search is live here rather than a link, because the shortest path from "what is
 *  this" to "oh, I see" is typing something you actually buy and recognising it. */
function FirstUseCard({ onStartNeed }: { onStartNeed: (p: ProductCandidate) => void }) {
  /* One version of this, not two. An earlier draft softened the headline to "anything
     *else* you buy?" once the account had a declaration — which is the copy almost
     everybody actually sees, since a seeded member starts with one. That buried the
     product's whole premise behind a word that assumes context a new visitor does not
     have. The strong sentence is true either way, so it is the only one. */
  return (
    <section className="panel panel-lead">
      <div className="panel-pad stack-sm">
        <h2 className="display" style={{ fontSize: 30, margin: 0 }}>
          Tell Pool something you buy anyway.
        </h2>
        <p className="lede" style={{ marginTop: 0 }}>
          That is the whole job. Pool watches for other people near you who need the same
          thing, works out whether buying it together is actually cheaper, and comes back
          to you only when it needs an answer.
        </p>
        <ProductSearch
          onSelect={onStartNeed}
          /* Same answer as the full form gives: a person may declare something Pool
             cannot source yet. The server stores it with no substitute group and no
             supplier, so the need is real and no pool can form for it. */
          onUnresolved={(query) => {
            void api.customProduct(query).then(onStartNeed).catch(() => {});
          }}
        />
        <p className="small muted">
          You are not creating a group and not inviting anyone. Nobody sees what you
          declared.
        </p>
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
  region,
}: {
  running: boolean;
  onFind: () => void;
  memberCount: number;
  needCount: number;
  liveDiscovery: boolean;
  region: string | null;
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
              {running ? "Coordinator running" : "Run Pool now"}
            </button>
          </div>
          {/* The honest version of the button. Pool is designed to do this on its own
              schedule; this deployment has no scheduler running, and saying so is
              cheaper than implying a background job that does not exist (AGENTS.md §8).
              The un-deployed `PoolStack` carries the EventBridge rule, and the judge
              account deliberately has zero rules in it. */}
          <p className="tiny faint prose">
            In the real product this runs by itself on the community's pool day. Nothing
            is scheduled in this demo account, so the coordinator starts when you press
            the button.
          </p>
          {running ? <CoordinatorWait live={liveDiscovery} region={region} /> : null}
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
  running,
  busyDecision,
  onFind,
  onOpenPool,
  onRespond,
  onShowAgent,
  onStartNeed,
  onGoCommunity,
  liveDiscovery,
  region,
}: {
  state: AppState;
  identity: { id: string; display_name: string };
  running: boolean;
  busyDecision: string | null;
  onFind: () => void;
  onOpenPool: (id: string) => void;
  onRespond: (id: string, approve: boolean) => void;
  onShowAgent: (poolId: string) => void;
  onStartNeed: (product: ProductCandidate | null) => void;
  onGoCommunity: () => void;
  liveDiscovery: boolean;
  region: string | null;
}) {
  const [needs, setNeeds] = useState<NeedRow[]>([]);
  const [me, setMe] = useState<MemberView | null>(null);
  const [hosting, setHosting] = useState<HostOpportunities | null>(null);
  /** The headline pool's full record. The list on `/api/state` carries no memberships,
   *  and this member's own allocation and price are the reason the card exists. */
  const [detail, setDetail] = useState<PoolView | null>(null);

  const pool = state.pools[0] ?? null;
  const poolId = pool?.pool_id ?? "";
  const poolStatus = pool?.status ?? "";

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

  useEffect(() => {
    if (!poolId) {
      setDetail(null);
      return;
    }
    api.pool(poolId).then(setDetail).catch(() => setDetail(null));
  }, [poolId, poolStatus, state.workspace, state.decisions.length]);

  const mine = needs
    .filter((n) => n.household_id === identity.id)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  const forMe = state.decisions.filter((d) => d.household_id === identity.id);
  const forOthers = state.decisions.length - forMe.length;
  const myMembership =
    detail && detail.pool_id === poolId
      ? (detail.members ?? []).find((m) => m.household_id === identity.id) ?? null
      : null;
  const m = state.metrics;
  const settled = state.pools.length > 0;

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
                <div className="small faint">you earn</div>
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

      {/* Before any pool exists, the member's own job comes first and the coordinator's
          comes second. A cold visitor previously landed on "24 members declared 33
          standing needs" above a button marked *Find opportunities*, and had to work out
          from a diagram what they were meant to do. The order is the fix. */}
      {!pool ? <FirstUseCard onStartNeed={onStartNeed} /> : null}

      {pool ? (
        <OpportunityCard
          pool={pool}
          mine={myMembership}
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
          region={region}
        />
      )}

      {forOthers > 0 ? (
        <p className="small muted">
          {forOthers} other {forOthers === 1 ? "person is" : "people are"} being asked
          something too. In the real product they answer on their own phone; here you can
          answer for them from <strong>Demo controls</strong>.
        </p>
      ) : null}

      {/* One community block, not two. Before any pool exists it states the premise —
          independent declarations, no groups. Afterwards it states the result, in the
          two currencies this product actually saves: money, and the attention it took
          nobody to arrange. Both halves are sums over stored rows for the whole
          Community, so both are labelled that way. */}
      <Block
        title={
          settled
            ? `What Pool did across ${state.community?.name ?? "your community"}`
            : `Across ${state.community?.name ?? "your community"}`
        }
        aside={
          <button className="btn btn-sm btn-ghost" onClick={onGoCommunity}>
            {settled ? "Where the money went" : "See the community"}
            <IconArrowRight />
          </button>
        }
      >
        {settled ? (
          <>
            {/* The agent's work leads here, because that is what Home is missing and
                what Community is not: Community opens on the money. The money still
                appears, and it reads $0.00 until money actually moves. */}
            <div className="grid grid-3">
              <SmallStat
                label="Things Pool did on its own"
                value={String(m.coordination_actions_automated)}
                accent
              />
              <SmallStat
                label="Times it had to ask a person"
                value={String(m.human_decisions_requested)}
              />
              <SmallStat
                label="Kept in the community"
                value={money(m.collective_savings_cents)}
              />
            </div>
            {m.commitments_without_asking > 0 || m.pools_recovered > 0 ? (
              <p className="small muted" style={{ marginTop: 12 }}>
                {m.commitments_without_asking > 0
                  ? `${m.commitments_without_asking} commitments were made without asking, each one inside the limits that member had already stored.`
                  : ""}
                {m.pools_recovered > 0
                  ? ` ${m.pools_recovered} order${m.pools_recovered === 1 ? " was" : "s were"} repaired after a payment failed.`
                  : ""}
              </p>
            ) : null}
          </>
        ) : (
          <div className="grid grid-3">
            <SmallStat label="Members" value={String(state.counts.members)} />
            <SmallStat label="Standing needs" value={String(state.counts.needs)} />
            <SmallStat label="Groups anyone organised" value="0" />
          </div>
        )}
        {state.activity.length > 0 ? (
          <div className="rows" style={{ marginTop: 16, borderTop: "1px solid var(--rule)" }}>
            {state.activity.slice(0, 3).map((e) => (
              <div key={e.id} className="row" style={{ paddingInline: 0 }}>
                <span style={{ color: "var(--moss)", display: "flex" }}>
                  {e.kind.includes("completed") ? <IconCheck /> : <IconDot />}
                </span>
                <div className="row-body">
                  <div className="small">{e.summary}</div>
                  <div className="small faint">{shortTime(e.at)}</div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </Block>

      <section className="panel">
        <div className="panel-head">
          <h2>What you buy anyway</h2>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={() => onStartNeed(null)}>
            Add something
          </button>
        </div>
        {mine.length === 0 ? (
          <Empty>Nothing yet. Tell Pool what you buy and it takes over from there.</Empty>
        ) : (
          <div className="rows">
            {mine.map((n) => (
              <div key={n.need_id} className="row">
                <div className="row-body">
                  <div className="row-title">{n.product_name}</div>
                  <div className="small muted">
                    {n.quantity} {n.unit} · about every {n.cadence_days} days
                    {n.flexibility_days > 0
                      ? ` · happy to buy up to ${n.flexibility_days} days early if it saves money`
                      : " · not willing to buy early"}
                  </div>
                </div>
                <div className="row-tail">
                  <div className="fact-value">{shortDateOnly(n.expected_next_need_date)}</div>
                  <div className="small faint">next needed</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Collapsed, because the honest answer to "what may Pool decide for you" is a
          single sentence and the four limits behind it are only consulted when that
          sentence says yes. Opening it is how somebody checks the arithmetic. */}
      {me ? (
        <details className="block">
          {/* The label stays a label — `.section-title` is uppercase, and a
              seventy-character sentence set in caps is not a sentence anyone reads. The
              answer sits beside it in ordinary case, because the answer is the point. */}
          <summary className="autonomy-summary">
            <span className="section-title">When Pool may act for you</span>
            <strong>{autonomyModeCopy(me.autonomy_display.mode)}</strong>
          </summary>
          <div className="grid grid-lede" style={{ marginTop: 14 }}>
            <p className="small muted prose">
              Every limit below has to pass as well. When any one of them does not, Pool
              stops and asks you instead of deciding.
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
