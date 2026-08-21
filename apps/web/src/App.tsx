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
  ScenarioResult,
  api,
  resetWorkspaceId,
} from "./api";
import { BrandMark } from "./brand";
import { Picked } from "./chosen";
import { IconArrowLeft, IconCross } from "./ui";
import { About } from "./views/about";
import { JudgeDemo } from "./views/judge";
import { Verify } from "./views/verify";
import { WhyThisOrder } from "./views/why";
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

type View =
  | "home"
  | "pools"
  | "needs"
  | "community"
  | "pool"
  | "operations"
  | "about"
  | "judge"
  | "why"
  | "verify";

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
];
/* Operations is deliberately absent. The console records supplier facts against the
   workspace the client is addressing, and inside showcase mode that is the showcase's
   own partition — so a presenter could write a rice quote into the recording between two
   takes and find out from a figure that stopped matching. The server refuses it now
   (`api/app.record_supplier_update`); this stops the door existing at all. */

/** Three destinations, and each one finishes the sentence "this page exists so a member
 *  can ___".
 *
 *    Home          … see what Pool needs from them and what it is doing right now
 *    Orders        … see and act on the group orders they are in
 *    What you buy  … manage the list of things Pool watches for them
 *
 *  **Community was removed from here, not renamed.** It could not finish that sentence.
 *  For a new account it was 3.45 viewport-heights of eight sections in which nearly every
 *  figure read $0.00: community-wide economics, an attention ledger, a
 *  responsibility-boundary explanation, a money ledger, a decision inbox for other
 *  people, a scatter of dots, and a link to the Operations console. All of it real, none
 *  of it an answer to anything a member came to the page with. It is judge proof and
 *  operator capability, and both now live behind one entry point in the footer.
 *
 *  `Pools` became `Orders` for the collision the vocabulary audit found: `Pool` is the
 *  product, and the nav was using the same word for the thing it makes. */
const NAV: { id: View; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "pools", label: "Orders" },
  { id: "needs", label: "What you buy" },
];

/** Until the first state read lands, nobody. The consumer's identity is server state —
 *  the account they set up during onboarding — rather than a constant compiled into the
 *  app. It used to be a hardcoded seeded student, which is how a visitor ended up being
 *  greeted by somebody else's name. */
const NOBODY: Identity = { id: "", display_name: "" };

/** The one linkable entry point. Everything else is a state machine, deliberately —
 *  Pool is one screen deep in most places and a router would be ceremony. But
 *  verification is a thing somebody is *sent to*, so `/verify` has to survive being
 *  typed, pasted and reloaded. Read once, at mount, from the real path. */
function initialView(): View {
  if (typeof window === "undefined") return "home";
  return window.location.pathname.replace(/\/+$/, "") === "/verify" ? "verify" : "home";
}

/** Whether this session may drive other synthetic participants.
 *
 *  Development and rehearsal only. The primary member experience never sets it, and the
 *  controls it reveals are *absent* rather than hidden when it is off — hiding an
 *  act-as control with CSS leaves it on the tab order, which is the same problem wearing
 *  a stylesheet. */
function operatorRequested(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("operator") === "1";
}

export default function App() {
  const [view, setView] = useState<View>(initialView);
  const [operatorMode] = useState(operatorRequested);
  /** Set when Home hands a chosen product to the Needs form. */
  const [pendingProduct, setPendingProduct] = useState<Picked | null>(null);
  const [state, setState] = useState<AppState | null>(null);
  const [map, setMap] = useState<MapData | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [openPool, setOpenPool] = useState<PoolView | null>(null);
  /** Which declaration "Why this order?" is about. One server read behind it, so the
   *  screen survives a reload — the old judge demo held its narrative in React state and
   *  lost it, which is the failure this replaces. */
  const [why, setWhy] = useState<{ needId: string; productName: string } | null>(null);
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
  /** Bumped when something changed the world that `/api/state` cannot see.
   *
   *  The member read below is re-triggered by the identity, the workspace, and three
   *  counts off `/api/state` — pools, decisions, activity — which between them catch
   *  everything a *coordination* write does. Recording a supplier quote does none of
   *  those things: it writes one offer row deliberately and nothing else, so that the
   *  mutation stays provable. The consequence is that the one screen whose whole job is
   *  to show the outlook moving would have gone on showing the old one.
   *
   *  An explicit epoch rather than a wider heuristic: the caller knows it changed the
   *  world, and making the server write a row it does not need in order to signal the
   *  browser would trade a real invariant for a refresh. */
  const [worldEpoch, setWorldEpoch] = useState(0);

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

  /* Dropping what was read for a *different subject* — and only for that.
   *
   * An operator stepping out of a synthetic participant must not carry that
   * participant's opportunity back onto their own screens, and a report describes one
   * run for one member, so neither may outlive a change of identity or of partition.
   *
   * Deliberately separate from the read below. The two used to be one effect, which
   * meant every reason to re-read was also a reason to wipe — so re-reading after the
   * world changed silently threw away the previous run's report, which is the one thing
   * in this app that is *supposed* to stay put while the world moves on. */
  useEffect(() => {
    setMember(null);
    setReport(null);
  }, [identity.id, state?.workspace]);

  /* Whose pool is whose is a server question, and it is re-asked whenever anything
     could have changed the answer: the identity, the partition, the three `/api/state`
     counts every coordination write moves, and an explicit signal for the writes that
     move none of them. */
  useEffect(() => {
    let live = true;
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
    worldEpoch,
  ]);

  /** Something changed the deterministic picture without changing anything
   *  `/api/state` counts. Re-read the server rather than adjusting anything here: what
   *  the outlook now says is the server's answer, and this only asks for it again. */
  const worldChanged = useCallback(() => {
    setWorldEpoch((n) => n + 1);
    void refresh();
  }, [refresh]);

  /** Everything held about *a* workspace, dropped because we are about to address a
   *  different one.
   *
   *  `member` and `report` are server answers scoped to one partition, and the effect
   *  above only notices a workspace change one render later — by which time Home has
   *  already asked the new partition for the old partition's pool id and been given a
   *  404. Dropped in the same callback that moves the scope, alongside `openPool`, which
   *  was already here for exactly this reason. */
  const forgetWorkspaceState = useCallback(() => {
    setOpenPool(null);
    setMember(null);
    setReport(null);
  }, []);

  /** Leaving showcase mode points every request back at the visitor's own session.
   *
   *  Their state is not "restored" so much as never touched: the scripted lifecycle
   *  writes a separate partition, so stepping out is a matter of addressing the right
   *  one again.
   *
   *  **Dropping that state is conditional, and has to be.** `forgetWorkspaceState`
   *  answers "we are about to address a different partition", not "the screen changed".
   *  It used to run on every view change, and the effect that refetches `member` is
   *  keyed on the identity, the workspace and three counts off `/api/state` — none of
   *  which move when a member walks from Home to Needs. So the state was cleared and
   *  then never re-asked: their standing demand, their current outlook and **Run Pool
   *  now** disappeared until the page was reloaded. `showcaseTo` already guarded the
   *  same call this way on the way in; this is the same rule on the way out. */
  const navigate = useCallback(
    (next: View) => {
      const leaving = api.inShowcaseScope();
      api.setShowcaseScope(false);
      setShowcase(null);
      /* Verification is a world, not a screen, so its scope survives navigation *within*
         it. Entering it happens on the page itself; leaving it is the visitor going back
         to their own session, which nothing here does implicitly — a member who wandered
         out of the coffee community and found their declaration gone would have been told
         the product forgot it. */
      if (leaving) forgetWorkspaceState();
      setView(next);
      setPanelOpen(false);
      void refresh();
      window.scrollTo({ top: 0 });
    },
    [refresh, forgetWorkspaceState],
  );

  /** What was picked on Home, handed to the form so the member does not have to search
   *  for the same thing twice. A family or a product; cleared once the form has it. */
  const startNeed = useCallback(
    (picked: Picked | null) => {
      setPendingProduct(picked);
      navigate("needs");
    },
    [navigate],
  );

  /** Entering showcase mode points every request at the showcase's own partition, so
   *  the scripted world is read from where it actually lives.
   *
   *  **The only way into showcase mode.** It used to be reachable from the drawer by
   *  setting the view directly, which left the scope on the visitor's session: the
   *  showcase's front page then read the visitor's community and printed its member and
   *  need counts as the showcase's. Moving the screen and moving the scope are one act,
   *  so they are one function. */
  const showcaseTo = useCallback(
    (next: ShowcaseView) => {
      const entering = !api.inShowcaseScope();
      api.setShowcaseScope(true);
      setShowcase(next);
      setPanelOpen(false);
      if (entering) {
        forgetWorkspaceState();
        void refresh();
      }
      window.scrollTo({ top: 0 });
    },
    [refresh, forgetWorkspaceState],
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
    // Reached from the drawer, this is what moves the scope, so it is also what has to
    // drop what was read from the partition being left.
    forgetWorkspaceState();
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
  }, [forgetWorkspaceState]);

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
      // The run it described no longer exists. A report is about one run in one
      // workspace, and leaving it up after a reset would be the clearest possible
      // version of a stale answer.
      setReport(null);
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
              /* No operations console in here. See SHOWCASE_NAV. */
              onOperations={null}
            />
          ) : null}

          {showcase === "pool" && openPool ? (
            <PoolRecord
              pool={openPool}
              mine={
                member
                  ? [member.opportunity?.pool_id, ...member.other_pool_ids].includes(
                      openPool.pool_id,
                    )
                  : null
              }
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
          {/* Verification explains the world before asking for a name. Somebody sent a
              link to check a claim should read what they are about to do first; the
              account step is a normal member action and happens when they start. */}
          {!showcase && needsOnboarding && view !== "judge" && view !== "verify" && consumer ? (
            <Onboarding
              consumer={consumer}
              onJudgeDemo={() => navigate("judge")}
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
              onWhy={(needId, productName) => {
                setWhy({ needId, productName });
                navigate("why");
              }}
              liveDiscovery={Boolean(demoConfig?.live_agent_available)}
              region={demoConfig?.region ?? null}
            />
          ) : null}

          {view === "why" && why ? (
            <WhyThisOrder
              needId={why.needId}
              productName={why.productName}
              onBack={() => navigate("home")}
            />
          ) : null}

          {view === "verify" ? (
            <Verify
              health={health}
              onStart={() => navigate("needs")}
              onHome={() => navigate("home")}
            />
          ) : null}

          {!showcase && !needsOnboarding && view === "pools" && state ? (
            <Pools
              state={state}
              member={member}
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
              onTechnical={() => {
                const pool = state?.pools.find((p) => p.execution_proof) ?? state?.pools[0];
                if (pool) void openPoolDetail(pool.pool_id, { tab: "activity", deep: "execution" });
                else navigate("pools");
              }}
              /* Through `showcaseTo`, so entering the recording moves the partition every
                 request addresses rather than only the screen. */
              onLifecycle={() => {
                if (scenario) showcaseTo("run");
                else void runScenario();
              }}
              onAbout={() => navigate("about")}
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
              onWorldChanged={worldChanged}
            />
          ) : null}

          {/* Reachable *before* setup, unlike every other destination: a judge who has
              never seen Pool should not have to guess their way through four onboarding
              screens to reproduce one claim, and step 1 performs that setup for them
              through the same endpoints. */}
          {!showcase && view === "judge" ? (
            <JudgeDemo
              member={member}
              hasOrder={Boolean(member?.opportunity)}
              onBack={() => navigate("home")}
              /* The lifecycle itself, not the showcase's front page. The same handler
                 Behind Pool's "one order, stage by stage" uses — it runs the scripted
                 replay if it has not run yet, in the showcase's own partition, so a judge
                 arriving from the walkthrough lands on the sheet rather than on a
                 second home screen with nothing on it. */
              onShowcase={() => {
                if (scenario) showcaseTo("run");
                else void runScenario();
              }}
              onBehindPool={() => navigate("community")}
              /* `worldChanged`, not `refreshAll`. Importing a quote writes one offer row
                 and deliberately moves none of the counts the member read is keyed on —
                 that is the no-demand-injection property — so a plain refresh would
                 leave the walkthrough showing the previous answer. This is the epoch that
                 already exists for exactly this case; the operations console uses it for
                 the same reason. */
              onRefresh={worldChanged}
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
              mine={
                member
                  ? [member.opportunity?.pool_id, ...member.other_pool_ids].includes(
                      openPool.pool_id,
                    )
                  : null
              }
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
            — synthetic people, simulated money, real software.{" "}
            {/* The one door to everything a judge or an operator needs: how this
                community works, where the money went, what the agent actually ran, and
                the console that drives a multi-person demo alone. A member never has to
                come through here, and nothing behind it is required to use Pool. */}
            <button className="linkish" onClick={() => navigate("community")}>
              Behind Pool
            </button>{" "}
            ·{" "}
            {/* The scripted judge demo used to live here. It walked somebody through
                loading a fixture, recording a quote and pressing "run agent" — six
                actions whose only purpose was advancing a demo, which is precisely the
                thing a judge is trying to see past. Verification now starts a fresh
                synthetic community and asks them to use the product. The old harness is
                still reachable at /judge for regression; it is not a front door. */}
            <button className="linkish" onClick={() => navigate("verify")}>
              Verify this yourself
            </button>
          </span>
        </div>
      </footer>

      <DemoPanel
        open={panelOpen}
        /* Operator capability is opt-in and absent otherwise. `?operator=1` is a
           development and rehearsal affordance rather than a feature: a member never
           needs it, the primary recording never uses it, and the regression harnesses
           that do need it still have somewhere to come from. Read from the URL rather
           than kept in state, so it cannot be reached by wandering. */
        operator={operatorMode}
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
        /* Through `showcaseTo`, not around it: entering showcase mode has to move the
           partition every request addresses, and a second copy of that logic here is how
           the two drifted apart. */
        onShowcase={() => {
          setView("home");
          showcaseTo("overview");
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
