import { useCallback, useEffect, useState } from "react";
import {
  AppState,
  DemoConfig,
  Health,
  LiveAgentResult,
  MapData,
  PoolView,
  ScenarioResult,
  api,
  resetWorkspaceId,
} from "./api";
import { BrandMark } from "./brand";
import { IconArrowLeft, IconCross } from "./ui";
import { About } from "./views/about";
import { CommunityView } from "./views/community";
import { DemoPanel, Identity } from "./views/demo-panel";
import { Home } from "./views/home";
import { Needs } from "./views/needs";
import { OperationsView } from "./views/operations";
import { PoolRecord } from "./views/pool";
import { Pools } from "./views/pools";
import { AgentExecution } from "./views/live";
import { RunView } from "./views/run";

type View = "home" | "pools" | "needs" | "community" | "pool" | "operations" | "about";

/** Showcase mode: the guided judge experience, kept alongside the product rather than
 *  instead of it. Same components, same state, same API — a different order and a
 *  different set of front doors. Useful for the submission video, for screenshots, and
 *  for anybody who would rather be walked through Pool than use it. */
type ShowcaseView = "overview" | "run" | "live" | "community" | "operations" | "pool";

const SHOWCASE_NAV: { id: ShowcaseView; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "run", label: "The run" },
  { id: "live", label: "Live on AWS" },
  { id: "community", label: "Community" },
  { id: "operations", label: "Operations" },
];

/** Four destinations, all of them things a member of the community actually has: their
 *  own front page, the orders they are part of, what they buy, and the place they live.
 *  Everything a judge needs in order to audit the agent hangs off a pool record, and
 *  everything needed to drive a multi-person demo alone lives in the drawer. */
const NAV: { id: View; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "pools", label: "Pools" },
  { id: "needs", label: "Needs" },
  { id: "community", label: "Community" },
];

/** Who the visitor is signed in as by default. Rosa is a member with two standing needs
 *  who joins the whey pool and — because one of her own rules does not clear — is one of
 *  the people Pool has to *ask* rather than decide for. That makes the first thing a
 *  judge sees a real question addressed to them, which is the product working. */
const DEFAULT_IDENTITY: Identity = { id: "hh_navarro", display_name: "Rosa N." };

export default function App() {
  const [view, setView] = useState<View>("home");
  const [state, setState] = useState<AppState | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [openPool, setOpenPool] = useState<PoolView | null>(null);
  const [busyDecision, setBusyDecision] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [scenario, setScenario] = useState<ScenarioResult | null>(null);
  const [scenarioMs, setScenarioMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [demoConfig, setDemoConfig] = useState<DemoConfig | null>(null);
  const [live, setLive] = useState<LiveAgentResult | null>(null);
  const [liveBusy, setLiveBusy] = useState(false);
  const [identity, setIdentity] = useState<Identity>(DEFAULT_IDENTITY);
  const [panelOpen, setPanelOpen] = useState(false);
  /** Which tab (and which deep view within Activity) a pool record should open on, so
   *  "see it run on AWS" can land on the evidence rather than on the front page of a
   *  record the visitor then has to navigate. */
  const [poolEntry, setPoolEntry] = useState<{ tab?: string; deep?: string }>({});
  const [showcase, setShowcase] = useState<ShowcaseView | null>(null);

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
    api.demoConfig().then(setDemoConfig).catch(() => setDemoConfig(null));
  }, [refresh]);

  useEffect(() => {
    const label = NAV.find((item) => item.id === view)?.label;
    document.title = label && view !== "home" ? `${label} — Pool` : "Pool";
  }, [view]);

  const navigate = useCallback((next: View) => {
    setShowcase(null);
    setView(next);
    setPanelOpen(false);
    window.scrollTo({ top: 0 });
  }, []);

  const showcaseTo = useCallback((next: ShowcaseView) => {
    setShowcase(next);
    setPanelOpen(false);
    window.scrollTo({ top: 0 });
  }, []);

  /** Re-reads the pool currently open, so an action taken in the drawer is visible on
   *  the record behind it without a manual refresh. */
  const refreshAll = useCallback(async () => {
    await refresh();
    if (openPool) {
      try {
        setOpenPool(await api.pool(openPool.pool_id));
      } catch {
        setOpenPool(null);
      }
    }
  }, [refresh, openPool]);

  const openPoolDetail = useCallback(
    async (poolId: string, entry: { tab?: string; deep?: string } = {}) => {
      try {
        setPoolEntry(entry);
        setOpenPool(await api.pool(poolId));
        if (showcase) setShowcase("pool");
        else setView("pool");
        setPanelOpen(false);
        setError(null);
        window.scrollTo({ top: 0 });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        // A pool this tab knows about but the server does not means the list is stale —
        // after a reset, say. Re-reading is the right recovery; an error banner is not.
        if (message.includes("not found")) {
          setOpenPool(null);
          setView("pools");
          await refresh();
          return;
        }
        setError(message);
      }
    },
    [refresh, showcase],
  );

  /** Invoke the coordinator deployed on Bedrock AgentCore, bound to this session.
   *
   *  Nothing here reads the run's answer to decide what happened. The result is kept as
   *  evidence — which tools it chose, what it cost, how long it took — and the state the
   *  page then renders comes from re-reading the server. That is the difference between
   *  the agent having done the work and the browser drawing what the agent said.
   *
   *  The server classifies the outcome. The caller may fall back only when the server
   *  explicitly proves that no remote execution can still mutate this workspace. */
  const invokeDeployedAgent = useCallback(async (): Promise<LiveAgentResult | null> => {
    setLiveBusy(true);
    setLive(null);
    try {
      const result = await api.liveAgent();
      setLive(result);
      // A failure is not proof that nothing changed: the invocation can time out after
      // the agent has written to the shared workspace. The server says when to re-read.
      if (result.refresh_state) await refresh();
      return result;
    } catch {
      // No response means the browser cannot establish whether the request reached AWS.
      // Treat it conservatively as ambiguous; never parse an exception string to decide
      // whether a local mutating fallback is safe.
      const failure: LiveAgentResult = {
        ok: false,
        live: false,
        classification: "ambiguous_remote_execution",
        remote_may_still_write: true,
        allow_local_fallback: false,
        refresh_state: true,
        reason:
          "The live request did not complete. The deployed run may still be finishing; " +
          "this session remains protected until it is safe to retry.",
      };
      setLive(failure);
      await refresh();
      return failure;
    } finally {
      setLiveBusy(false);
    }
  }, [refresh]);

  /** The product action. Pool's coordinator looks across the community's standing needs
   *  and forms an opportunity if one is genuinely worth forming.
   *
   *  Where it runs depends on the deployment, and the answer is never hidden. On the
   *  public demo it is the coordinator deployed on Bedrock AgentCore, working on this
   *  session's own DynamoDB workspace — so the pool that appears was formed by that run.
   *  Locally, or when the server explicitly confirms that no remote execution can still
   *  mutate the workspace, the same coordinator runs on this server with a deterministic
   *  planner in the model's place.
   *  Both are the real Strands loop and the real typed tools; `model_provider` on the
   *  run record says which one answered, and the technical view shows it. */
  const findOpportunities = useCallback(async () => {
    setRunning(true);
    try {
      if (demoConfig?.live_agent_available) {
        const liveResult = await invokeDeployedAgent();
        if (liveResult?.ok) {
          setView("home");
          window.scrollTo({ top: 0 });
          return;
        }
        if (!liveResult?.allow_local_fallback) {
          if (liveResult) setError(liveResult.reason);
          return;
        }
      }
      await api.run("manual_scan");
      await refresh();
      setView("home");
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [refresh, demoConfig, invokeDeployedAgent]);

  /** The same invocation, reached from the technical view rather than from the product.
   *  One code path, so what a judge audits there is what the product actually did. */
  const runLiveAgent = useCallback(async () => {
    await invokeDeployedAgent();
  }, [invokeDeployedAgent]);

  const runScenario = useCallback(async () => {
    setRunning(true);
    setPanelOpen(false);
    try {
      const started = performance.now();
      const result = await api.scenario();
      setScenarioMs(Math.round(performance.now() - started));
      setScenario(result);
      const fresh = await api.state();
      setState(fresh);
      setMap(await api.map());
      if (result.pool_id) {
        setOpenPool(await api.pool(result.pool_id));
        if (showcase) {
          // Showcase already has a dedicated reader, so land there.
          setShowcase("run");
        } else {
          // In the product the lifecycle exists to be *read*, so open the record on the
          // reader rather than on its front page.
          setPoolEntry({ tab: "activity", deep: "walkthrough" });
          setView("pool");
        }
      }
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [showcase]);

  const respond = useCallback(
    async (decisionId: string, approve: boolean) => {
      setBusyDecision(decisionId);
      try {
        await api.respond(decisionId, approve);
        await refreshAll();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusyDecision(null);
      }
    },
    [refreshAll],
  );

  const reset = useCallback(async () => {
    setRunning(true);
    try {
      await api.reset();
      setScenario(null);
      setScenarioMs(null);
      setOpenPool(null);
      setLive(null);
      await refresh();
      setView("home");
      setPanelOpen(false);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [refresh]);

  const communityName = state?.community?.name ?? "Demo University";

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="topbar">
        <div className="wrap topbar-inner">
          <button className="brand" onClick={() => navigate("home")} aria-label="Pool, home">
            <BrandMark />
            <span className="brand-name">Pool</span>
          </button>

          {showcase ? (
            <nav className="nav" aria-label="Showcase sections">
              {SHOWCASE_NAV.map((item) => (
                <button
                  key={item.id}
                  aria-current={
                    showcase === item.id || (showcase === "pool" && item.id === "community")
                      ? "page"
                      : undefined
                  }
                  onClick={() => showcaseTo(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          ) : (
            <nav className="nav" aria-label="Sections">
              {NAV.map((item) => (
                <button
                  key={item.id}
                  aria-current={
                    view === item.id || (view === "pool" && item.id === "pools")
                      ? "page"
                      : undefined
                  }
                  onClick={() => navigate(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          )}

          <div className="topbar-tail">
            {showcase ? (
              <button className="btn btn-sm btn-ghost" onClick={() => navigate("home")}>
                <IconArrowLeft />
                Leave showcase
              </button>
            ) : null}
            <button
              className="btn btn-sm"
              onClick={() => setPanelOpen(true)}
              aria-haspopup="dialog"
              title="Demo environment, controls, and what is real here"
            >
              <span className="env-dot" aria-hidden="true" />
              {communityName}
            </button>
          </div>
        </div>
      </header>

      <main className="main wrap" id="main">
        <div className="stack">
          {error ? (
            <div className="banner banner-stop">
              <span>{error}</span>
              <button
                className="btn btn-sm"
                onClick={() => {
                  resetWorkspaceId();
                  window.location.reload();
                }}
              >
                Start a fresh session
              </button>
            </div>
          ) : null}

          {showcase === "overview" ? (
            <About
              health={health}
              demoConfig={demoConfig}
              memberCount={state?.counts.members ?? null}
              needCount={state?.counts.needs ?? null}
              onOpenTechnical={() => showcaseTo("live")}
              onRun={runScenario}
              running={running}
            />
          ) : null}

          {showcase === "run" ? (
            <RunView
              scenario={scenario}
              roundTripMs={scenarioMs}
              running={running}
              onRun={runScenario}
              onOpenPool={openPoolDetail}
              onLive={() => showcaseTo("live")}
            />
          ) : null}

          {showcase === "live" ? (
            <AgentExecution
              config={demoConfig}
              health={health}
              result={live}
              busy={liveBusy}
              onRun={runLiveAgent}
              runs={state?.runs ?? []}
              proof={
                state?.pools.find((pool) => pool.execution_proof)?.execution_proof ?? null
              }
              standalone
            />
          ) : null}

          {showcase === "community" && state ? (
            <CommunityView
              state={state}
              map={map}
              onOpenPool={openPoolDetail}
              onRespond={respond}
              busyDecision={busyDecision}
              onOperations={() => showcaseTo("operations")}
            />
          ) : null}

          {showcase === "operations" ? (
            <OperationsView
              hostPoolId={
                state?.pools.find(
                  (p) =>
                    p.status === "distributing" ||
                    p.status === "completed" ||
                    p.status === "purchased",
                )?.pool_id ?? null
              }
              onBack={() => showcaseTo("community")}
            />
          ) : null}

          {showcase === "pool" && openPool ? (
            <PoolRecord
              pool={openPool}
              runs={state?.runs ?? []}
              activity={(state?.activity ?? []).filter(
                (e) => e.pool_id === null || e.pool_id === openPool.pool_id,
              )}
              identity={identity}
              entry={poolEntry}
              scenario={scenario}
              scenarioMs={scenarioMs}
              running={running}
              health={health}
              demoConfig={demoConfig}
              live={live}
              liveBusy={liveBusy}
              onBack={() => showcaseTo("community")}
              onRefresh={() => void openPoolDetail(openPool.pool_id)}
              onRunLive={runLiveAgent}
              onRunScenario={runScenario}
            />
          ) : null}

          {showcase && !state && showcase !== "operations" ? (
            <p className="empty">Loading…</p>
          ) : null}

          {!showcase && view === "home" && state ? (
            <Home
              state={state}
              identity={identity}
              running={running}
              busyDecision={busyDecision}
              onFind={findOpportunities}
              onOpenPool={openPoolDetail}
              onRespond={respond}
              /* The card names the pool it drew; the proof opens for that exact pool
                 rather than for whichever one happens to sort first. */
              onShowAgent={(poolId) =>
                void openPoolDetail(poolId, { tab: "activity", deep: "execution" })
              }
              onGoNeeds={() => navigate("needs")}
              onGoCommunity={() => navigate("community")}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && view === "pools" && state ? (
            <Pools
              state={state}
              onOpen={openPoolDetail}
              onFind={findOpportunities}
              running={running}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && view === "needs" ? (
            <Needs
              identity={identity}
              communityName={communityName}
              onFind={findOpportunities}
              running={running}
              hasPool={(state?.pools.length ?? 0) > 0}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && view === "community" && state ? (
            <CommunityView
              state={state}
              map={map}
              onOpenPool={openPoolDetail}
              onRespond={respond}
              busyDecision={busyDecision}
              onOperations={() => navigate("operations")}
            />
          ) : null}

          {!showcase && view === "operations" ? (
            <OperationsView
              hostPoolId={
                state?.pools.find(
                  (p) =>
                    p.status === "distributing" ||
                    p.status === "completed" ||
                    p.status === "purchased",
                )?.pool_id ?? null
              }
              onBack={() => navigate("community")}
            />
          ) : null}

          {!showcase && view === "about" ? (
            <About
              health={health}
              demoConfig={demoConfig}
              memberCount={state?.counts.members ?? null}
              needCount={state?.counts.needs ?? null}
              onBack={() => navigate("home")}
              onOpenTechnical={() => {
                const pool = state?.pools[0];
                if (pool) void openPoolDetail(pool.pool_id, { tab: "activity", deep: "execution" });
                else navigate("pools");
              }}
            />
          ) : null}

          {!showcase && view === "pool" && openPool ? (
            <PoolRecord
              pool={openPool}
              runs={state?.runs ?? []}
              activity={(state?.activity ?? []).filter(
                (e) => e.pool_id === null || e.pool_id === openPool.pool_id,
              )}
              scenario={scenario}
              scenarioMs={scenarioMs}
              running={running}
              health={health}
              demoConfig={demoConfig}
              live={live}
              liveBusy={liveBusy}
              identity={identity}
              entry={poolEntry}
              onBack={() => navigate("pools")}
              onRefresh={() => void openPoolDetail(openPool.pool_id)}
              onRunLive={runLiveAgent}
              onRunScenario={runScenario}
            />
          ) : null}

          {!showcase && !state && view !== "needs" && view !== "operations" && view !== "about" ? (
            <p className="empty">Loading…</p>
          ) : null}
        </div>
      </main>

      <footer className="footer">
        <div className="wrap footer-inner">
          <span>
            Pool coordinates group purchases inside one community.{" "}
            <button className="linkish" onClick={() => navigate("about")}>
              What Pool is
            </button>{" "}
            ·{" "}
            <button className="linkish" onClick={() => setPanelOpen(true)}>
              {communityName} is a safe demo environment
            </button>{" "}
            — synthetic people, simulated money, real software.
          </span>
        </div>
      </footer>

      <DemoPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        state={state}
        health={health}
        demoConfig={demoConfig}
        identity={identity}
        onIdentity={setIdentity}
        onReset={reset}
        onRefresh={refreshAll}
        onAbout={() => navigate("about")}
        onTechnical={() => {
          const pool = state?.pools[0];
          if (pool) void openPoolDetail(pool.pool_id, { tab: "activity", deep: "execution" });
          else navigate("pools");
        }}
        onOperations={() => navigate("operations")}
        onShowcase={() => {
          setView("home");
          setShowcase("overview");
          setPanelOpen(false);
          window.scrollTo({ top: 0 });
        }}
        onLifecycle={() => {
          const pool = state?.pools[0];
          if (pool && scenario) {
            void openPoolDetail(pool.pool_id, { tab: "activity", deep: "walkthrough" });
          } else {
            void runScenario();
          }
        }}
      />
    </div>
  );
}

/** Kept out of the drawer's own file: the shell owns the affordance that opens it. */
export function CloseIcon() {
  return <IconCross />;
}
