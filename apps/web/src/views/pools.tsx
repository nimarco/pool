/* Pools — the community's orders, past and in flight. */

import { AppState, money, statusCopy } from "../api";
import { Chip, CoordinatorWait, Empty, IconArrowRight, Meter } from "../ui";

export function Pools({
  state,
  onOpen,
  onFind,
  running,
  liveDiscovery,
}: {
  state: AppState;
  onOpen: (id: string) => void;
  onFind: () => void;
  running: boolean;
  liveDiscovery: boolean;
}) {
  return (
    <div className="stack">
      <header className="stack-sm">
        <h1 className="title">Pools</h1>
        <p className="lede">
          An order several people are making together. Each one exists because their
          standing needs lined up, not because anybody created a group.
        </p>
      </header>

      {state.pools.length === 0 ? (
        <section className="panel">
          <Empty>
            No pool yet. Pool forms one when enough compatible demand exists to clear a
            supplier's minimum without anybody being asked to buy earlier than they agreed
            to.
          </Empty>
          <div className="panel-pad" style={{ paddingTop: 0 }}>
            <button className="btn btn-primary" onClick={onFind} disabled={running}>
              {running ? <span className="spinner" /> : null}
              {running ? "Coordinator running" : "Find opportunities"}
            </button>
            {running ? <CoordinatorWait live={liveDiscovery} /> : null}
          </div>
        </section>
      ) : (
        <section className="panel">
          <div className="rows">
            {state.pools.map((p) => {
              const s = statusCopy(p.status);
              const declined = p.member_count - p.buyer_count;
              return (
                <button key={p.pool_id} className="row" onClick={() => onOpen(p.pool_id)}>
                  <div className="row-body">
                    <div className="row-title">
                      {p.product_name}
                      <Chip tone={s.tone}>{s.label}</Chip>
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
