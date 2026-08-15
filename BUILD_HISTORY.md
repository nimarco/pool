# BUILD_HISTORY.md — Engineering Notebook for Pool

A factual, append-oriented development journal. **This is not a README and not a git changelog.**
Its purpose is to let us reconstruct the *truthful* development story later for:

- the three AWS Builder Center articles
- the Devpost submission
- the final README
- the architecture explanation
- the demo script
- the postmortem

The operating rules for the project live in [`AGENTS.md`](AGENTS.md). This file records what
actually happened.

---

## Rules for this file

**Read these before adding an entry.**

- **This history must remain truthful.** It is the primary source for public writing. A false entry
  becomes a false article.
- **Do not manufacture entries** for work that did not happen.
- **Do not claim a test passed unless it was actually run.**
- **Do not claim AWS infrastructure exists unless it was actually deployed.**
- **Do not claim a feature works because code exists.**
- **Distinguish clearly between planned, implemented, tested, and deployed** (vocabulary below).
- **Preserve failures and abandoned approaches.** These are the most valuable article material in
  the file. Do not tidy them away.
- Prefer **concise but information-dense** entries. Judgment and reasoning over narration.
- **Avoid enormous dumps of terminal output.** Quote the few lines that mattered.
- **Never include secrets.** No keys, tokens, credentials, or credential-bearing URLs — including
  inside pasted logs, traces, and screenshots.
- **Never include private user data.** Real addresses, real names, real contact details. Synthetic
  households only.
- **Do not rewrite old entries to make the project story look cleaner.**
- **Corrections are added explicitly** (see below), never applied by silent edit.

**Deserves an entry even when the visible change is small:**

- significant architecture changes (even when the UI barely moves)
- significant product decisions (even when little code changes)
- anything AWS-cost-related
- any change to autonomy or human-in-the-loop boundaries
- production or deployment incidents

**Does not need an entry:** meaningless formatting changes, renames, typos, formatter runs.

### Correcting an earlier entry

Do not edit the original. Append a new entry titled `Correction to #NNNN — <what was wrong>`, state
what the earlier entry claimed, what was actually true, and how we found out. Then add a single
line to the original entry: `> **Corrected by #NNNN.**` That one-line pointer is the only permitted
modification to a past entry.

---

## Conventions

**Order:** append-only, **oldest first**. New entries go at the bottom. Entries are numbered
sequentially (`#0001`, `#0002`, …) so they can be cross-referenced.

**Status vocabulary** — shared with `AGENTS.md`, used precisely:

| Term | Means |
| --- | --- |
| **Planned** | Decided, not written. |
| **Implemented** | Code exists and is runnable. Says nothing about correctness. |
| **Tested** | Verified by an actual executed test, fixture, or reproduced scenario. |
| **Deployed** | Actually running on AWS, verified by an observed response or trace. |

**Tags** — for finding article-worthy material later. Use only the tags genuinely relevant to an
entry. Do not spam every tag onto every entry; a file where everything is tagged is a file where
nothing is findable.

| Tag | Use for |
| --- | --- |
| `[ARTICLE-1]` | Concept and problem framing — why this is an agent problem. |
| `[ARTICLE-2]` | AWS and technical architecture — Strands, Bedrock, AgentCore, data. |
| `[ARTICLE-3]` | Autonomy and human-in-the-loop — act vs. ask. |
| `[DEMO]` | Material for the demo video or live demo. |
| `[ARCHITECTURE]` | Structural decisions and their consequences. |
| `[COST]` | Cost-relevant decisions, incidents, or bounds. |
| `[HITL]` | Human-in-the-loop and authorization semantics. |
| `[AGENT]` | Agent loop behavior, tool use, prompting, termination. |
| `[AWS]` | AWS service behavior, limitations, surprises. |

---

## Entry template

Copy this block for each new entry. Omit fields that genuinely do not apply — do not pad them with
"N/A" noise, but never omit a field to hide something.

```markdown
### #NNNN — [YYYY-MM-DD] — Short milestone title
`[TAG]` `[TAG]`

**Goal / user intent**
What we were trying to accomplish.

**Starting state**
What existed before this change, where relevant.

**Decision**
What architecture or product decision was made.

**Why**
Why this approach was selected, and what alternatives were considered and rejected.

**Implementation**
What materially changed. Status: planned / implemented / tested / deployed.

**AWS / external services touched**
Which cloud resources or services were actually used. "None" is a valid and common answer.

**Cost-relevant activity**
Meaningful paid AWS or model activity, unusual request volume, schedules created, browser/search
usage, or anything potentially persistent. Do not guess dollar figures if they are unknown —
describe the activity instead.

**Agent behavior** *(if applicable)*
Model/provider · tools available · tools called · iteration count and bounds · HITL behavior ·
termination condition · unexpected behavior.

**Validation**
Exactly how this was verified: tests run, fixture results, deployment checked, trace inspected,
API response verified, scenario reproduced. If it was not verified, say so plainly.

**Failures / dead ends**
What did not work, including approaches abandoned. Do not rewrite history to look clean.

**What we learned**
The concise technical or product lesson.

**Article fodder**
Which of Article 1 / Article 2 / Article 3 / demo / architecture diagram this may serve, and why.

**Evidence worth preserving**
Screenshots to capture, trace IDs or descriptions, architecture snapshots, benchmarks, test
output, before/after UI, interesting log output. Never store secrets or private data here.

**Relevant commits / files**
When known.
```

---

## Live AWS resource ledger

The one **mutable** section of this file. Every AWS resource created — including throwaway test
resources — is recorded here at creation time, per `AGENTS.md` §3.8. Rows move to *Destroyed* or
carry an explicit reason for remaining. Review this before ending any session that touched AWS.

### Active

| Resource | Service | Created | Purpose | Recurring cost? | Destroy by |
| --- | --- | --- | --- | --- | --- |
| _(none)_ | | | | | |

### Recurring / scheduled (highest risk — review every session)

| Resource | Schedule | Enabled? | Created | Kill switch | Destroy by |
| --- | --- | --- | --- | --- | --- |
| _(none)_ | | | | | |

### Destroyed

| Resource | Service | Created | Destroyed | Notes |
| --- | --- | --- | --- | --- |
| _(none)_ | | | | |

---

## Open questions / to verify

Tracked so they are not silently assumed. Move each to an entry when resolved.

| # | Question | Why it matters | Status |
| --- | --- | --- | --- |
| Q1 | Which Bedrock model tier is sufficient for the coordination loop? | Cost vs. reasoning quality; §3.3 says do not over-buy. | **Open** — a cost-efficient tool-use model is the documented default, but the exact inference-profile id is unverified against a live account. |
| Q2 | What state belongs in DynamoDB vs. AgentCore Memory? | `AGENTS.md` §6 sets the principle; the boundary is undecided. | **Resolved (#0004, #0008)** — AgentCore Memory is *not used*. Every piece of state Pool holds is transactional (commitments, money, quantities, membership, deadlines, policies), which §6 forbids putting in agent memory. Adding it would have been logo-collecting. Revisit only if durable learned preferences appear. |
| Q3 | Is AgentCore Runtime the right deployment target, or is plain Lambda sufficient? | Favorable for judging, but must be justified, not decorative. | **Partly resolved (#0009)** — both are implemented: Lambda serves the API, AgentCore hosts the coordinator via the official toolkit. Neither is deployed, so the operational comparison is still unmade. |
| Q4 | Do we need a real routing/geocoding provider, or do synthetic distances suffice for the demo? | Live routing is a per-request paid call (§3.4). | **Resolved (#0003)** — deterministic routing is the default so tests and demos are free; the Amazon Location `geo-routes` adapter is implemented and its parsing tested against the real service model. It has not been called live. |
| Q5 | How does a household express preauthorization (Smart Join) in a machine-verifiable way? | Core of Article 3; must not be an informal LLM judgment. | **Resolved (#0004)** — six numeric/boolean rules evaluated by a pure function returning a full audit trail. Stricter-of-policy-and-need wins. Every rule has a test proving it can block an auto-join. |
| Q6 | Re-verify hackathon requirements before submission. | Snapshot in `AGENTS.md` §2 is dated 2026-08-15. | **Open** — still required before submitting, and specifically before publishing any Builder Center article (the blog-post wording changed mid-event). |
| Q7 | Does the deterministic routing model resemble real travel times? | The demo shows travel minutes as if they were real. | **Open** — blocked on live AWS. Until then the provider is labelled in the API response and the UI. |
| Q8 | What is the actual per-run Bedrock cost at the configured bounds? | Determines whether a 6-hourly schedule is affordable. | **Open** — blocked on live AWS. |

--- | --- | --- | --- |
| Q1 | Which Bedrock model tier is sufficient for the coordination loop? | Cost vs. reasoning quality; §3.3 says do not over-buy. | Open |
| Q2 | What state belongs in DynamoDB vs. AgentCore Memory? | `AGENTS.md` §6 sets the principle; the boundary is undecided. | Open |
| Q3 | Is AgentCore Runtime the right deployment target, or is plain Lambda sufficient? | Favorable for judging, but must be justified, not decorative. | Open |
| Q4 | Do we need a real routing/geocoding provider, or do synthetic distances suffice for the demo? | Live routing is a per-request paid call (§3.4). | Open |
| Q5 | How does a household express preauthorization (Smart Join) in a machine-verifiable way? | Core of Article 3; must not be an informal LLM judgment. | Open |
| Q6 | Re-verify hackathon requirements before submission. | Snapshot in `AGENTS.md` §2 is dated 2026-08-15. | Open |

---

## Entries

### #0001 — [2026-08-15] — Repository documentation foundation
`[ARTICLE-1]` `[ARCHITECTURE]` `[COST]`

**Goal / user intent**
Establish durable operating rules and a truthful historical record *before* serious development
begins, so that (a) any coding agent joining later has full context without chat history, and
(b) the eventual Builder Center articles can be reconstructed from a real record rather than
invented after the fact.

**Starting state**
Empty directory at `~/Desktop/pool`. No files, no hidden files, no git repository, no code, no
AWS configuration, no dependencies.

**Decision**
Create two documents and nothing else:

- `AGENTS.md` — operating manual for coding agents: mission, hackathon-aware engineering, AWS cost
  safety, security and privacy, agent architecture principles, source of truth, development
  discipline, no-fake-demo rules, observability, documentation duties, and an end-of-task checklist.
- `BUILD_HISTORY.md` — this file: append-only engineering journal with a fixed entry template,
  article tags, a live AWS resource ledger, and an open-questions table.

Deliberately **not** done in this task: no feature code, no scaffolding, no dependency choices, no
`git init`, no AWS calls of any kind.

**Why**
Two constraints shaped this. First, the hackathon requires the project to be newly created during
the submission period, so the record of *how* it was built starts now and has to be real. Second,
the project runs on student promotional credits, so cost rules need to exist before the first agent
loop is written — retrofitting bounds onto a running system is how credits get burned.

Writing the history rules *first* is the load-bearing choice: a journal started after the
interesting decisions have been made can only be a reconstruction, and a reconstruction is exactly
what we are trying to avoid.

Alternatives considered:

- *Single `AGENTS.md` with a history section* — rejected. Operating rules are read constantly and
  should stay short; the journal only grows. Mixing them buries the rules.
- *Start coding and document afterward* — rejected. This is precisely the failure mode the task
  exists to prevent.
- *Separate infrastructure ledger as a third file* — rejected to keep the deliverable to two files.
  The ledger lives at the top of this file instead, and is explicitly marked as the single mutable
  section of an otherwise append-only document. Worth revisiting if it becomes noisy.

**Implementation**
Two files created: `AGENTS.md`, `BUILD_HISTORY.md`. Status: **implemented** (documentation only —
nothing here is executable, so "tested" does not apply).

**AWS / external services touched**
None. No AWS account access, no SDK calls, no credentials read, no resources created.

**Cost-relevant activity**
Three HTTP fetches of public Devpost pages (hackathon overview, rules, resources) to verify
competition requirements rather than assume them. No paid API usage. No model inference beyond the
authoring session itself. No schedules, no persistent resources. This task was effectively
cost-free.

**Validation**
- Confirmed the working directory was empty, including hidden files, before writing.
- Hackathon facts recorded in `AGENTS.md` §2 were read from the official Devpost pages on
  2026-08-15, not recalled from memory. Marked in-file as a dated snapshot requiring re-verification
  before submission (tracked as Q6).
- No claim of tested or deployed status is made anywhere in this entry.

**Failures / dead ends**
None yet — this is the first entry. The absence of failures here is a fact about the task being
documentation-only, not a sign of a smooth project.

**What we learned**
The hackathon's scoring shape (five equally weighted criteria; Design and Presentation together
40%) argues for building observability and evidence capture into the process from the start rather
than treating them as end-stage polish. Explaining the system *is* 40% of the score, and the same
artifacts serve the demo, the README, and the articles.

**Article fodder**
- **Article 1** — the framing in `AGENTS.md` §1 (why group buying fails on coordination labor
  rather than on software, and why latent demand discovery is the agent-shaped part of the problem)
  is the seed of the article's thesis.
- **Article 2** — the cost-safety constraints will shape real architecture choices; documenting
  them before building means the article can show constraints driving design rather than
  rationalizing it afterward.
- **Article 3** — the act-vs-ask split in `AGENTS.md` §5 is the starting position. Its evolution
  under real implementation pressure is the article's actual content.

**Evidence worth preserving**
- This entry as the zero point of the build timeline.
- The initial act/ask split and the AI-decides/code-verifies table in `AGENTS.md` §5, for later
  before-and-after comparison once reality has pushed back on them.

**Relevant commits / files**
`AGENTS.md`, `BUILD_HISTORY.md`. No commits — the repository is not yet under version control.

---

### #0002 — [2026-08-15] — Version control and secret-leak prevention
`[COST]`

**Goal / user intent**
Put the repository under version control and make `AGENTS.md` §4 (never commit secrets) and the
§3.1/§3.2 cost bounds mechanically enforced rather than merely written down.

**Starting state**
Two documentation files, no git repository, no ignore rules. Nothing prevented a future `.env`
containing AWS keys from being committed to a repository that must eventually be public.

**Decision**
`git init` on `main`; add `.gitignore` with secrets patterns listed first and explicitly annotated;
add `.env.example` carrying the loop bounds and the `SCHEDULES_ENABLED=false` kill switch as
committed defaults.

**Why**
The hackathon requires a public repository, so a leaked credential would be public and permanent —
and git history keeps it after deletion. Ignore rules are worth more before the first `.env` exists
than after.

Putting the §3.1 bounds in `.env.example` rather than leaving them to code makes them visible on
first clone and adjustable without a code change, as §3.1 requires. `SCHEDULES_ENABLED=false`
ships as the committed default so the safe state is what a fresh environment inherits.

The `.gitignore` also excludes raw traces and logs, which for this product will routinely contain
household locations (§4).

**Implementation**
`.gitignore`, `.env.example`, initial commit on `main`. Status: **implemented** — the bounds are
declared configuration only; no code reads them yet.

**AWS / external services touched**
None.

**Cost-relevant activity**
None. No resources, no schedules, no model calls.

**Validation**
`git check-ignore` confirmed `.env` is ignored and `.env.example` is not. Confirmed the initial
commit contains only the four intended files.

**Failures / dead ends**
None.

**What we learned**
Nothing novel — but worth recording that the cost bounds existed as enforced defaults from the
first commit, since the alternative (retrofitting bounds onto a running agent loop) is the standard
way credits get burned.

**Article fodder**
Minor. Possibly a supporting detail for Article 2 on constraints shaping the build from the start.
Not a story on its own — recorded because it is security- and cost-relevant per the entry rules,
not because it is interesting.

**Evidence worth preserving**
None beyond the commit itself.

**Relevant commits / files**
`.gitignore`, `.env.example`. Initial commit on `main`.

---

### #0003 — [2026-08-15] — Verified the toolchain instead of assuming it
`[ARTICLE-2]` `[AWS]` `[ARCHITECTURE]`

**Goal / user intent**
Establish the real API surfaces of Strands, boto3 Location, and AgentCore before writing
code against them, rather than writing from recall and debugging later.

**Starting state**
Two documentation files, a git repo, an MIT licence. No code, no dependencies, no AWS.

**Decision**
Install each SDK and introspect it. Take no API shape from memory.

**Why**
Assistant knowledge has a cutoff; these libraries move. A wrong parameter name discovered
at integration time costs far more than fifteen minutes of introspection, and this
repository has an explicit rule against inventing API details.

**Implementation**
Installed `strands-agents 1.52.0`, `boto3 1.43.72`, `bedrock-agentcore`. Introspected:
`Agent.__init__`, the `@tool` decorator, `BedrockModel(model_config=...)`, the hook event
classes and their fields, `Model.stream`, the streaming event TypedDicts, the `geo-routes`
and `location` service models, and `BedrockAgentCoreApp.entrypoint`. Status: **tested** —
every finding came from executing against the installed package.

**AWS / external services touched**
None. Service *models* were read from the local botocore data files; no API was called.

**Cost-relevant activity**
None. Package downloads only.

**Validation**
Direct introspection output, quoted into the design decisions it informed.

**Failures / dead ends**
`Session.get_service_model` does not exist on a boto3 `Session` — the loader is at
`Session()._loader.load_service_model(name, "service-2")`. Cost one wrong turn.

**What we learned**
Four findings that shaped the architecture:
1. Strands exposes a full hook system (`BeforeModelCallEvent`, `BeforeToolCallEvent`, …).
   That, not prompt instructions, is where loop bounds belong.
2. `BeforeToolCallEvent.cancel_tool` accepts a **string**, so a cancelled tool call can
   tell the model *why* — graceful termination instead of an opaque error.
3. Two AWS routing services exist. `geo-routes` requires **no provisioned route
   calculator**, unlike `location`. Chose it for operational reasons: one less billable
   resource to create and forget.
4. `geo-routes` takes `Position: [lon, lat]` and returns Distance in **metres**, Duration
   in **seconds**. Reversing the coordinate pair silently routes into the Indian Ocean, so
   there is now a test asserting the order.

**Article fodder**
Article 2 — "choosing an AWS API for operational rather than feature reasons" is a small
but real lesson, and the hook system is the technical centrepiece.

**Evidence worth preserving**
The `geo-routes` service-model output pinning `Position`/`Distance`/`Duration` semantics;
it is the justification for the routing test.

**Relevant commits / files**
`services/agent/pool/adapters/routing.py`, `pool/agent/bounds.py`, `agentcore_app.py`

---

### #0004 — [2026-08-15] — Deterministic domain: money, matching, allocation, policy
`[ARCHITECTURE]` `[ARTICLE-3]`

**Goal / user intent**
Build the layer that decides what is *true*, before any agent code exists.

**Decision**
A pure-Python domain package that cannot import a model client. Integer cents everywhere;
savings in basis points; largest-remainder cost allocation; an explicit legal-transition
table for the pool state machine; Smart Join as a pure function returning a full audit
trail.

**Why**
Pool handles other people's money. A model that can produce a price will eventually produce
a wrong one, and the error is invisible until someone is out of pocket. Making the boundary
*structural* — these modules have no path to an LLM — is stronger than making it a rule.

Basis points rather than float percentages so policy comparisons are exact integer
comparisons. Largest-remainder allocation so per-household shares always sum to exactly the
group total; two households comparing notes must never find a missing cent.

**Implementation**
`domain/{money,models,matching,allocation,policy,state}.py`. Status: **tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None.

**Validation**
`pytest` — allocation sums asserted exact across many totals; every Smart Join rule has a
test proving it can block an auto-join; every illegal state transition raises.

**Failures / dead ends**
First pricing model shared cost across *purchased* units rather than *requested* units,
which quietly hid case surplus and overstated savings. Corrected: the group pays for whole
cases and the surplus cost is shared across what people asked for, which is what actually
happens when neighbours split a case. There is now a test asserting that a near-empty case
produces *negative* savings rather than a flattering number.

**What we learned**
Deciding that savings may go negative — rather than clamping at zero — turned out to matter
more than expected. It is what lets the agent correctly conclude "this deal is not worth
doing" instead of always finding something to sell.

**Article fodder**
Article 3 — Smart Join's six-rule audit trail, and the choice to evaluate all rules rather
than short-circuit so the UI can show every reason a household is being asked.

**Relevant commits / files**
`services/agent/pool/domain/*`, `tests/test_{money,matching,allocation,policy,state}.py`

---

### #0005 — [2026-08-15] — First working Strands loop, with bounds that actually fire
`[AGENT]` `[COST]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
A real bounded agent loop: the agent chooses tools adaptively, and cannot run away.

**Decision**
One `PoolCoordinator` agent, seven narrow typed tools, and a `BoundedRun` HookProvider that
raises on run-level bounds and cancels on tool-level bounds.

**Why**
One agent, not a swarm: pricing/matching/routing/policy need to be correct, not creative,
so they are tools. Splitting cancel-vs-raise matters — a cancelled tool lets the model wind
down gracefully and *see why*; a breached iteration cap means the run is no longer trusted
to stop itself.

**Implementation**
`agent/{bounds,tools,coordinator,offline_model}.py`. Status: **tested**.

**AWS / external services touched**
None — the offline planner and deterministic routing were used throughout.

**Cost-relevant activity**
Zero tokens. Every run in this entry cost nothing.

**Agent behavior**
Model provider `offline`; 6 tools available; typical scan calls `list_unmet_demand →
evaluate_opportunity → create_buying_pool` in 4 iterations; terminates `completed`.

**Validation**
`tests/test_agent_bounds.py` drives the *real* Strands event loop with two deliberately
broken models: one repeating an identical call (cancelled by duplicate detection), one
varying its arguments to evade that (stopped by the iteration cap). Asserted that the fault
is stored, that the model was not invoked again after the cap, and that no reasoning text
appears in the run record.

**Failures / dead ends**
1. **`except BoundExceeded` never fired.** Strands wraps a hook exception in
   `EventLoopException`, so a tripped safety bound was being recorded as a generic crash —
   the single worst place to lose fidelity. Fixed by walking the `__cause__`/`__context__`
   chain (bounded to 12 links so a cyclic chain cannot spin).
2. **Token usage was always zero.** `stop_response` has only `message` and `stop_reason`;
   usage rides in `stop_response.message["metadata"]["usage"]`. Found by probing a live
   run, not by reading types. Now read per model call rather than from `AgentResult`, so an
   *aborted* run still records what it spent.

**What we learned**
When your safety net raises, verify the catch actually catches it. A bound that fires but
is mislabelled as a crash is worse than no bound, because it destroys the signal you built
it to produce.

**Article fodder**
Article 2 — both integration findings, with the fix. Article 3 — cancel-vs-raise as an
autonomy design decision.

**Evidence worth preserving**
The probe output showing `stop_response` attributes (`message`, `stop_reason` only) — it is
the justification for a non-obvious line of code.

**Relevant commits / files**
`services/agent/pool/agent/*`, `tests/test_agent_bounds.py`

---

### #0006 — [2026-08-15] — An offline planner so tests and demos cost nothing
`[COST]` `[ARTICLE-2]` `[DEMO]`

**Goal / user intent**
Run the complete agent path — repeatedly, in CI, during UI work — without spending tokens.

**Decision**
Implement the Strands `Model` interface with `DeterministicPlannerModel`: a planner that
reads structured tool results and emits the next tool call as real Bedrock-shaped stream
events.

**Why**
Cheap tests are the tests that actually get run. Mocking the *agent* would prove nothing —
the loop is the part most likely to break. Substituting only the model keeps the real event
loop, the real tools, the real domain math, the real state machine, and the real approval
boundary in the exercise.

Alternative considered: record/replay of real Bedrock responses. Rejected — it needs
credentials to record, and it goes stale the moment a tool schema changes.

**Implementation**
`agent/offline_model.py`. Emits `messageStart` / `contentBlockStart(toolUse)` /
`contentBlockDelta` / `contentBlockStop` / `messageStop`, plus a metadata event with
explicitly zero usage. Runs are labelled `model_provider="offline"` in the run record and
the UI. Status: **tested**.

**Cost-relevant activity**
Zero, permanently, by construction.

**Failures / dead ends**
**The planner looped forever.** Once every product had been evaluated and none was viable,
it re-issued `record_no_action` indefinitely. The iteration cap caught it and recorded a
`loop_fault` — the safety net working exactly as designed. But a system that needs its net
every run is a bug, so `record_no_action` was made terminal and a regression test added
that runs repeated scans and asserts none faults.

**What we learned**
Two things worth writing down. First, the guard proved itself against real (our own) buggy
code rather than a contrived test. Second, "the safety net fired" is a signal to fix the
thing that tripped it, not evidence the system is fine.

**Article fodder**
Article 2 — this is the strongest transferable idea in the project: how to test an agent
without paying for it, without mocking away the part you need to test.

**Relevant commits / files**
`services/agent/pool/agent/offline_model.py`,
`tests/test_persistence_and_termination.py::TestTerminationRegression`

---

### #0007 — [2026-08-15] — Tuning the demo so the dropout genuinely breaks the pool
`[DEMO]` `[ARTICLE-1]` `[ARTICLE-3]`

**Goal / user intent**
Make the showcase honest: the withdrawal has to *actually* kill the deal, and the recovery
has to *actually* find someone new.

**Starting state**
Working end-to-end scan, but the first tuning produced a pool with so much surplus demand
that no single withdrawal mattered. The "recovery" would have been theatre.

**Decision**
Two changes. (a) The supplier minimum sits just under the inner ring's aggregate demand, so
the pool is genuinely marginal. (b) A deliberate radius asymmetry: **form tight (2 km),
repair wide (8 km)**.

**Why**
The asymmetry is not a demo trick — it is the right product behaviour. Keep the initial
travel burden low; widen the net only when repairing, and even then every candidate is
still bounded by their own travel policy. It also makes the replacement genuinely *new*
rather than someone who should have been included originally.

Also fixed pickup-site selection: choosing the site nearest the demand *centroid* drifted
toward outliers and picked a site convenient for nobody. Now it maximises how many
households fall inside the formation radius, breaking ties on total distance.

**Implementation**
`data/seed.py` (25 households, 29 needs, 8 products, 13 offers, 5 sites — all synthetic),
`services/coordination.py` radius constants, `agent/tools.py` site selection. Status:
**tested**.

**Validation**
`make demo` and `tests/test_demo_scenario.py`. Observed: pool forms at 133/150 committed
(two households need approval) → approvals → 155/150 → largest participant withdraws (−30)
→ 125/150, status `recovering` → recovery run adds one Smart Join-eligible household →
155/150 `threshold_met`. Group savings $99.00, 42.3%. Zero existing members re-contacted.

**Failures / dead ends**
Three failed tunings before this. First: threshold too low, dropout irrelevant. Second:
formation radius too wide, so the reserve households were already in the pool and recovery
had nobody to find. Third: 50 lb cases left 22% surplus, which was honest but made the
savings look weak.

**What we learned**
It is easy to build a demo where the dramatic moment cannot actually fail. Forcing the
scenario to be genuinely marginal made both the product and the tests better — the
recovery path now has to really work, and the tests assert the *shape* of the outcome
(threshold broken, replacement found, nobody else disturbed) rather than pinned numbers.

**Article fodder**
Article 1 — the economics that make the pool marginal are the economics that make the
product necessary. Article 3 — "form tight, repair wide" as an escalation-minimising rule.

**Evidence worth preserving**
The `make demo` transcript. It is reproducible any time and is the core of the demo video.

**Relevant commits / files**
`services/agent/pool/data/seed.py`, `pool/services/{coordination,demo}.py`,
`tests/test_demo_scenario.py`

---

### #0008 — [2026-08-15] — API, web app, and the privacy boundary
`[ARCHITECTURE]` `[DEMO]`

**Goal / user intent**
A consumer product a judge can use without an account, and a privacy boundary that is
enforced rather than promised.

**Decision**
FastAPI (uvicorn locally, Lambda via Mangum in cloud) plus a React/TypeScript SPA. Each
visitor gets an isolated workspace. Household coordinates are snapped to a ~110 m grid
**in the API layer**, before they leave the process.

**Why**
Enforcing privacy at the serialisation boundary means no future UI change can leak a
precise position — the data never reaches the client. A convention would eventually be
broken by a well-meaning feature.

Workspaces isolate judges from each other and carry a DynamoDB TTL, which is both a
privacy and a cost property.

**Implementation**
`pool/api/app.py`, `apps/web/*`. Design system deliberately avoids the purple-gradient AI
house style: paper-and-ink palette, one warm and one cool accent, serif display against a
sans UI face, tabular numerals. Dark mode, reduced-motion, skip link, ARIA progressbar.
Status: **tested** (API), **implemented + manually verified in a browser** (web).

**AWS / external services touched**
None — in-memory repository throughout.

**Validation**
`tests/test_api.py` including an explicit assertion that the map endpoint can never return
a precise household coordinate and never returns names on markers. Manually exercised in a
browser: landing → scan → pool formed (42.3%) → decision inbox populated → full guided
scenario returning all seven steps. `npm run build` clean; `tsc -b --noEmit` clean.

**What we learned**
Putting the privacy rule in the serialiser rather than the component made it testable in
one assertion. Privacy properties that can be unit tested are the ones that survive.

**Article fodder**
Article 1 — a neighbourhood product where location privacy is a design constraint rather
than a settings toggle.

**Evidence worth preserving**
Screenshots to capture for the article and video: decision inbox with the "why you're being
asked" line; activity feed showing automatic recovery; the approximate-position map.

**Relevant commits / files**
`services/agent/pool/api/app.py`, `apps/web/src/*`, `tests/test_api.py`

---

### #0009 — [2026-08-15] — Infrastructure, with cost claims turned into tests
`[AWS]` `[COST]` `[ARCHITECTURE]`

**Goal / user intent**
Reproducible, cheap, destroyable infrastructure — and a guarantee that the cost properties
stay true.

**Decision**
AWS CDK (Python): DynamoDB on-demand + TTL, Lambda + API Gateway HTTP API, EventBridge rule
**created disabled**, S3 + CloudFront. AgentCore Runtime deliberately excluded from the
stack — it is deployed with its own official tooling.

Then: assert every cost claim against the synthesized template in `infra/test_stack.py`.

**Why**
A cost rule in a document decays. A cost rule in a test fails the build. The tests assert
the schedule is DISABLED, DynamoDB is PAY_PER_REQUEST with a TTL, log retention is bounded,
no always-on resource type exists, nothing survives `cdk destroy`, no IAM policy grants
wildcard actions, and the web bucket blocks public access.

AgentCore is excluded from CDK because duplicating its container build and IAM would be
exactly the fragile custom path to avoid — but it is called out in `COST_NOTES.md` as the
resource most likely to be forgotten, precisely *because* `cdk destroy` will not remove it.

**Implementation**
`infra/app.py`, `infra/test_stack.py`, `scripts/*.sh`, `Makefile`. Status: **tested**
(synth + 21 assertions). **Not deployed.**

**AWS / external services touched**
None. `cdk synth` runs entirely offline.

**Cost-relevant activity**
None. No resource created.

**Validation**
Synthesized `PoolStack.template.json` and asserted against it: EventBridge `State:
DISABLED`, DynamoDB `PAY_PER_REQUEST` + TTL enabled, log retention 14 days, zero always-on
resource types.

**Failures / dead ends**
The tagging test failed, and it was a real defect rather than a bad test: tags were applied
at the *app* level (`cdk.Tags.of(stack)` after construction), so any other instantiation of
`PoolStack` would produce untagged resources — and untagged resources are the ones you
cannot find later when hunting for strays. Moved tagging inside the stack constructor.

Also hit two CDK deprecations (`point_in_time_recovery`, `log_retention`). Fixing the
second was worth more than it looked: an implicit Lambda log group **survives
`cdk destroy`** and retains logs indefinitely. Declaring it explicitly makes it destroyable.

**What we learned**
Writing tests against infrastructure found a real bug in ten minutes. The "assert your cost
claims" pattern is cheap and should be the default for any credit-constrained project.

**Article fodder**
Article 2 — turning cost policy into CI assertions; the implicit-log-group trap.

**Relevant commits / files**
`infra/app.py`, `infra/test_stack.py`, `Makefile`, `scripts/*.sh`

---

### #0010 — [2026-08-15] — Submission artifacts
`[DEMO]` `[ARTICLE-1]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
Make the work explicable to a judge who never runs it, and preserve article material while
it is still accurate.

**Implementation**
`README.md`, `docs/ARCHITECTURE.md`, `docs/architecture.{mmd,svg}`,
`docs/HACKATHON_SCORECARD.md`, `docs/DEMO_SCRIPT.md`, `docs/DEVPOST_DRAFT.md`,
`docs/ARTICLE_NOTES.md`, `docs/COST_NOTES.md`. Status: **implemented**.

**Validation**
Diagram rendered with `@mermaid-js/mermaid-cli` and visually checked. The README status
table and the scorecard both mark every cloud item as unverified, matching reality.

**What we learned**
Writing the scorecard exposed that the *only* materially incomplete category is "nothing
has run in the cloud". Everything else is done and tested. Knowing that precisely is more
useful than a long generic backlog.

**Article fodder**
All three. `ARTICLE_NOTES.md` now carries the failures and dead ends from entries #0003–
#0009 while they are still accurate, which was the entire point of starting the journal
before the build.

**Relevant commits / files**
`README.md`, `docs/*`
