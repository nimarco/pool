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

import { useEffect, useState } from "react";
import { AppState, DemoConfig, Health, api } from "../api";
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
  identity,
  onIdentity,
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
  identity: Identity;
  onIdentity: (next: Identity) => void;
  onReset: () => void;
  onRefresh: () => Promise<void>;
  onAbout: () => void;
  onTechnical: () => void;
  onLifecycle: () => void;
  onOperations: () => void;
  onShowcase: () => void;
}) {
  const [people, setPeople] = useState<Identity[]>([]);
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

  // Escape closes it, because a drawer that traps you is worse than no drawer.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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
      <aside className="sheet" role="dialog" aria-label="Demo environment">
        <div className="sheet-head">
          <div>
            <h2 style={{ fontSize: 16 }}>Demo University</h2>
            <p className="tiny muted">A safe environment you cannot break.</p>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <IconCross />
          </button>
        </div>

        <div className="sheet-body">
          <section className="block" style={{ borderTop: "none", paddingTop: 0 }}>
            <h3 className="section-title" style={{ marginBottom: 10 }}>
              You are signed in as
            </h3>
            <select
              className="btn"
              style={{ width: "100%", justifyContent: "flex-start" }}
              value={identity.id}
              onChange={(ev) => {
                const next = people.find((p) => p.id === ev.target.value);
                if (next) onIdentity(next);
              }}
              aria-label="Signed in as"
            >
              {people.length === 0 ? (
                <option value={identity.id}>{identity.display_name}</option>
              ) : (
                people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))
              )}
            </select>
            <p className="tiny muted" style={{ marginTop: 8 }}>
              Everyone here is invented. Switching account changes whose needs, questions
              and pools you are looking at — it does not change any of the data.
            </p>
          </section>

          <section className="block">
            <h3 className="section-title" style={{ marginBottom: 6 }}>
              Demo controls
            </h3>
            <p className="tiny muted" style={{ marginBottom: 14 }}>
              Pool needs a community to work. These act on behalf of the other synthetic
              participants, using the same endpoints they would use themselves — so the
              state machine, the economics and every viability check still apply.
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
              <Chip tone="ok">real</Chip> The application, Strands loop, typed tools,
              timing and matching engines, exact-cent economics, viability checks,
              payment state machine, recovery workflow and one-time pickup credentials.
              State is stored and read back, not held in the page.
            </p>
            <p className="small muted" style={{ marginBottom: 12 }}>
              <Chip tone="warn">synthetic</Chip> The university, the people, the supplier
              catalogue and the prices in it. No wholesale relationship exists.
            </p>
            <p className="small muted">
              <Chip tone="warn">simulated</Chip> Money and the supplier order. No card is
              charged, no goods exist, and every purchase record is flagged as simulated
              wherever it appears.
            </p>
            {health ? (
              <p className="tiny mono muted" style={{ marginTop: 14 }}>
                store {health.repository} · lifecycle planner {health.model_provider} ·
                payments {health.payment_mode} · purchase{" "}
                {health.purchase_simulated ? "simulated" : health.purchase_executor} ·
                background schedules {health.schedules_enabled ? "on" : "off"}
              </p>
            ) : null}
          </section>

          <section className="block">
            <h3 className="section-title" style={{ marginBottom: 10 }}>
              For judges
            </h3>
            <p className="tiny muted" style={{ marginBottom: 12 }}>
              Everything technical hangs off the object it explains rather than off the
              navigation, so none of it is in a member's way. Here are the direct routes.
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
                  The guided tour: Overview, the thirteen-stage run, the deployed agent,
                  the community and the operations console, each as its own destination.
                  Same data and same code as the product — a different order, built for
                  being walked through rather than used.
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
                  The argument, the agent/deterministic boundary, and what the three marks
                  used throughout the product mean.
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
                  The exact stored run-to-pool relationship, tool sequence, bounds and
                  authoritative readback. A new AgentCore invocation is secondary.
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
                  All thirteen stages with the figures behind each: the timing split, the
                  host ranking, the exact price, the declined card, the repair, the lock
                  and the handover. Runs the whole lifecycle server-side first if this
                  session has not recorded one.
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
                  The fulfilment job as the host sees it, the supplier quotes a final price
                  may not rest on, and every authorisation and capture with its failure
                  code intact.
                </p>
              </div>
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
