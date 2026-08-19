import { useCallback, useEffect, useState } from "react";
import {
  AppState,
  DemoConfig,
  Health,
  LiveAgentResult,
  MapData,
  MemberView,
  RunReport,
  PoolView,
  ProductCandidate,
  ScenarioResult,
  api,
  resetWorkspaceId,
} from "./api";
import { BrandMark } from "./brand";
import { IconArrowLeft, IconCross } from "./ui";
import { About } from "./views/about";
import { Onboarding } from "./views/onboarding";
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

/** Until the first state read lands, nobody. The consumer's identity is server state —
 *  the account they set up during onboarding — rather than a constant compiled into the
 *  app. It used to be a hardcoded seeded student, which is how a visitor ended up being
 *  greeted by somebody else's name. */
const NOBODY: Identity = { id: "", display_name: "" };

export default function App() {
  const [view, setView] = useState<View>("home");
  /** Set when Home hands a chosen product to the Needs form. */
  const [pendingProduct, setPendingProduct] = useState<ProductCandidate | null>(null);
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
  /** Set only when the operator is deliberately acting for a synthetic participant.
   *  Null means "me", and "me" is whatever the server says the consumer account is. */
  const [actingAs, setActingAs] = useState<Identity | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  /** Which tab (and which deep view within Activity) a pool record should open on, so
   *  "see it run on AWS" can land on the evidence rather than on the front page of a
   *  record the visitor then has to navigate. */
  const [poolEntry, setPoolEntry] = useState<{ tab?: string; deep?: string }>({});
  const [showcase, setShowcase] = useState<ShowcaseView | null>(null);
  /** The current identity's own view of themselves — including which pool, if any, is
   *  genuinely theirs. Owned here rather than by each screen: two of them need it, one
   *  request answers both, and the outlook it carries is the most expensive read the
   *  API serves. Never inferred from the pool list. */
  const [member, setMember] = useState<MemberView | null>(null);
  /** What the last member-triggered run concluded about *this* member's declarations.
   *
   *  Kept here because it belongs to a run rather than to a screen: it is fetched once,
   *  from the server, keyed to that run's id, and cleared whenever the identity or the
   *  workspace changes. The server refuses to build one for a run that was not this
   *  member's, so a community scan and a previous visitor's run can never land here. */
  const [report, setReport] = useState<RunReport | null>(null);

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

  /** Who the app is acting as right now.
   *
   *  Normally the consumer's own account. When the operator has deliberately stepped
   *  into a synthetic participant, that participant — and the shell says so, loudly,
   *  because acting as somebody else should never be a state you are in by accident. */
  const consumer = state?.consumer ?? null;
  const identity: Identity =
    actingAs ??
    (consumer && consumer.household_id
      ? { id: consumer.household_id, display_name: consumer.display_name }
      : NOBODY);
  const needsOnboarding = Boolean(consumer && !consumer.onboarded);

  /* Whose pool is whose is a server question, and it is re-asked whenever the identity
     or the workspace changes. Cleared first so an operator stepping out of a synthetic
     participant can never carry that participant's pool back to their own screens. */
  useEffect(() => {
    let live = true;
    // Cleared first, so an operator stepping out of a synthetic participant can never
    // carry that participant's opportunity back onto their own screens.
    setMember(null);
    // A report describes one run, for one member. Stepping into another identity must
    // never leave the previous one's answer on screen.
    setReport(null);
    if (!identity.id) return;
    api
      .member(identity.id)
      .then((me) => {
        if (live) setMember(me);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [
    identity.id,
    state?.workspace,
    state?.pools.length,
    state?.decisions.length,
    state?.activity.length,
  ]);

  /** Leaving showcase mode points every request back at the visitor's own session.
   *
   *  Their state is not "restored" so much as never touched: the scripted lifecycle
   *  writes a separate partition, so stepping out is a matter of addressing the right
   *  one again. */
  const navigate = useCallback(
    (next: View) => {
      api.setShowcaseScope(false);
      setShowcase(null);
      setOpenPool(null);
      setView(next);
      setPanelOpen(false);
      void refresh();
      window.scrollTo({ top: 0 });
    },
    [refresh],
  );

  /** A product picked on Home, handed to the Needs form so the member does not have to
   *  search for the same thing twice. Cleared as soon as the form has taken it. */
  const startNeed = useCallback(
    (product: ProductCandidate | null) => {
      setPendingProduct(product);
      navigate("needs");
    },
    [navigate],
  );

  /** Entering showcase mode points every request at the showcase's own partition, so
   *  the scripted world is read from where it actually lives. */
  const showcaseTo = useCallback(
    (next: ShowcaseView) => {
      const entering = !api.inShowcaseScope();
      api.setShowcaseScope(true);
      setShowcase(next);
      setPanelOpen(false);
      if (entering) {
        setOpenPool(null);
        void refresh();
      }
      window.scrollTo({ top: 0 });
    },
    [refresh],
  );

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
  const invokeDeployedAgent = useCallback(
    async (action: "member" | "community" = "member"): Promise<LiveAgentResult | null> => {
    setLiveBusy(true);
    setLive(null);
    try {
      const result = await api.liveAgent(action);
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
    },
    [refresh],
  );

  /** Ask Pool to look at what *this member* buys.
   *
   *  Where it runs depends on the deployment, and the answer is never hidden. On the
   *  public demo it is the coordinator deployed on Bedrock AgentCore, working on this
   *  session's own DynamoDB workspace — so the pool that appears was formed by that run.
   *  Locally, or when the server explicitly confirms that no remote execution can still
   *  mutate the workspace, the same coordinator runs on this server with a deterministic
   *  planner in the model's place. Both are the real Strands loop and the real typed
   *  tools; `model_provider` on the run record says which one answered.
   *
   *  `member_scan` is the whole of what the browser sends. The server resolves whose
   *  declarations that means and builds the run's objective from stored state — there is
   *  no field here in which to name another household or supply a prompt.
   *
   *  Afterwards the run's id is used to read back what it concluded. Nothing about the
   *  answer is inferred from the response: the report is assembled server-side from the
   *  evaluation records that run wrote, and it comes back empty if the run was not this
   *  member's. */
  const findOpportunities = useCallback(async () => {
    setRunning(true);
    setReport(null);
    try {
      let runId = "";
      if (demoConfig?.live_agent_available) {
        const liveResult = await invokeDeployedAgent();
        if (liveResult?.ok) {
          runId = liveResult.run.run_id ?? "";
        } else if (!liveResult?.allow_local_fallback) {
          if (liveResult) setError(liveResult.reason);
          return;
        }
      }
      if (!runId) {
        runId = (await api.run("member_scan")).run_id;
        await refresh();
      }
      if (runId && identity.id) {
        try {
          setReport(await api.runReport(runId, identity.id));
        } catch {
          /* The run happened and the state is already re-read. An explanation that
             could not be fetched is worth losing; the result is not. */
        }
      }
      setView("home");
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [refresh, demoConfig, invokeDeployedAgent, identity.id]);

  /** The same invocation, reached from the technical view rather than from the product.
   *  One code path, so what a judge audits there is what the product actually did — and
   *  a community-wide scan, because a pool record is not anybody's own button and a
   *  member-anchored run reached from one would answer a question nobody asked. */
  const runLiveAgent = useCallback(async () => {
    await invokeDeployedAgent("community");
  }, [invokeDeployedAgent]);

  /** Replay the canonical scripted lifecycle — in its own world.
   *
   *  It always lands in showcase mode, because that is where it happened. The visitor's
   *  own account is in a different partition and is not read, written, or reseeded by
   *  any of this: a coffee-only member who watches the whey lifecycle end to end comes
   *  back to their own Needs page unchanged. */
  const runScenario = useCallback(async () => {
    setRunning(true);
    setPanelOpen(false);
    api.setShowcaseScope(true);
    try {
      const started = performance.now();
      const result = await api.scenario();
      setScenarioMs(Math.round(performance.now() - started));
      setScenario(result);
      setState(await api.state());
      setMap(await api.map());
      setShowcase("run");
      setView("home");
      if (result.pool_id) setOpenPool(await api.pool(result.pool_id));
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, []);

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
          ) : needsOnboarding ? (
            /* Nothing behind these links exists for somebody who has not finished
               setting up, and offering navigation into an account that is not ready yet
               is how a setup flow starts feeling optional. */
            <span className="nav-setup small muted">Setting up</span>
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
          {/* Stepping into a synthetic participant is operator work, and it is the one
              state where every screen below is answering somebody else's questions.
              Saying so continuously beats saying it once in a drawer nobody has open. */}
          {actingAs ? (
            <div className="acting-banner" role="status">
              <span>
                Demo controls — you are acting as <strong>{actingAs.display_name}</strong>,
                not as yourself.
              </span>
              <span className="spacer" />
              <button className="btn btn-sm" onClick={() => setActingAs(null)}>
                Back to you
              </button>
            </div>
          ) : null}
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

          {/* Setup comes before the product, and replaces it rather than sitting beside
              it — a half-configured account looking at a working Home is how the old
              build ended up greeting people by a stranger's name. Showcase mode skips
              it: that is the guided walkthrough, and it is explicitly not the consumer
              experience. */}
          {!showcase && needsOnboarding && consumer ? (
            <Onboarding
              consumer={consumer}
              onDone={async () => {
                setActingAs(null);
                await refresh();
                navigate("home");
              }}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "home" && state ? (
            <Home
              state={state}
              identity={identity}
              member={member}
              report={report}
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
              onStartNeed={startNeed}
              onGoCommunity={() => navigate("community")}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "pools" && state ? (
            <Pools
              state={state}
              onOpen={openPoolDetail}
              onFind={findOpportunities}
              running={running}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "needs" ? (
            <Needs
              identity={identity}
              communityName={communityName}
              initialProduct={pendingProduct}
              onConsumeInitialProduct={() => setPendingProduct(null)}
              onFind={findOpportunities}
              running={running}
              /* The read-only current outlook, labelled as one where it is shown. Home
                 poses the question before a run; this says how it looks as things
                 stand, which is a different claim and belongs beside the declaration. */
              outlook={member?.needs_outlook ?? []}
              /* This member's own pool, not "some pool exists". Answered by the
                 server from membership and need lineage. */
              hasPool={Boolean(member?.opportunity)}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "community" && state ? (
            <CommunityView
              state={state}
              map={map}
              onOpenPool={openPoolDetail}
              onRespond={respond}
              busyDecision={busyDecision}
              onOperations={() => navigate("operations")}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "operations" ? (
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

          {!showcase && !needsOnboarding && view === "about" ? (
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

          {!showcase && !needsOnboarding && view === "pool" && openPool ? (
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
        consumer={consumer}
        actingAs={actingAs}
        onActAs={setActingAs}
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
        /* Both branches land in the showcase, because that is the world the scripted
           lifecycle happened in. It used to open `state.pools[0]` — the oldest pool in
           whatever workspace was loaded, which after isolation is the visitor's own and
           has nothing to do with the replay. */
        onLifecycle={() => {
          if (scenario) showcaseTo("run");
          else void runScenario();
        }}
      />
    </div>
  );
}

/** Kept out of the drawer's own file: the shell owns the affordance that opens it. */
export function CloseIcon() {
  return <IconCross />;
}
