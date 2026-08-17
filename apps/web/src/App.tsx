import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppState,
  DemoConfig,
  Health,
  LiveAgentResult,
  MapData,
  NeedRow,
  PoolView,
  RunResult,
  ScenarioResult,
  api,
  resetWorkspaceId,
} from "./api";
import {
  AgentRuns,
  Chip,
  Dashboard,
  HostConsole,
  Impact,
  Landing,
  LiveAgent,
  Needs,
  Operator,
  PoolDetail,
  ScenarioPanel,
} from "./views";

type View = "home" | "dashboard" | "needs" | "host" | "operator" | "agent" | "impact" | "pool";

const NAV: { id: View; label: string }[] = [
  { id: "dashboard", label: "Community" },
  { id: "needs", label: "Needs" },
  { id: "host", label: "Host" },
  { id: "operator", label: "Operator" },
  { id: "agent", label: "Agent" },
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
  const [openPool, setOpenPool] = useState<PoolView | null>(null);
  const [busyDecision, setBusyDecision] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [scenario, setScenario] = useState<ScenarioResult | null>(null);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [live, setLive] = useState<LiveAgentResult | null>(null);
  const [liveBusy, setLiveBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([api.state(), api.map()]);
      setState(s);
      setMap(m);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    // One load on mount. Nothing here polls: a browser tab that quietly re-triggers
    // work is exactly the kind of background cost AGENTS.md §3.2 forbids.
    void refresh();
    api.health().then(setHealth).catch(() => setHealth(null));
    api.needs().then(setNeeds).catch(() => setNeeds([]));
    // Only the deployed demo answers this. A 404 locally is the expected answer, and
    // it hides the live panel rather than offering a button that cannot work.
    api.demoConfig().then(setDemoConfig).catch(() => setDemoConfig(null));
  }, [refresh]);

  const openPoolDetail = useCallback(
    async (poolId: string) => {
      try {
        setOpenPool(await api.pool(poolId));
        setView("pool");
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        // A pool the client knows about but the server does not means this tab is
        // holding a stale list — after a demo reset, say. Re-reading is the right
        // recovery; an alarming error banner is not.
        if (message.includes("not found")) {
          setOpenPool(null);
          setView("dashboard");
          await refresh();
          return;
        }
        setError(message);
      }
    },
    [refresh],
  );

  const runAgent = useCallback(
    async (trigger: "manual_scan" | "manual_advance") => {
      setRunning(true);
      try {
        setLastRun(await api.run(trigger));
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setRunning(false);
      }
    },
    [refresh],
  );

  /** The one action that leaves this machine. It does not touch the state below —
   *  the deployed runtime seeds its own community inside its own session. */
  const runLiveAgent = useCallback(async () => {
    setLiveBusy(true);
    try {
      setLive(await api.liveAgent());
    } catch (err) {
      setLive({ ok: false, live: false, reason: err instanceof Error ? err.message : String(err) });
    } finally {
      setLiveBusy(false);
    }
  }, []);

  const runScenario = useCallback(async () => {
    setRunning(true);
    try {
      const result = await api.scenario();
      setScenario(result);
      await refresh();
      setView("dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [refresh]);

  const respond = useCallback(
    async (decisionId: string, approve: boolean) => {
      setBusyDecision(decisionId);
      try {
        await api.respond(decisionId, approve);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusyDecision(null);
      }
    },
    [refresh],
  );

  const reset = useCallback(async () => {
    setRunning(true);
    try {
      await api.reset();
      setScenario(null);
      setLastRun(null);
      setOpenPool(null);
      await refresh();
      setNeeds(await api.needs());
      setView("dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [refresh]);

  /** The host console shows whichever pool currently has a fulfilment job. */
  const hostPoolId = useMemo(() => {
    const pools = state?.pools ?? [];
    const active = pools.find(
      (p) => p.status === "distributing" || p.status === "completed" || p.status === "purchased",
    );
    return active?.pool_id ?? null;
  }, [state]);

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" onClick={() => setView("home")}>
            <BrandMark />
            <span className="brand-name">Pool</span>
          </button>
          <nav className="nav">
            {NAV.map((item) => (
              <button
                key={item.id}
                className={view === item.id ? "active" : ""}
                onClick={() => setView(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="btn-row">
            <button
              className="btn btn-sm"
              onClick={() => runAgent("manual_scan")}
              disabled={running}
            >
              {running ? "Working…" : "Run a scan"}
            </button>
            <button
              className="btn btn-sm"
              onClick={() => runAgent("manual_advance")}
              disabled={running}
            >
              Advance pools
            </button>
            <button className="btn btn-sm" onClick={reset} disabled={running}>
              Reset
            </button>
          </div>
        </div>
      </header>

      <main className="main" id="main">
        {error ? (
          <div className="banner banner-warn">
            {error}{" "}
            <button
              className="btn btn-sm"
              onClick={() => {
                resetWorkspaceId();
                window.location.reload();
              }}
            >
              Start a fresh workspace
            </button>
          </div>
        ) : null}

        {state?.is_demo_data ? (
          <div className="banner">
            Synthetic demo data. Payments are {health?.payment_mode ?? "simulated"}; the
            supplier purchase is simulated; no goods move.
          </div>
        ) : null}

        {lastRun && view !== "home" ? (
          <div className="card card-pad">
            <div className="card-head">
              <h3>
                Last run <Chip tone="info">{lastRun.outcome}</Chip>
              </h3>
              <button className="btn btn-sm" onClick={() => setLastRun(null)}>
                Dismiss
              </button>
            </div>
            <p className="tiny mono muted">
              {lastRun.tool_calls.map((t) => t.name).join(" → ") || "no tools called"} ·{" "}
              {lastRun.iterations} iterations · {lastRun.termination_reason} ·{" "}
              {lastRun.input_tokens ?? 0}/{lastRun.output_tokens ?? 0} tokens
            </p>
            {lastRun.notes.length > 0 ? (
              <p className="small muted">{lastRun.notes.join(" · ")}</p>
            ) : null}
          </div>
        ) : null}

        {scenario ? (
          <ScenarioPanel scenario={scenario} onClose={() => setScenario(null)} />
        ) : null}

        {view === "home" ? (
          <Landing
            onEnter={() => setView("dashboard")}
            onScenario={runScenario}
            onSeeAgent={() => setView("agent")}
            running={running}
            health={health}
            demoConfig={demoConfig}
            memberCount={state?.counts.members ?? null}
          />
        ) : null}

        {view === "dashboard" && state ? (
          <Dashboard
            state={state}
            map={map}
            onOpenPool={openPoolDetail}
            onRespond={respond}
            busyDecision={busyDecision}
          />
        ) : null}

        {view === "needs" ? <Needs needs={needs} /> : null}

        {view === "host" ? <HostConsole poolId={hostPoolId} /> : null}

        {view === "operator" ? <Operator /> : null}

        {view === "agent" && state ? (
          <AgentRuns
            runs={state.runs}
            activity={state.activity}
            live={
              demoConfig ? (
                <LiveAgent
                  config={demoConfig}
                  result={live}
                  busy={liveBusy}
                  onRun={runLiveAgent}
                />
              ) : null
            }
          />
        ) : null}

        {view === "impact" && state ? <Impact state={state} /> : null}

        {view === "pool" && openPool ? (
          <PoolDetail
            pool={openPool}
            onBack={() => setView("dashboard")}
            onRefresh={() => void openPoolDetail(openPool.pool_id)}
          />
        ) : null}

        {!state && view !== "home" ? <p className="empty">Loading…</p> : null}
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span className="tiny muted">
            Pool — an autonomous collective-purchasing coordinator. Synthetic data
            throughout; no real money, no real supplier, no real institution.
          </span>
          {health ? (
            <span className="tiny mono muted">
              {health.repository} · {health.routing_provider} · {health.model_provider} ·{" "}
              {health.payment_mode}
            </span>
          ) : null}
        </div>
      </footer>
    </div>
  );
}
