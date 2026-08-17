/* The unglamorous machinery: the fulfilment job as the host sees it, and the ledger an
 * operator has to be able to audit.
 *
 * These two surfaces exist because a coordination product that only has a consumer
 * screen is a mockup. Somebody has to be paid, somebody has to reconcile a declined
 * card, and somebody has to answer for a stale supplier quote.
 */

import { useEffect, useState } from "react";
import { Checklist, OperatorView, api, money, statusCopy } from "../api";
import { Chip, Empty, Figure, IconArrowLeft, IconCheck, IconDot, LedgerLine } from "../ui";

function HostConsole({ poolId }: { poolId: string | null }) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [code, setCode] = useState("");
  const [outcome, setOutcome] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    if (!poolId) {
      setChecklist(null);
      return;
    }
    api.checklist(poolId).then(setChecklist).catch(() => setChecklist(null));
  }, [poolId]);

  if (!poolId || !checklist) {
    return (
      <section className="panel">
        <div className="panel-head">
          <h3>The fulfilment job</h3>
        </div>
        <Empty>
          No job is open. Once a pool has a host and the order has been placed, the
          fulfilment run and its checklist appear here.
        </Empty>
      </section>
    );
  }

  const earnings = checklist.earnings as Record<string, string>;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>The fulfilment job — {checklist.product_name}</h3>
        <span className="spacer" />
        <Chip tone={statusCopy(checklist.status as never).tone}>{checklist.status}</Chip>
      </div>
      <div className="panel-pad stack-sm">
        <div className="grid grid-3">
          <Figure
            label="Collected"
            value={`${checklist.picked_up} / ${checklist.total}`}
            sub={`${checklist.units_total} units in total`}
          />
          <Figure
            label="The host earns"
            value={earnings.total_display ?? "—"}
            accent
            sub="funded by the buyers, never subsidised"
          />
          <Figure
            label="Already earned"
            value={money(Number(earnings.paid_cents ?? 0))}
            sub="a buyer who does not turn up cannot erase pay for the trip"
          />
        </div>

        <div className="inset stack-sm">
          <p className="small">
            <strong>Confirm a handoff.</strong> Type a buyer's one-time code. The server
            checks it — a host cannot mark an order collected without one, and the only
            other route is an operator override that requires a stated reason and is
            audited.
          </p>
          <div className="btn-row">
            <input
              className="btn"
              style={{ minWidth: "11rem", fontFamily: "var(--mono)", letterSpacing: "0.06em" }}
              value={code}
              placeholder="e.g. 4KQ7WMTX"
              aria-label="One-time pickup code"
              onChange={(ev) => setCode(ev.target.value)}
            />
            <button
              className="btn btn-primary btn-sm"
              disabled={!code.trim()}
              onClick={async () => {
                try {
                  const res = await api.redeem(poolId, code.trim(), true);
                  setOutcome({
                    ok: res.ok,
                    message: res.ok ? "Handoff confirmed." : res.reason,
                  });
                } catch (err) {
                  setOutcome({
                    ok: false,
                    message: err instanceof Error ? err.message : String(err),
                  });
                }
                setCode("");
                api.checklist(poolId).then(setChecklist).catch(() => undefined);
              }}
            >
              Confirm
            </button>
          </div>
          {outcome ? (
            <p className={`small${outcome.ok ? "" : " muted"}`}>{outcome.message}</p>
          ) : null}
        </div>
      </div>

      <div className="rows">
        {checklist.orders.map((o) => (
          <div key={o.household_id} className="row">
            <span style={{ color: o.state === "picked_up" ? "var(--moss)" : "var(--ink-faint)", display: "flex" }}>
              {o.state === "picked_up" ? <IconCheck /> : <IconDot />}
            </span>
            <div className="row-body">
              <div className="row-title">{o.display_name}</div>
              <div className="tiny muted">
                {o.units} units · {o.state.replace(/_/g, " ")}
                {o.via ? ` · confirmed by ${o.via}` : ""}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function OperationsView({
  hostPoolId,
  onBack,
}: {
  hostPoolId: string | null;
  onBack: () => void;
}) {
  const [data, setData] = useState<OperatorView | null>(null);

  useEffect(() => {
    api.operator().then(setData).catch(() => setData(null));
  }, []);

  return (
    <div className="stack">
      <header className="stack-sm">
        <div>
          <button className="btn btn-sm btn-ghost" onClick={onBack}>
            <IconArrowLeft />
            Back
          </button>
        </div>
        <h1 className="title" style={{ maxWidth: "24ch" }}>
          Somebody has to be paid, and somebody has to reconcile it
        </h1>
        <p className="lede">
          The parts of a coordination product that are never in the pitch: the job as the
          person carrying the boxes sees it, the supplier quotes a final price is not
          allowed to rest on, and every authorisation and capture with its failure code
          intact.
        </p>
      </header>

      <HostConsole poolId={hostPoolId} />

      {!data ? (
        <Empty>Loading the ledger…</Empty>
      ) : (
        <>
          <section className="panel">
            <div className="panel-head">
              <h3>Supplier offers</h3>
              <span className="spacer" />
              <span className="tiny faint">a final price may never rest on a stale quote</span>
            </div>
            <div className="table-scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>Offer</th>
                    <th>Supplier</th>
                    <th className="r">Unit</th>
                    <th className="r">Case</th>
                    <th>Minimum</th>
                    <th className="r">Verified</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {data.offers.map((o) => (
                    <tr key={o.offer_id}>
                      <td className="mono">{o.offer_id}</td>
                      <td>{o.supplier}</td>
                      <td className="r">{o.unit_price_display}</td>
                      <td className="r">{o.case_units}</td>
                      <td>{o.moq}</td>
                      <td className="r">{o.age_hours}h ago</td>
                      <td>
                        <Chip tone={o.source === "manual_verified" ? "ok" : "info"}>
                          {o.source.replace(/_/g, " ")}
                        </Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.pools.map((p) => (
            <section key={p.pool_id} className="panel">
              <div className="panel-head">
                <h3>{p.product_name}</h3>
                <Chip tone={statusCopy(p.status).tone}>{statusCopy(p.status).label}</Chip>
                <span className="spacer" />
                {p.purchase ? (
                  <span className="tiny mono muted">
                    {String(p.purchase.supplier_reference)} ·{" "}
                    {p.purchase.simulated ? "SIMULATED" : "real"} ·{" "}
                    {String(p.purchase.cases_purchased)} case(s),{" "}
                    {String(p.purchase.units_purchased)} units,{" "}
                    {money(Number(p.purchase.total_cents ?? 0))}
                  </span>
                ) : null}
              </div>
              {p.payments.length === 0 ? (
                <Empty>No authorisations yet.</Empty>
              ) : (
                <div className="rows">
                  {p.payments.map((pay) => (
                    <div key={pay.payment_id} className="row">
                      <div className="row-body">
                        <div className="row-title">
                          {pay.household_name}
                          {pay.failure_code ? <Chip tone="stop">{pay.failure_code}</Chip> : null}
                        </div>
                        <div className="tiny muted">
                          {pay.state.replace(/_/g, " ")} · {pay.provider} ({pay.provider_mode})
                        </div>
                      </div>
                      <div className="row-tail fact-value num">{pay.amount_display}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}

          {data.issues.length > 0 ? (
            <section className="panel">
              <div className="panel-head">
                <h3>Open cases</h3>
              </div>
              <div className="rows">
                {data.issues.map((i) => (
                  <div key={String(i.id)} className="row">
                    <div className="row-body">
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

          {data.failed_runs.length > 0 ? (
            <section className="panel">
              <div className="panel-head">
                <h3>Runs that did not succeed</h3>
                <span className="spacer" />
                <span className="tiny faint">kept, not hidden</span>
              </div>
              <div className="rows">
                {data.failed_runs.map((r) => (
                  <div key={r.run_id} className="row">
                    <div className="row-body">
                      <div className="row-title">
                        <span className="mono">{r.run_id}</span>
                        <Chip tone="warn">{r.outcome.replace(/_/g, " ")}</Chip>
                      </div>
                      <div className="tiny muted">
                        {r.termination_reason}
                        {r.notes.length > 0 ? ` · ${r.notes.join(" · ")}` : ""}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="panel panel-pad">
            <h3 className="section-title" style={{ marginBottom: 12 }}>
              Pool's own economics
            </h3>
            <div className="ledger">
              <LedgerLine
                label="Gross value coordinated"
                value={money(data.metrics.pool_spend_cents)}
              />
              <LedgerLine label="Paid out to hosts" value={money(data.metrics.host_earnings_cents)} />
              <LedgerLine
                label="Card processing recovered"
                value={money(data.metrics.payment_processing_cents)}
              />
              <LedgerLine
                label="Pool's fee, a share of the saving"
                value={money(data.metrics.platform_fee_cents)}
                kind="total"
              />
            </div>
            <p className="tiny muted" style={{ marginTop: 12 }}>
              Pool's own viability is one of the conditions a pool must satisfy before it
              may lock. A platform that quietly subsidises a transaction is a platform
              that stops existing, so "we lose a little on this one" is not an outcome the
              engine will accept.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
