/* Orders — the community's group purchases, past and in flight.
 *
 * Every row says whose it is, and the server decided that.
 *
 * The list is the whole Community's, which is correct: Pool coordinates a community and
 * an order that formed without this member is real work worth seeing. What was wrong is
 * that nothing said so. Home would tell somebody "Pool formed an order for coffee, and
 * your units were not in this one" — honest, careful, and then one click later the list
 * read `6 buyers · 18/18 units` with no marker at all, and the order page said
 * `Buyers 6 — everyone still in`. The prose fixed the contradiction and the next screen
 * reintroduced it.
 *
 * Which orders are this member's comes from `services/relevance.py` and nowhere else: if
 * a screen says "yours", the server decided it (AGENTS.md §8). */

import { AppState, MemberView, money, statusCopy } from "../api";
import { Chip, CoordinatorWait, Empty, IconArrowRight, Meter } from "../ui";

export function Pools({
  state,
  member,
  onOpen,
  onFind,
  running,
  liveDiscovery,
  region,
}: {
  state: AppState;
  /** The server's answer to which orders are this member's. Null before it lands, and
   *  then nothing claims to be theirs — which is the right way round. */
  member: MemberView | null;
  onOpen: (id: string) => void;
  onFind: () => void;
  running: boolean;
  liveDiscovery: boolean;
  region: string | null;
}) {
  const mine = new Set(
    [member?.opportunity?.pool_id, ...(member?.other_pool_ids ?? [])].filter(
      Boolean,
    ) as string[],
  );
  return (
    <div className="stack">
      <header className="stack-sm">
        <h1 className="title">Orders</h1>
        <p className="lede">
          Group orders Pool put together by noticing that several people near you buy the
          same thing. Nobody organised a group.
        </p>
      </header>

      {state.pools.length === 0 ? (
        <section className="panel">
          <Empty>
            No order yet. Pool makes one only when compatible, authorised demand clears
            a supplier's minimum and the all-in price actually beats buying alone.
          </Empty>
          <div className="panel-pad" style={{ paddingTop: 0 }}>
            <button className="btn btn-primary" onClick={onFind} disabled={running}>
              {running ? <span className="spinner" /> : null}
              {running ? "Pool is checking…" : "Ask Pool to check now"}
            </button>
            {running ? <CoordinatorWait live={liveDiscovery} region={region} /> : null}
          </div>
        </section>
      ) : (
        <section className="panel">
          <div className="rows">
            {state.pools.map((p) => {
              const s = statusCopy(p.status);
              const declined = p.member_count - p.buyer_count;
              const isMine = mine.has(p.pool_id);
              return (
                <button key={p.pool_id} className="row" onClick={() => onOpen(p.pool_id)}>
                  <div className="row-body">
                    <div className="row-title">
                      {p.product_name}
                      <Chip tone={s.tone}>{s.label}</Chip>
                      {/* Said either way, never only when the news is good. A row with a
                          marker on some orders and nothing on others makes the absence
                          ambiguous, and the ambiguous reading is the flattering one. */}
                      <span className={isMine ? "scope-mine" : "scope-theirs"}>
                        {isMine ? "You are in this" : "Not yours"}
                      </span>
                    </div>
                    <div className="tiny muted" style={{ marginBottom: 6 }}>
                      {p.buyer_count} buyers
                      {declined > 0
                        ? ` (${p.member_count} on record — ${declined} declined)`
                        : ""}{" "}
                      · {p.provisional_units}/{p.threshold_units} units · {p.pickup_site}
                      {p.host ? ` · ${p.host.display_name} carrying it` : " · host needed"}
                    </div>
                    <Meter value={p.provisional_units} max={p.threshold_units} />
                  </div>
                  <div className="row-tail">
                    <div className="fact-value num">{p.savings_pct || "—"}</div>
                    <div className="tiny faint">
                      {p.economics ? money(p.economics.net_savings_cents) : "estimating"}
                    </div>
                  </div>
                  <IconArrowRight />
                </button>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
