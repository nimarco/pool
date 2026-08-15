import { useCallback, useEffect, useState } from "react";
import {
  AppState,
  Health,
  MapData,
  NeedRow,
  RunResult,
  ScenarioResult,
  api,
  resetWorkspaceId,
} from "./api";
import {
  AgentRuns,
  Dashboard,
  Impact,
  Landing,
  Needs,
  PoolDetail,
  ScenarioPanel,
} from "./views";

type View = "home" | "dashboard" | "needs" | "impact" | "agent" | "pool";

const NAV: { id: View; label: string }[] = [
  { id: "dashboard", label: "Neighbourhood" },
  { id: "needs", label: "Needs" },
  { id: "agent", label: "Agent activity" },
  { id: "impact", label: "Impact" },
];

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 28 28" aria-hidden="true">
      {/* Separate circles converging — the product in one glyph. */}
      <circle cx="9" cy="9" r="5" fill="none" stroke="var(--moss)" strokeWidth="1.6" />
      <circle cx="19" cy="9" r="5" fill="none" stroke="var(--moss)" strokeWidth="1.6" />
      <circle cx="14" cy="18" r="5" fill="var(--clay)" opacity="0.9" />
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState<View>("home");
  const [state, setState] = useState<AppState | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [needs, setNeeds] = useState<NeedRow[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [openPool, setOpenPool] = useState<string | null>(null);
  const [busyDecision, setBusyDecision] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [scenario, setScenario] = useState<ScenarioResult | null>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([api.state(), api.map()]);
      setState(s);
      setMap(m);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the Pool API");
    }
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (view === "needs" && needs.length === 0) {
      api.needs().then((r) => setNeeds(r.needs)).catch(() => undefined);
    }
  }, [view, needs.length]);

  const runAgent = async (trigger: string) => {
    setRunning(true);
    setLastRun(null);
    try {
      const result = await api.runAgent(trigger);
      setLastRun(result);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  };

  const respond = async (id: string, approve: boolean) => {
    setBusyDecision(id);
    try {
      await api.respond(id, approve);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record that answer");
    } finally {
      setBusyDecision(null);
    }
  };

  const withdraw = async (poolId: string, householdId: string) => {
    setRunning(true);
    try {
      await api.withdraw(poolId, householdId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Withdrawal failed");
    } finally {
      setRunning(false);
    }
  };

  const runScenario = async () => {
    setRunning(true);
    setScenario(null);
    try {
      setScenario(await api.scenario());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scenario failed");
    } finally {
      setRunning(false);
    }
  };

  const resetDemo = async () => {
    setRunning(true);
    try {
      await api.reset();
      setScenario(null);
      setLastRun(null);
      await refresh();
    } finally {
      setRunning(false);
    }
  };

  const newWorkspace = async () => {
    resetWorkspaceId();
    setScenario(null);
    setLastRun(null);
    await refresh();
  };

  const pool = state?.pools.find((p) => p.pool_id === openPool) ?? null;

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="topbar">
        <div className="topbar-inner">
          <button
            className="brand"
            onClick={() => setView("home")}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
          >
            <BrandMark />
            <span className="brand-name">Pool</span>
          </button>

          <nav className="nav" aria-label="Sections">
            {NAV.map((n) => (
              <button
                key={n.id}
                onClick={() => {
                  setView(n.id);
                  setOpenPool(null);
                }}
                aria-current={view === n.id || (n.id === "dashboard" && view === "pool") ? "page" : undefined}
              >
                {n.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="main" id="main">
        {error && (
          <div className="banner banner-warn" style={{ marginBottom: 18 }}>
            <div>
              <strong>{error}</strong>
              <div className="tiny">
                If you are running locally, make sure the API is up:{" "}
                <code className="mono">make api</code>
              </div>
            </div>
          </div>
        )}

        {view === "home" && (
          <Landing onStart={() => setView("dashboard")} health={health} />
        )}

        {view !== "home" && (
          <section className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h2>Pool is running in the background</h2>
              <span className="spacer" />
              <div className="btn-row">
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => runAgent("manual_demo")}
                  disabled={running}
                >
                  {running && <span className="spin" />}
                  Run a background scan
                </button>
                <button className="btn btn-sm" onClick={resetDemo} disabled={running}>
                  Reset demo
                </button>
                <button className="btn btn-sm" onClick={newWorkspace} disabled={running}>
                  New workspace
                </button>
              </div>
            </div>
            <div className="card-pad small muted">
              In production this runs on a schedule, event-driven and unattended. The button
              triggers the identical code path so you can watch it happen — there is no
              separate demo mode.
              {lastRun && (
                <div style={{ marginTop: 10 }}>
                  <span
                    className={`chip ${
                      lastRun.outcome === "loop_fault" || lastRun.outcome === "error"
                        ? "chip-warn"
                        : "chip-ok"
                    }`}
                  >
                    {lastRun.outcome.replace(/_/g, " ")}
                  </span>{" "}
                  <span className="mono tiny">
                    {lastRun.iterations} iterations · {lastRun.tool_calls.map((t) => t.name).join(" → ")}
                    {" · "}
                    {lastRun.duration_ms}ms
                  </span>
                </div>
              )}
            </div>
          </section>
        )}

        {view === "dashboard" && state && (
          <>
            <Dashboard
              state={state}
              map={map}
              onOpenPool={(id) => {
                setOpenPool(id);
                setView("pool");
              }}
              onRespond={respond}
              busyDecision={busyDecision}
            />
            <div style={{ marginTop: 18 }}>
              <ScenarioPanel onRun={runScenario} running={running} result={scenario} />
            </div>
          </>
        )}

        {view === "pool" && pool && (
          <PoolDetail
            pool={pool}
            onBack={() => {
              setOpenPool(null);
              setView("dashboard");
            }}
            onWithdraw={(hid) => withdraw(pool.pool_id, hid)}
            busy={running}
          />
        )}

        {view === "pool" && !pool && (
          <div className="card">
            <div className="empty">
              <strong>Pool not found</strong>
              <button className="btn btn-sm" onClick={() => setView("dashboard")}>
                Back to the neighbourhood
              </button>
            </div>
          </div>
        )}

        {view === "needs" && <Needs rows={needs} />}
        {view === "impact" && state && <Impact metrics={state.metrics} />}
        {view === "agent" && state && <AgentRuns runs={state.runs} health={health} />}

        {view !== "home" && !state && (
          <div className="card">
            <div className="empty">
              <strong>Loading the neighbourhood…</strong>
              <span className="small">Fetching state from the Pool API.</span>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>
            Pool — autonomous neighbourhood group-buying coordinator. Built for the AWS Agents
            for Humans hackathon.
          </span>
          <span>
            All data is synthetic. No payments are processed. Household locations are
            approximate by design.
          </span>
        </div>
      </footer>
    </div>
  );
}
