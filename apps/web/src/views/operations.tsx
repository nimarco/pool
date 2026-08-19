/* The unglamorous machinery: the fulfilment job as the host sees it, and the ledger an
 * operator has to be able to audit.
 *
 * These two surfaces exist because a coordination product that only has a consumer
 * screen is a mockup. Host compensation has to be accounted for, somebody has to reconcile a declined
 * card, and somebody has to answer for a stale supplier quote.
 */

import { useEffect, useState } from "react";
import { Checklist, OperatorView, SupplierUpdates, api, money, statusCopy } from "../api";
import { Chip, Empty, Figure, IconArrowLeft, IconCheck, IconDot, LedgerLine } from "../ui";

/** Supplier quotes arriving from outside, and what they do to demand that is already
 *  standing.
 *
 *  This is an **operator** surface, and it is on Operations rather than Home for a
 *  reason that is part of the product rather than a layout preference: a member cannot
 *  conjure a wholesale quote. What a member does is say what they buy. What changes
 *  whether that can be acted on is the world.
 *
 *  Everything numeric below is rendered from the server and sent back as a key. There
 *  is no input here, and there is no request shape in which this component could name a
 *  price — which is the difference between demonstrating that Pool re-evaluates and
 *  demonstrating that a presenter can type numbers until it agrees.
 */
function SupplierQuotes({ onRecorded }: { onRecorded: () => void }) {
  const [data, setData] = useState<SupplierUpdates | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.supplierUpdates().then(setData).catch(() => setData(null));
  };
  useEffect(load, []);

  if (!data) return null;

  const record = async (key: string) => {
    setBusy(key);
    setError(null);
    try {
      await api.recordSupplierQuote(key);
      load();
      onRecorded();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const units = (n: number) => (n === 1 ? data.unit : `${data.unit}s`);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Supplier updates</h2>
        <span className="spacer" />
        <span className="tiny faint">synthetic quotes, for demonstrating re-evaluation</span>
      </div>
      <div className="panel-pad stack-sm">
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="row-title">{data.product_name}</div>
            {/* Why recording a quote is an event rather than a button: the demand is
                already there, and has been since before anybody opened this screen. */}
            <p className="small muted" style={{ marginTop: 4 }}>
              <strong>{data.declared_members}</strong>{" "}
              {data.declared_members === 1 ? "member" : "members"} already declared this
              independently — {data.declared_units} {units(data.declared_units)} standing.
            </p>
          </div>
          <Chip tone={data.has_bulk_offer ? "ok" : "warn"}>
            {data.has_bulk_offer ? "bulk quote on file" : "no bulk quote"}
          </Chip>
        </div>

        <p className="tiny muted prose">
          Recording a quote writes one supplier offer and nothing else. No declaration,
          household, pool or past run record is touched — and no run happens. What moves
          is the deterministic outlook, because the world moved.
        </p>

        {error ? <p className="small" style={{ color: "var(--clay)" }}>{error}</p> : null}

        <div className="rows">
          {data.quotes.map((q) => (
            <div key={q.key} className="row">
              <div className="row-body">
                <div className="row-title">
                  {q.label}
                  {q.synthetic ? <Chip>synthetic</Chip> : null}
                  {q.recorded ? <Chip tone="ok">recorded</Chip> : null}
                </div>
                <div className="tiny muted">{q.summary}</div>
                <div className="tiny faint">
                  {money(q.unit_price_cents)} per {data.unit} · {q.case_units} to a case ·{" "}
                  minimum {q.min_units} {units(q.min_units)} ·{" "}
                  <span className="mono">{q.supplier_reference}</span>
                </div>
              </div>
              <div className="row-tail">
                <button
                  className="btn btn-sm"
                  disabled={busy !== null || q.recorded}
                  onClick={() => void record(q.key)}
                >
                  {busy === q.key ? "…" : q.recorded ? "On file" : "Record quote"}
                </button>
              </div>
            </div>
          ))}
        </div>

        <p className="tiny faint prose">
          These suppliers and terms are invented for this demo and are stored as
          synthetic, not as verified quotes — nobody negotiated them and no wholesaler
          relationship exists. Whether an order works is still the evaluator&apos;s
          answer, computed when somebody presses <strong>Run Pool now</strong>.
        </p>
      </div>
    </section>
  );
}

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
          <h2>The fulfilment job</h2>
        </div>
        <Empty>
          No job is open. A host checklist appears after the supplier order is recorded.
        </Empty>
      </section>
    );
  }

  const earnings = checklist.earnings as Record<string, string>;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>The fulfilment job — {checklist.product_name}</h2>
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
            label="Compensation earned"
            value={money(Number(earnings.paid_cents ?? 0))}
            sub="recorded in the simulated transaction; no payout rail exists"
          />
        </div>

        <div className="inset stack-sm">
          <p className="small">
            <strong>Confirm a handoff.</strong> Enter the buyer's one-time code; the server
            verifies it before marking the order collected.
          </p>
          <details>
            <summary className="tiny muted">
              Override boundary
            </summary>
            <p className="tiny muted" style={{ marginTop: 8 }}>
              The only other route is an audited operator override with a stated reason.
            </p>
          </details>
          <div className="btn-row">
            <input
              className="control"
              style={{ maxWidth: "13rem", fontFamily: "var(--mono)", letterSpacing: "0.06em" }}
              value={code}
              placeholder="e.g. 4KQ7WMTX"
              aria-label="One-time pickup code"
              onChange={(ev) => setCode(ev.target.value)}
            />
            <button
              className="btn btn-primary"
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
            <p className={`small${outcome.ok ? "" : " muted"}`} role="status">
              {outcome.message}
            </p>
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

  const loadLedger = () => {
    api.operator().then(setData).catch(() => setData(null));
  };
  useEffect(loadLedger, []);

  return (
    <div className="stack">
      <header className="stack-sm">
        <div>
          <button className="btn btn-sm btn-ghost" onClick={onBack}>
            <IconArrowLeft />
            Back
          </button>
        </div>
        <h1 className="title">Operations</h1>
        <p className="lede">
          Host fulfilment, supplier-quote freshness, and payment records with failure codes
          intact.
        </p>
      </header>

      {/* Before the ledger, because it is the thing an operator comes here to *do*
          rather than to read — and the offer table below is where its effect lands. */}
      <SupplierQuotes onRecorded={loadLedger} />

      <HostConsole poolId={hostPoolId} />

      {!data ? (
        <Empty>Loading the ledger…</Empty>
      ) : (
        <>
          <section className="panel">
            <div className="panel-head">
              <h2>Supplier offers</h2>
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
                <h2>{p.product_name}</h2>
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
                <h2>Open cases</h2>
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
                <h2>Runs that did not succeed</h2>
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
            <h2 className="section-title" style={{ marginBottom: 12 }}>
              Pool's own economics
            </h2>
            <p className="tiny muted" style={{ marginBottom: 12 }}>
              Stored-record figures. Payments are simulated; host compensation is earned
              and accounted for, never disbursed — no payout rail exists.
            </p>
            <div className="ledger">
              <LedgerLine
                label="Gross value coordinated"
                value={money(data.metrics.pool_spend_cents)}
              />
              {/* Earned, not paid. Host compensation is computed deterministically and is part
                    of what every buyer was charged — but Pool has no payout rail, so no money has
                    left anything. Calling this "paid out" described a system that does not exist. */}
              <LedgerLine
                label="Earned by hosts, for work done"
                value={money(data.metrics.host_earnings_cents)}
              />
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
            <details style={{ marginTop: 12 }}>
              <summary className="tiny muted">
                Platform viability rule
              </summary>
              <p className="tiny muted" style={{ marginTop: 8 }}>
                Pool's own economics must pass before lock; the engine refuses transactions
                that require a hidden platform subsidy.
              </p>
            </details>
          </section>
        </>
      )}
    </div>
  );
}
