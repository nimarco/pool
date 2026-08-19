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
  RunReport,
  RunReportResult,
  StandingDemand,
  api,
  money,
  pct,
  shortDateOnly,
  shortTime,
  statusCopy,
} from "../api";
import { autonomyModeCopy, blockingRuleExplanation } from "../labels";
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
  substituteFor,
  whyItWorked,
  onOpen,
  onShowAgent,
}: {
  pool: PoolView;
  /** This member's own membership row, when the server says they have one. */
  mine: PoolMember | null;
  /** What this member actually typed, when the pool is buying an authorised
   *  substitute for it. The card leads with the pool's name and photograph, so
   *  without this the two silently disagree with the declaration behind them. */
  substituteFor: string;
  /** Why this order worked, as the run that formed it established — supplier minimum,
   *  case fit, which tier won, which pickup point. Empty unless the run on screen is
   *  the one that produced this pool, because these are facts about *that* run rather
   *  than about the world now. */
  whyItWorked: string[];
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
            {substituteFor ? (
              <p className="small muted" style={{ marginTop: 6 }}>
                A substitute for the <strong>{substituteFor}</strong> you declared —
                allowed by the substitution rule you set.
              </p>
            ) : null}
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

        {whyItWorked.length > 0 ? (
          <details className="inset">
            <summary className="small">
              <strong>Why this worked</strong>
            </summary>
            <ul className="fact-list" style={{ marginTop: 10 }}>
              {whyItWorked.map((f: string) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </details>
        ) : null}

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
 *  There is deliberately no **Run Pool now** here. The button asks Pool to look at what
 *  *you* buy, and an account that has said nothing has asked nothing — offering it would
 *  promise an answer the run cannot have.
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

/* ------------------------------------------------------------- before the run */

/** One declaration, and the overlap that has accumulated around it on its own.
 *
 *  Three things, in order: what I told Pool, what already exists near it, and what is
 *  still genuinely unknown. Every figure is a server count over stored declarations —
 *  nothing here is a verdict, because none has been earned yet.
 *
 *  This replaced a diagram of the canonical whey arithmetic: eight people due, eighteen
 *  units, two pulled forward, twenty-four. Drawn before the run, it told a judge the
 *  answer and then asked them to watch Pool produce it. What belongs here is the
 *  question. */
function StandingLine({ demand, need }: { demand: StandingDemand; need: NeedRow | null }) {
  const unit = (n: number) => (n === 1 ? demand.unit : `${demand.unit}s`);
  const together = demand.compatible_units + demand.my_units;
  return (
    <div className="standing-line">
      <div className="standing-head">
        <span className="standing-product">{demand.product_name}</span>
        <span className="small faint">
          {demand.my_units} {unit(demand.my_units)}
          {need ? ` · about every ${need.cadence_days} days` : ""}
          {need && need.flexibility_days > 0
            ? ` · may be bought up to ${need.flexibility_days} days early`
            : need
              ? " · never early"
              : ""}
        </span>
      </div>
      {!demand.has_supplier ? (
        <p className="small muted">
          No supplier Pool has verified sells this in bulk yet, so there is nothing for it
          to coordinate. Your declaration stays on file.
        </p>
      ) : (
        <>
          <p className="small muted">
            {demand.compatible_members > 0 ? (
              <>
                <strong>{demand.compatible_members}</strong> other{" "}
                {demand.compatible_members === 1 ? "member has" : "members have"}{" "}
                independently declared something this could be bought for —{" "}
                {demand.compatible_units} {unit(demand.compatible_units)}. With yours,{" "}
                {together}.
              </>
            ) : (
              <>Nobody else near you has declared anything compatible yet.</>
            )}
            {demand.minimum_units
              ? ` The supplier's best price starts at ${demand.minimum_units}.`
              : ""}
          </p>
          {demand.sourceable_product_name ? (
            <p className="tiny faint">
              The order Pool could form would buy {demand.sourceable_product_name}, which
              your substitution rule allows.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function StandingCard({
  demand,
  needs,
  running,
  onFind,
  liveDiscovery,
  region,
  hasAnswer,
}: {
  demand: StandingDemand[];
  needs: NeedRow[];
  running: boolean;
  onFind: () => void;
  liveDiscovery: boolean;
  region: string | null;
  /** True once this session has a run report on screen, so the card stops leading and
   *  becomes the place to run again. */
  hasAnswer: boolean;
}) {
  const byNeed = new Map(needs.map((n) => [n.need_id, n]));
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{hasAnswer ? "Still standing" : "What you buy, and what is around it"}</h2>
      </div>
      <div className="panel-pad stack-sm">
        <div className="standing">
          {demand.map((d) => (
            <StandingLine key={d.need_id} demand={d} need={byNeed.get(d.need_id) ?? null} />
          ))}
        </div>
        {/* The honest half. These are the things a run decides and a screen cannot, and
            naming them is what stops the counts above reading as a promise. */}
        <p className="small muted prose">
          Whether an order actually works still depends on things Pool has not checked
          yet: whether those people can reach one pickup point, whether their restock
          dates overlap with yours, whether the units fill whole cases, and whether the
          all-in price beats buying alone.
        </p>
        <div className="btn-row">
          <button className="btn btn-primary" onClick={onFind} disabled={running}>
            {running ? <span className="spinner" /> : null}
            {running ? "Coordinator running" : hasAnswer ? "Run Pool again" : "Run Pool now"}
          </button>
        </div>
        {/* Pool is designed to do this on its own schedule; this deployment has no
            scheduler running, and saying so is cheaper than implying a background job
            that does not exist (AGENTS.md §8). */}
        <p className="tiny faint prose">
          In the real product this runs by itself on the community&apos;s pool day. Nothing
          is scheduled in this demo account, so the coordinator starts when you press the
          button.
        </p>
        {running ? (
          <CoordinatorWait
            live={liveDiscovery}
            region={region}
            /* Named before the run starts, from the member's own declarations, so this
               describes the *request* rather than narrating work the browser cannot
               see. Only when there is exactly one — with several, which of them a
               bounded run takes on is the server's decision and not this component's
               to guess. */
            objective={
              demand.length === 1
                ? `Pool is checking your ${demand[0].product_name} declaration against what this community has declared.`
                : undefined
            }
          />
        ) : null}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- after the run */

/** What the run concluded about this member's own declarations.
 *
 *  Every line is the server's, assembled from the evaluation records that run wrote
 *  while it was running. The browser decides nothing here: not which pool is theirs, not
 *  whether a product was evaluated, not why anything was refused. A result the run did
 *  not reach says so rather than being given a plausible reason.
 *
 *  Orders this member is *in* are deliberately absent — those lead with the order card
 *  above, and repeating the outcome twice would make one answer look like two. */
function RunAnswer({
  results,
  onOpenPool,
}: {
  results: RunReportResult[];
  onOpenPool: (id: string) => void;
}) {
  const nothing = results.every(
    (r) => r.result === "declined" || r.result === "not_investigated",
  );
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{nothing ? "Nothing worth coordinating yet" : "What Pool found"}</h2>
        <span className="spacer" />
        <ActorTag actor="agent" label="Pool checked" />
      </div>
      <div className="panel-pad stack-sm">
        {results.map((r) => (
          <div key={r.need_id} className="run-result">
            <div className="standing-head">
              <span className="standing-product">{r.product_name}</span>
              {r.pool_id ? (
                <button className="linkish small" onClick={() => onOpenPool(r.pool_id)}>
                  Open the order
                </button>
              ) : null}
            </div>
            <p className="small">{r.headline}</p>
            {r.facts.length > 0 ? (
              <ul className="fact-list">
                {r.facts.map((f: string) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

/** Real work Pool is doing for other people. Never this member's answer. */
function ElsewhereCard({
  pools,
  onOpenPool,
  communityName,
}: {
  pools: PoolView[];
  onOpenPool: (id: string) => void;
  communityName: string;
}) {
  return (
    <section className="panel panel-muted">
      <div className="panel-head">
        <h2>Elsewhere in {communityName}</h2>
      </div>
      <div className="panel-pad">
        {pools.map((p) => (
          <p key={p.pool_id} className="small muted">
            Pool is coordinating <strong>{p.product_name}</strong> for {p.buyer_count}{" "}
            {p.buyer_count === 1 ? "member" : "members"}. You are not part of this order.{" "}
            <button className="linkish" onClick={() => onOpenPool(p.pool_id)}>
              See it
            </button>
          </p>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------------- view */

export function Home({
  state,
  identity,
  member,
  report,
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
  /** The server's view of this identity, including which pool is genuinely theirs.
   *  Fetched by the shell, because Needs needs the same answer and this is the most
   *  expensive read the API serves. */
  member: MemberView | null;
  /** What the last member-triggered run concluded about this member's declarations.
   *  Null before any run in this session, and null whenever the server says the run was
   *  not this member's — which is what stops a community scan, or a previous member's
   *  run, becoming the answer on this screen. */
  report: RunReport | null;
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
  const [hosting, setHosting] = useState<HostOpportunities | null>(null);
  /** The headline pool's full record. The list on `/api/state` carries no memberships,
   *  and this member's own allocation and price are the reason the card exists. */
  const [detail, setDetail] = useState<PoolView | null>(null);

  /* Which pool Home leads with is the server's answer, not this component's.
   *
   * It used to be `state.pools[0]` — the oldest pool in the workspace, whoever it
   * belonged to. A member who had declared coffee pressed Run Pool now, the coordinator
   * correctly formed a whey protein order out of ten *other* students' declarations,
   * and Home led with it. `/api/members/{id}` now answers "which pool is mine, and
   * which declaration put me in it" from membership and need lineage, and answers
   * `null` when the honest answer is none. */
  const poolId = member?.opportunity?.pool_id ?? "";
  const poolStatus = member?.opportunity?.status ?? "";
  /* `detail` is only usable as a fallback while it is a record of *this* pool. Without
     the id check, switching from one pool to another renders the previous product's
     name and photograph for a frame — the stale-card version of the same bug. */
  const pool = poolId
    ? state.pools.find((p) => p.pool_id === poolId) ??
      (detail && detail.pool_id === poolId ? detail : null)
    : null;

  useEffect(() => {
    api.needs().then((view) => setNeeds(view.needs)).catch(() => setNeeds([]));
  }, [state.workspace]);

  useEffect(() => {
    // Cleared first: switching identity must never leave the previous member's pool
    // record on screen while the next answer loads.
    setDetail(null);
    // Pool is three-sided, and one of those sides is this same person on a different
    // day. If they are carrying an order, that is the most important thing on their
    // home screen.
    api.hostOpportunities(identity.id).then(setHosting).catch(() => setHosting(null));
    // `activity.length` is in here as the cheapest honest proxy for "the workspace
    // changed": every coordination write logs one. Without it a run that added this
    // member to an *existing* pool would leave the previous answer on screen.
  }, [
    identity.id,
    state.workspace,
    state.pools.length,
    state.decisions.length,
    state.activity.length,
  ]);

  useEffect(() => {
    if (!poolId) {
      setDetail(null);
      return;
    }
    api.pool(poolId).then(setDetail).catch(() => setDetail(null));
  }, [poolId, poolStatus, state.workspace, state.decisions.length]);

  /* Retired declarations are excluded: `/api/needs` serves the whole table so the
     community view can show it, and a member who has stopped buying something should
     not find it still listed under "what you buy anyway". The matcher stopped counting
     them at the same time. */
  const mine = needs
    .filter((n) => n.household_id === identity.id && n.active)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  const forMe = state.decisions.filter((d) => d.household_id === identity.id);
  const forOthers = state.decisions.length - forMe.length;
  const myMembership =
    detail && detail.pool_id === poolId
      ? (detail.members ?? []).find((m) => m.household_id === identity.id) ?? null
      : null;
  const m = state.metrics;
  const settled = state.pools.length > 0;
  /* Pools the coordinator formed for other people. Real work, worth saying so — but on
   * the community's terms, never as this member's result.
   *
   * Every pool the server says is theirs is excluded, not just the one being led with:
   * a member in a settled order *and* a live one would otherwise have been told "you
   * are not in it" about a pool they are in. */
  const notMine = new Set([poolId, ...(member?.other_pool_ids ?? [])]);
  const elsewhere = state.pools.filter((p) => !notMine.has(p.pool_id));

  /* What the run concluded, split by whether the member ended up in the order.
   *
   * An order they are in leads with the order card, and its "why this worked" lines
   * hang off that rather than becoming a second answer above it. Everything else — a
   * refusal, an order that filled without them, a declaration the run did not reach —
   * is what the answer card is for. */
  const mineFromRun = report?.is_mine ? report.results : [];
  const included = mineFromRun.filter((r: RunReportResult) => r.result === "formed_included");
  const answers = mineFromRun.filter(
    (r: RunReportResult) => r.result !== "formed_included" && r.result !== "already_coordinated",
  );
  const whyItWorked = included.find((r: RunReportResult) => r.pool_id === poolId)?.facts ?? [];

  /* Declarations still waiting on Pool. A need already inside an order has its answer
     on the order card, so listing it here again would ask the same question twice. */
  const pooledNeedIds = new Set(
    [
      member?.opportunity?.need_id,
      ...mineFromRun.filter((r: RunReportResult) => r.pool_id).map((r: RunReportResult) => r.need_id),
    ].filter(Boolean) as string[],
  );
  const standing = (member?.standing_demand ?? []).filter(
    (d) => !pooledNeedIds.has(d.need_id),
  );

  return (
    <div className="stack">
      <header className="row-between">
        <div>
          <h1 className="title">
            {greeting()}, {identity.display_name.split(" ")[0]}
          </h1>
          <p className="small muted" style={{ marginTop: 4 }}>
            {state.community?.name ?? "Demo University"}
            {member?.community_membership
              ? ` · verified by ${member.community_membership.verification_method.replace(/_/g, " ")}`
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

      {/* Only for an account that has told Pool nothing yet.
          Setting up now ends with the member declaring something, so leading Home with
          "tell Pool what you buy" would ask again, thirty seconds later, for what they
          just did — a second onboarding wearing the product's clothes. Once they have a
          declaration the coordinator's card leads instead, and adding another lives with
          the rest of their needs further down where it belongs. */}
      {!pool && mine.length === 0 ? <FirstUseCard onStartNeed={onStartNeed} /> : null}

      {/* The order this member is actually in, and — when the run that formed it is the
          one on screen — the deterministic facts that made it work. */}
      {pool ? (
        <OpportunityCard
          pool={pool}
          mine={myMembership}
          substituteFor={
            member?.opportunity && !member.opportunity.is_exact_product
              ? member.opportunity.declared_product_name
              : ""
          }
          whyItWorked={whyItWorked}
          onOpen={() => onOpenPool(pool.pool_id)}
          onShowAgent={onShowAgent}
        />
      ) : null}

      {/* Everything else the run concluded. Absent before any run in this session, and
          absent whenever the server says the run was not this member's. */}
      {answers.length > 0 ? (
        <RunAnswer results={answers} onOpenPool={onOpenPool} />
      ) : null}

      {/* What is still standing, and the button that asks Pool about it. */}
      {standing.length > 0 ? (
        <StandingCard
          demand={standing}
          needs={mine}
          running={running}
          onFind={onFind}
          liveDiscovery={liveDiscovery}
          region={region}
          hasAnswer={mineFromRun.length > 0}
        />
      ) : null}

      {elsewhere.length > 0 ? (
        <ElsewhereCard
          pools={elsewhere}
          onOpenPool={onOpenPool}
          communityName={state.community?.name ?? "your community"}
        />
      ) : null}

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
      {member ? (
        <details className="block">
          {/* The label stays a label — `.section-title` is uppercase, and a
              seventy-character sentence set in caps is not a sentence anyone reads. The
              answer sits beside it in ordinary case, because the answer is the point. */}
          <summary className="autonomy-summary">
            <span className="section-title">When Pool may act for you</span>
            <strong>{autonomyModeCopy(member.autonomy_display.mode)}</strong>
          </summary>
          <div className="grid grid-lede" style={{ marginTop: 14 }}>
            <p className="small muted prose">
              Every limit below has to pass as well. When any one of them does not, Pool
              stops and asks you instead of deciding.
            </p>
            <div className="ledger">
              <LedgerRow label="Minimum saving before it acts" value={member.autonomy_display.min_savings} />
              <LedgerRow label="Most it may ever spend" value={member.autonomy_display.max_spend} />
              <LedgerRow label="Furthest you will walk" value={member.autonomy_display.max_travel} />
              <LedgerRow
                label="Substitutions"
                value={member.autonomy_display.substitution.replace(/_/g, " ")}
              />
              <LedgerRow
                label="Payment method saved"
                value={member.has_payment_method ? "yes" : "no"}
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
