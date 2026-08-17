/* Needs — the only thing a member ever has to do.
 *
 * Yours first, because that is the part that is actually yours. The community's standing
 * needs sit underneath, because seeing that thirty-three of them exist and none of them
 * are organised into anything is the whole premise of the product.
 */

import { useEffect, useState } from "react";
import { NeedRow, api, shortDate } from "../api";
import { Block, Chip, Empty, IconArrowRight } from "../ui";

export function Needs({
  identity,
  communityName,
  onFind,
  running,
  hasPool,
}: {
  identity: { id: string; display_name: string };
  communityName: string;
  onFind: () => void;
  running: boolean;
  hasPool: boolean;
}) {
  const [needs, setNeeds] = useState<NeedRow[] | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    api.needs().then(setNeeds).catch(() => setNeeds([]));
  }, []);

  if (needs === null) return <Empty>Loading…</Empty>;

  const mine = needs
    .filter((n) => n.household_id === identity.id)
    .sort((a, b) => a.expected_next_need_date.localeCompare(b.expected_next_need_date));
  const others = needs.filter((n) => n.household_id !== identity.id);

  return (
    <div className="stack">
      <header className="stack-sm">
        <h1 className="title">What you buy anyway</h1>
        <p className="lede">
          Tell Pool once, then forget about it. Two numbers do different jobs: how often
          you restock, and how far ahead you are willing to buy if it saves money. Only
          the second one lets Pool bring your order forward to complete somebody else's —
          and if you set it to nothing, nothing is ever moved.
        </p>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h3>Yours</h3>
          <span className="spacer" />
          <span className="tiny faint">{identity.display_name}</span>
        </div>
        {mine.length === 0 ? (
          <Empty>Nothing declared yet.</Empty>
        ) : (
          <div className="rows">
            {mine.map((n) => (
              <div key={n.need_id} className="row">
                <div className="row-body">
                  <div className="row-title">
                    {n.product_name}
                    {n.flexibility_days > 0 ? (
                      <Chip tone="ok">may buy {n.flexibility_days}d early</Chip>
                    ) : (
                      <Chip>never early</Chip>
                    )}
                  </div>
                  <div className="tiny muted">
                    {n.quantity} {n.unit} · about every {n.cadence_days} days · you
                    normally restock {n.routine_lead_days} days ahead
                  </div>
                  <div className="tiny faint">
                    Will not join below {n.min_savings_pct}% saving, and never above{" "}
                    {n.max_spend_display}
                  </div>
                </div>
                <div className="row-tail">
                  <div className="fact-value">{shortDate(n.expected_next_need_date)}</div>
                  <div className="tiny faint">next needed</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Block
        title={`Standing needs across ${communityName}`}
        aside={
          <button className="btn btn-sm" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Hide" : `Show all ${needs.length}`}
          </button>
        }
      >
        <p className="small muted prose">
          {needs.length} standing needs across the community, and not one of them is part
          of a group. Nobody has created a chat, a sign-up sheet or a spreadsheet — they
          each told Pool what they buy and got on with their week. Finding the overlap is
          Pool's job, not theirs.
        </p>
        {!hasPool ? (
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn btn-primary" onClick={onFind} disabled={running}>
              {running ? <span className="spinner" /> : null}
              {running ? "Looking…" : "Find opportunities"}
              {running ? null : <IconArrowRight />}
            </button>
          </div>
        ) : null}
        {showAll ? (
          <div className="panel" style={{ marginTop: 16 }}>
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
                  {others.map((n) => (
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
          </div>
        ) : null}
      </Block>
    </div>
  );
}
