/* The demo operator's drawer.
 *
 * Pool is a three-sided product: buyers, a host, and an operator. One judge cannot be
 * ten synthetic people at once, so this is where they act on everyone else's behalf.
 *
 * Two rules keep it honest:
 *
 *   - **No control sets state directly.** Every button calls the same endpoint the real
 *     participant would call, and the domain validates it exactly as it would for them.
 *     There is no "mark this pool purchased" here, because there is no such operation in
 *     Pool.
 *   - **A control that cannot legally run is not offered.** Availability is derived from
 *     the pool's own status and the decisions actually outstanding, so the drawer never
 *     invites an action the state machine would refuse.
 *
 * It lives behind a menu on purpose. It is scaffolding for a single-player demo of a
 * multi-player product, and it should never look like part of the product.
 */

import { useEffect, useRef, useState } from "react";
import { AppState, Consumer, DemoConfig, Health, api } from "../api";
import { Chip, IconCheck, IconCross, IconReplay } from "../ui";

export interface Identity {
  id: string;
  display_name: string;
}

interface Control {
  id: string;
  label: string;
  hint: string;
  available: boolean;
  unavailable?: string;
  run: () => Promise<string>;
}

/** What can legally happen next, given what the server currently says. */
function buildControls(state: AppState): Control[] {
  const pool = state.pools[0] ?? null;
  const hostOffer = state.decisions.find((d) => d.kind === "host_offer");
  const buyerQuestions = state.decisions.filter((d) => d.kind !== "host_offer");
  const status = pool?.status ?? null;

  const controls: Control[] = [
    {
      id: "host",
      label: hostOffer
        ? `${hostOffer.household_name} accepts the fulfilment job`
        : "The host accepts the job",
      hint: "Answers the offer Pool made to the best-ranked eligible candidate.",
      available: Boolean(hostOffer),
      unavailable: "No fulfilment offer is outstanding.",
      run: async () => {
        await api.respond(hostOffer!.decision_id, true);
        return `${hostOffer!.household_name} accepted.`;
      },
    },
    {
      id: "buyers",
      label:
        buyerQuestions.length > 0
          ? `${buyerQuestions.length} buyer${buyerQuestions.length === 1 ? "" : "s"} answer their question`
          : "Buyers answer their questions",
      hint: "Approves every price Pool had to ask a person about.",
      available: buyerQuestions.length > 0,
      unavailable: "Nobody is waiting to be asked.",
      run: async () => {
        for (const d of buyerQuestions) await api.respond(d.decision_id, true);
        return `${buyerQuestions.length} answered.`;
      },
    },
    {
      id: "advance",
      label: "Let Pool work the queue",
      hint: "One coordination run: price it, repair a shortfall, lock it, order it.",
      available: Boolean(pool) && status !== "completed",
      unavailable: pool ? "This pool is finished." : "There is no pool yet.",
      run: async () => {
        const run = await api.run("manual_advance");
        return `${run.outcome.replace(/_/g, " ")} · ${run.tool_calls.length} tools called.`;
      },
    },
    {
      id: "distribute",
      label: "Open the pickup window",
      hint: "What the scheduler does when the collection slot arrives.",
      available: status === "purchased",
      unavailable:
        status === "distributing" || status === "completed"
          ? "Already open."
          : "The order has not been placed yet.",
      run: async () => {
        await api.openDistribution(pool!.pool_id);
        return "Pickup is open, and every buyer has a credential waiting.";
      },
    },
    {
      id: "handout",
      label: "Everyone collects their order",
      hint: "Issues each buyer's one-time code and redeems it, exactly as a host would.",
      available: status === "distributing",
      unavailable:
        status === "completed" ? "Every order is collected." : "Pickup is not open yet.",
      run: async () => {
        const checklist = await api.checklist(pool!.pool_id);
        let done = 0;
        for (const order of checklist.orders) {
          if (order.state === "picked_up") continue;
          const credential = await api.issueCredential(pool!.pool_id, order.household_id);
          const outcome = await api.redeem(pool!.pool_id, credential.token, false);
          if (outcome.ok) done += 1;
        }
        return `${done} handoff${done === 1 ? "" : "s"} confirmed against a one-time code.`;
      },
    },
  ];
  return controls;
}

/* ---------------------------------------------------------------------- panel */

export function DemoPanel({
  open,
  onClose,
  state,
  health,
  demoConfig,
  consumer,
  actingAs,
  onActAs,
  onReset,
  onRefresh,
  onAbout,
  onTechnical,
  onLifecycle,
  onOperations,
  onShowcase,
}: {
  open: boolean;
  onClose: () => void;
  state: AppState | null;
  health: Health | null;
  demoConfig: DemoConfig | null;
  consumer: Consumer | null;
  /** Non-null only while the operator has stepped into a synthetic participant. */
  actingAs: Identity | null;
  onActAs: (next: Identity | null) => void;
  onReset: () => void;
  onRefresh: () => Promise<void>;
  onAbout: () => void;
  onTechnical: () => void;
  onLifecycle: () => void;
  onOperations: () => void;
  onShowcase: () => void;
}) {
  const [people, setPeople] = useState<Identity[]>([]);
  const sheet = useRef<HTMLElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{ id: string; text: string; ok: boolean } | null>(
    null,
  );

  useEffect(() => {
    if (!open || people.length > 0) return;
    api
      .needs()
      .then((view) => {
        const seen = new Map<string, string>();
        for (const row of view.needs) seen.set(row.household_id, row.household_name);
        setPeople(
          [...seen.entries()]
            .map(([id, display_name]) => ({ id, display_name }))
            .sort((a, b) => a.display_name.localeCompare(b.display_name)),
        );
      })
      .catch(() => setPeople([]));
  }, [open, people.length]);

  // Escape closes it, because a drawer that traps you is worse than no drawer. Tab is
  // held inside while it is open — a keyboard visitor tabbing out of a modal drawer and
  // landing silently on the page behind it is the same bug in a quieter form. Focus goes
  // in on open and returns to whatever opened it on close.
  useEffect(() => {
    if (!open) return undefined;
    opener.current = document.activeElement as HTMLElement | null;
    sheet.current?.focus();
    const focusable = () =>
      [
        ...(sheet.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
        ) ?? []),
      ].filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        onClose();
        return;
      }
      if (ev.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (!ev.shiftKey && active === last) {
        ev.preventDefault();
        first.focus();
      } else if (ev.shiftKey && (active === first || active === sheet.current)) {
        ev.preventDefault();
        last.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      opener.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  const controls = state ? buildControls(state) : [];

  const perform = async (control: Control) => {
    setBusy(control.id);
    setOutcome(null);
    try {
      const text = await control.run();
      await onRefresh();
      setOutcome({ id: control.id, text, ok: true });
    } catch (err) {
      setOutcome({
        id: control.id,
        text: err instanceof Error ? err.message : String(err),
        ok: false,
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <div className="sheet-scrim" onClick={onClose} aria-hidden="true" />
      <aside
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-sheet-title"
        tabIndex={-1}
        ref={sheet}
      >
        <div className="sheet-head">
          <div>
            <h2 id="demo-sheet-title" style={{ fontSize: 16 }}>
              Demo University
            </h2>
            <p className="tiny muted">A safe environment you cannot break.</p>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <IconCross />
          </button>
        </div>

        <div className="sheet-body">
          {/* Operator tooling, and framed as such.
              This used to be headed "You are signed in as", which made a roster of
              invented students look like the account model — the first thing a visitor
              met was a question about which fictional person to be. Pool is a
              multi-person product being demonstrated by one person, so the capability
              has to stay; what changed is that stepping into somebody else is now an
              explicit, visibly-temporary act rather than the default state. */}
          <section className="block" style={{ borderTop: "none", paddingTop: 0 }}>
            <h3 className="section-title" style={{ marginBottom: 10 }}>
              Act as a synthetic participant
            </h3>
            <select
              className="btn"
              style={{ width: "100%", justifyContent: "flex-start" }}
              value={actingAs?.id ?? ""}
              onChange={(ev) => {
                if (!ev.target.value) {
                  onActAs(null);
                  return;
                }
                const next = people.find((p) => p.id === ev.target.value);
                if (next) onActAs(next);
              }}
              aria-label="Act as a synthetic participant"
            >
              <option value="">
                {consumer?.display_name ? `You — ${consumer.display_name}` : "You"}
              </option>
              {people
                .filter((p) => p.id !== consumer?.household_id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
            </select>
            {actingAs ? (
              <p className="tiny" style={{ marginTop: 8, color: "var(--clay)" }}>
                <strong>You are acting as {actingAs.display_name}.</strong> Their screens,
                their decisions — not yours. Choose <em>You</em> to come back.
              </p>
            ) : (
              <p className="tiny muted" style={{ marginTop: 8 }}>
                Pool is a product for many people and this demo has one. Everyone here is
                invented; acting as them answers the questions they would answer, through
                their own endpoints. It changes the viewpoint, not the data.
              </p>
            )}
          </section>

          <section className="block">
            <h3 className="section-title" style={{ marginBottom: 6 }}>
              Demo controls
            </h3>
            <p className="tiny muted" style={{ marginBottom: 14 }}>
              These act for other synthetic participants through their normal endpoints;
              state, economics and viability rules still apply.
            </p>
            <div className="stack-sm">
              {controls.map((control) => (
                <div key={control.id}>
                  <button
                    className="btn"
                    style={{ width: "100%", justifyContent: "flex-start", textAlign: "left" }}
                    disabled={!control.available || busy !== null}
                    onClick={() => void perform(control)}
                  >
                    {busy === control.id ? <span className="spinner" /> : null}
                    {control.label}
                  </button>
                  <p className="tiny faint" style={{ marginTop: 4 }}>
                    {control.available ? control.hint : control.unavailable}
                  </p>
                  {outcome && outcome.id === control.id ? (
                    <p
                      className="tiny"
                      role="status"
                      style={{
                        marginTop: 4,
                        color: outcome.ok ? "var(--moss)" : "var(--clay)",
                      }}
                    >
                      {outcome.ok ? <IconCheck size={12} /> : <IconCross size={12} />}{" "}
                      {outcome.text}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="btn-row" style={{ marginTop: 16 }}>
              <button className="btn btn-sm" onClick={onReset}>
                <IconReplay />
                Reset Demo University
              </button>
            </div>
          </section>

          <section className="block">
            <h3 className="section-title" style={{ marginBottom: 10 }}>
              What is real here
            </h3>
            <div className="facts" style={{ marginBottom: 14 }}>
              <div>
                <div className="fact-label">Discovery</div>
                <div className="fact-value">
                  {demoConfig?.live_agent_available
                    ? `AgentCore / Bedrock available · ${demoConfig.region}`
                    : "local bounded coordinator"}
                </div>
              </div>
              <div>
                <div className="fact-label">Lifecycle</div>
                <div className="fact-value">deterministic planner</div>
              </div>
              <div>
                <div className="fact-label">Payments / supplier order</div>
                <div className="fact-value">simulated</div>
              </div>
            </div>
            <p className="small muted" style={{ marginBottom: 12 }}>
              <Chip tone="ok">real</Chip> App, Strands loop, typed tools, deterministic
              matching/economics/viability, recovery and pickup credentials. State is stored
              and read back.
            </p>
            <p className="small muted" style={{ marginBottom: 12 }}>
              <Chip tone="warn">synthetic</Chip> University, people, supplier catalogue and
              prices; no wholesale relationship exists.
            </p>
            <p className="small muted">
              <Chip tone="warn">simulated</Chip> Payments and supplier order; no card is
              charged, no goods exist, and purchase records are labelled simulated.
            </p>
            {health ? (
              <details className="inset" style={{ marginTop: 14 }}>
                <summary className="tiny muted">
                  Environment detail
                </summary>
                <p className="tiny mono muted" style={{ marginTop: 8 }}>
                  store {health.repository} · lifecycle planner {health.model_provider} ·
                  payments {health.payment_mode} · purchase{" "}
                  {health.purchase_simulated ? "simulated" : health.purchase_executor} ·
                  background schedules {health.schedules_enabled ? "on" : "off"}
                </p>
              </details>
            ) : null}
          </section>

          <section className="block">
            <h3 className="section-title" style={{ marginBottom: 10 }}>
              For judges
            </h3>
            <p className="tiny muted" style={{ marginBottom: 12 }}>
              Direct judge routes; Product mode remains the normal member experience.
            </p>
            <div className="stack-sm">
              <div>
                <button
                  className="btn btn-primary"
                  style={{ width: "100%", justifyContent: "flex-start" }}
                  onClick={onShowcase}
                >
                  Open Showcase mode
                </button>
                <p className="tiny faint" style={{ marginTop: 4 }}>
                  Same data and code, reordered into a guided judge walkthrough.
                </p>
              </div>
              <div>
                <button
                  className="btn"
                  style={{ width: "100%", justifyContent: "flex-start" }}
                  onClick={onAbout}
                >
                  What Pool is
                </button>
                <p className="tiny faint" style={{ marginTop: 4 }}>
                  Product thesis, actor key, and model/deterministic boundary.
                </p>
              </div>
              <div>
                <button
                  className="btn"
                  style={{ width: "100%", justifyContent: "flex-start" }}
                  onClick={onTechnical}
                >
                  Technical proof
                </button>
                <p className="tiny faint" style={{ marginTop: 4 }}>
                  Same-run link, exact tools, bounds and authoritative readback.
                </p>
              </div>
              <div>
                <button
                  className="btn"
                  style={{ width: "100%", justifyContent: "flex-start" }}
                  onClick={onLifecycle}
                >
                  How a pool happens, stage by stage
                </button>
                <p className="tiny faint" style={{ marginTop: 4 }}>
                  All 13 stages and figures; runs the server lifecycle first if needed.
                </p>
              </div>
              <div>
                <button
                  className="btn"
                  style={{ width: "100%", justifyContent: "flex-start" }}
                  onClick={onOperations}
                >
                  Operations console
                </button>
                <p className="tiny faint" style={{ marginTop: 4 }}>
                  Host job, quote freshness, authorizations, captures and failure codes.
                </p>
              </div>
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
