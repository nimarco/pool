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

**Still empty, and that is accurate.** Entries #0019, #0020 and #0021 made real Bedrock
calls, but an on-demand model invocation creates no resource: it is billed per token and
there is nothing to destroy, forget, or leave running. #0022 prepared the AgentCore
deployment and stopped at a dry run, creating nothing at all — the account holds no
CloudFormation stack, no runtime, no bucket, no ECR repository, and no role beyond three
AWS service-linked ones. Account 860325090409, `us-east-1`.

**Pending approval, not yet created.** The first real `agentcore deploy` will require a
CDK bootstrap (`CDKToolkit`: an S3 staging bucket, an ECR repository, an SSM parameter,
and five `cdk-*` roles, one holding `AdministratorAccess`) before the four-resource Pool
stack. Both belong in the table above the moment they exist. Note that the runtime's
CloudWatch log group is created by the service *outside* the stack and has no retention
policy, so `agentcore destroy` will not remove it — see #0022.

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
| Q1 | Which Bedrock model tier is sufficient for the coordination loop? | Cost vs. reasoning quality; §3.3 says do not over-buy. | **Resolved (#0019, #0021)** — `us.amazon.nova-lite-v1:0` drove discovery correctly three runs of three, and the consequential recovery + lock branch correctly six runs of six, well inside every bound. One known rough edge, characterised in #0021 and tracked as Q16: in 1 of 12 coordinator runs it opened a turn with an invented pool identifier, which deterministic code refused without touching state. The documented default `us.anthropic.claude-haiku-4-5-20251001-v1:0` exists as an inference profile in the account but has still not been run. |
| Q2 | What state belongs in DynamoDB vs. AgentCore Memory? | `AGENTS.md` §6 sets the principle; the boundary is undecided. | **Resolved (#0004, #0008)** — AgentCore Memory is *not used*. Every piece of state Pool holds is transactional (commitments, money, quantities, membership, deadlines, policies), which §6 forbids putting in agent memory. Adding it would have been logo-collecting. Revisit only if durable learned preferences appear. |
| Q3 | Is AgentCore Runtime the right deployment target, or is plain Lambda sufficient? | Favorable for judging, but must be justified, not decorative. | **Partly resolved (#0009, #0022)** — both are implemented: Lambda serves the API, AgentCore hosts the coordinator. #0022 replaced the retired starter-toolkit path with the official `@aws/agentcore` CLI and took it to a verified dry run: **4 resources**, one runtime plus its execution role, no ECR and no CodeBuild under `CodeZip`. Both paths are now CDK-based, so the comparison is narrower than it looked. Still not deployed — the operational comparison waits on a CDK bootstrap. |
| Q4 | Do we need a real routing/geocoding provider, or do synthetic distances suffice for the demo? | Live routing is a per-request paid call (§3.4). | **Resolved (#0003)** — deterministic routing is the default so tests and demos are free; the Amazon Location `geo-routes` adapter is implemented and its parsing tested against the real service model. It has not been called live. |
| Q5 | How does a household express preauthorization (Smart Join) in a machine-verifiable way? | Core of Article 3; must not be an informal LLM judgment. | **Resolved (#0004)** — six numeric/boolean rules evaluated by a pure function returning a full audit trail. Stricter-of-policy-and-need wins. Every rule has a test proving it can block an auto-join. |
| Q6 | Re-verify hackathon requirements before submission. | Snapshot in `AGENTS.md` §2 is dated 2026-08-15. | **Open** — still required before submitting, and specifically before publishing any Builder Center article (the blog-post wording changed mid-event). |
| Q7 | Does the deterministic routing model resemble real travel times? | The demo shows travel minutes as if they were real. | **Open** — blocked on live AWS. Until then the provider is labelled in the API response and the UI. |
| Q8 | What is the actual per-run Bedrock cost at the configured bounds? | Determines whether a 6-hourly schedule is affordable. | **Measured (#0019, re-measured #0020, extended #0021)** — a discovery run is 6 ConverseStream calls, ~19.2k input / ~490 output tokens, ~5.5 s after the tool-result projection (was ~35.7k / ~420 / ~6 s). A recovery run is 4–5 calls and 11.3k–14.5k input tokens; a lock run 3–6 calls and 7.1k–17.0k. The consequential branches are **cheaper** than discovery — they read a 468-byte work queue instead of evaluating economics across the community. Dollar cost still not asserted: the current Bedrock rate has not been checked. |
| Q9 | Does the Stripe PaymentIntent manual-capture flow behave as documented? | The whole payment lifecycle rests on it, and it has never touched Stripe's servers. | **Open** — needs TEST keys. Re-read the current official docs first; the shapes were written from documentation, not from a response. |
| Q10 | Is the platform fee mode (10% of gross savings) defensible as a business model? | It is provisional business configuration, not domain truth. | **Open** — aligned by construction (no saving, no fee) and transparent, but untested against anyone's willingness to pay. |
| Q11 | Does the case-fitting solver stay fast with realistic community sizes? | It is a bounded DP; bounded is not the same as fast at scale. | **Open** — trivially fast at demo scale (tens of members). Needs a benchmark at a few hundred before a pilot. |
| Q12 | What actually happens to unclaimed paid-for goods? | The lifecycle deliberately stops at operator review. | **Open** — a policy question with legal edges. See `docs/PILOT_READINESS.md`. |
| Q13 | Should tool results be trimmed before they reach the model? | Measured 85:1 input-to-output tokens (#0019). `evaluate_pool_economics` alone returns ~2,250 tokens and is re-sent every turn, so the cost grows with community size. | **Resolved (#0020)** — yes, by projection, not by summarization. `pool/agent/projection.py` gives the model the decision-critical facts and keeps the complete deterministic result for the API, auditing, and tests. Re-measured on the same model, seed, scenario and bounds: **35.8k → 19.2k input tokens (−46%)**, identical tool sequence and outcome. The "fetch detail on demand" shape was rejected: a thirteenth tool costs schema bytes on every turn and buys an extra paid iteration. |
| Q14 | Does the agent handle the harder branches on a small model? | Only discovery has run on Bedrock. Recovery, final offer, and lock involve more state and more careful ordering. | **Resolved for recovery and lock (#0021)** — six real-model runs of the payment-failure recovery branch, shaped so lost demand (2 units) and merely-unanswered demand (4 units) are different numbers. Every run repaired exactly the hole, left the pending buyers alone, preserved the case boundary, and did not lock; three of six *attempted* the lock and were refused by the viability engine. Then locked correctly once the humans answered. `issue_final_offer` was never reached on a pool that already had one, so that ordering rule is still only proven offline. |
| Q15 | Are the tool schemas worth 6.8 KB of context on every turn? | After #0020 compacted the results, the twelve tool schemas are **62% of the model's remaining context** — 6,805 bytes re-sent per turn. | **Open** — measured, deliberately not acted on. The docstrings are what lets a small model pick the right tool, so trimming them trades selection quality for tokens. Answering it needs an A/B on the real model, not a byte count. #0021 is a point against trimming: tool selection was correct in 12 of 12 runs. |
| Q16 | Should consequential tool docstrings state that identifiers must come from a read tool? | #0021 observed the real model opening a turn with `recover_pool(pool_id="short_of_demand_pool")` — an invented identifier passed to a money-adjacent tool. Refused before touching state, and the model recovered, but it happened in 1 of 12 runs. | **Open, deliberately** — the safety property is proven and regression-tested (all seven consequential tools refuse an invented id before reading or writing anything). The candidate mitigation is one sentence per docstring; it is a *behavioural* change to tool selection, so adopting it means re-running the paid verification and it should be its own decision, not a drive-by edit during a verification. See Q15 — it also adds schema bytes to every turn. **#0022 made the refusal observable** without touching model behaviour: the hosted entrypoint now reports `ok` and `summary` per tool call, so a deployed run can prove an invented id was *rejected* rather than merely showing that `recover_pool` was called. That was a prerequisite for testing this on AgentCore at all — with `POOL_REPOSITORY=memory` the run record dies with the microVM, so the response and the logs are the only evidence. |

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

---

### #0011 — [2026-08-16] — Community as a first-class boundary, and the canonical lifecycle
`[ARCH]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Take Pool from a polished neighbourhood prototype to the canonical product: a
collective-purchasing coordinator with Communities, a paid fulfilment side, real financial
commitment, purchase execution, and physical handoff.

**Starting state**
A working v1: `Household` / `NeedDeclaration` / `Offer` / `Pool` / `Membership`, a
`CANDIDATE → INVITING → THRESHOLD_MET → CONFIRMED` lifecycle, Smart Join, dropout recovery,
198 app tests + 21 infra tests passing, lint clean. Verified by running the baseline before
touching anything, rather than trusting the previous run's summary.

**Decision**
Extend rather than rebuild. Map the old concepts into the canonical model:

| Old | Canonical |
| --- | --- |
| `Household` | kept — it *is* the account unit; a Community membership is a separate entity |
| implicit "neighbourhood" | `Community` + `CommunityMembership` + verification providers |
| `PoolStatus` (8 states) | 13-state canonical lifecycle |
| `MembershipState` | `ParticipationState` — provisional vs funded is now explicit |
| `allocation.py` | `economics.py` — complete landed cost, not merchandise-only |

Deleted `domain/allocation.py` outright rather than keeping a second pricing path. Two
sources of truth about what something costs is the failure mode most worth avoiding here.

**Why**
The brief's non-negotiable is that Community, not campus, is the domain concept. Keeping
`Household` as the account entity avoided a rename that would have churned 198 tests for no
semantic gain — a dorm room is a household. `CommunityMembership` is keyed
`(community_id, household_id)` so one account belonging to several Communities is a schema
fact rather than a future migration.

**Implementation**
`domain/models.py` rewritten (~1,200 lines: 25 entities, 20 enums, 4 config dataclasses).
New: `economics.py`, `viability.py`, `hosting.py`, `timing.py`, `substitution.py`,
`pickup.py`. `state.py` rewritten around the canonical adjacency. Status: **tested**.

**AWS / external services touched**
None.

**Cost-relevant activity**
None. Everything ran offline.

**Validation**
443 application tests + 24 infrastructure tests passing, all offline. The state machine has
property tests rather than a restatement of the table: nothing reaches `LOCKED` except from
`FUNDING`/`RECOVERING`, and nothing rewinds out of a captured state.

**Failures / dead ends**
First attempt kept `allocation.py` alongside `economics.py` "for compatibility". Within an
hour there were two functions that could disagree about a price. Deleted it.

**What we learned**
The single most useful artifact was the two-column table of *what the model may decide* vs
*what deterministic code must determine*. It made the tool surface, the module boundaries,
and the test list all fall out. Writing it before the code would have saved a rewrite.

**Article fodder**
Article 1 — mapping an existing domain onto a larger canonical one without forking it.

**Relevant commits / files**
`services/agent/pool/domain/*`

---

### #0012 — [2026-08-16] — Complete landed economics, and two circular definitions
`[ECONOMICS]` `[ARTICLE-1]` `[ARTICLE-3]`

**Goal / user intent**
Make the buyer-facing price include every modelled cost — merchandise, host pay, card
processing, and Pool's own fee — so Smart Join is evaluated against net savings rather than
a headline number with the operating costs hidden.

**Decision**
Fix an explicit computation order, because two components are circular if computed naively:

1. merchandise and host compensation (independent of fees)
2. **platform fee = share of *gross* savings** — defined without referring to the total it
   belongs to
3. split across buyers by units, largest-remainder
4. **processing grossed up per buyer**: `charge = ceil((share + fixed) × 10000 / (10000 − bps))`
5. all-in = the sum; net savings = retail − all-in

**Why**
A percentage-of-savings fee aligns incentives (no saving, no fee) and reads honestly on an
offer. But savings depend on the total, which includes the fee — so the fee is drawn from
*gross* savings instead, which is well-defined and monotone.

Processing is the subtler one. The processor takes a cut of the amount you charge,
*including* the processing itself. Computing the fee on the pre-fee share under-recovers by
roughly 3% of the fee — a few cents per buyer. Nobody would notice, and it is a silent
platform subsidy, which the brief explicitly forbids.

**Implementation**
`domain/economics.py`. Every value is integer cents; floats never touch money.
Status: **tested**.

**Validation**
`test_economics.py` asserts buyer lines sum to exactly the all-in total, that each component
split sums to its own total, and that the gross-up never under-recovers. Demo output:
$756.00 merchandise + $44.68 host + $28.06 processing + $32.70 fee = $861.44 against
$1127.76 retail — 23.6% net.

**What we learned**
"Include all costs" sounds like an accounting requirement. It is actually two small algebra
problems, and getting either wrong produces a system whose real unit economics differ from
the ones it displays.

**Article fodder**
Article 1 (why transparency is a design constraint), Article 3 (the subsidy failure mode).

**Relevant commits / files**
`services/agent/pool/domain/economics.py`, `tests/test_economics.py`

---

### #0013 — [2026-08-16] — Zero speculative surplus became a solver, not a refusal
`[ECONOMICS]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Honour the rule that Pool never quietly buys the leftovers of a part-filled case.

**Starting state**
The first implementation was a *check*: if case rounding left surplus, refuse to lock. Ran
the demo and the pool refused — 29 units against 12-unit cases leaves 7 unallocated. The
rule was working and the product was unusable.

**Decision**
Make it a solver. `fit_to_cases` chooses the buyer subset whose quantities sum to a multiple
of the case size and clear the minimum — a bounded exact search over reachable totals,
capped a few cases above the minimum, preferring members whose need is already due over
demand pulled forward from the future.

**Why**
"Do not buy speculative stock" is only half a rule. The other half is "so choose a buyer set
that doesn't require any". Rejecting is honest; solving is a product.

This also turned the flexible-future-demand mechanic from decoration into load-bearing
machinery. In the demo, current demand is 18 units against a 24-unit minimum and a 12-unit
case size — the *only* way to a viable pool is pulling forward exactly six units from
members who authorised an early purchase.

**Implementation**
`fit_to_cases` in `domain/economics.py`, wired into `evaluate_opportunity`.
Status: **tested**.

**Validation**
`test_economics.py` covers exact fill, priority preference, refusal when nothing lands on a
boundary, refusal below the minimum, and determinism across repeated runs. The end-to-end
scenario now produces exactly 2 cases, 24 units, 0 surplus.

**Failures / dead ends**
Considered "allow explicit extra-unit decisions" (ask a buyer to take a spare). Rejected for
v1: it is a real product option but it puts a question in front of a human to solve a
problem the system can solve itself, which is backwards.

**What we learned**
A constraint that only ever rejects is usually a constraint you have not finished
implementing.

**Relevant commits / files**
`services/agent/pool/domain/economics.py`

---

### #0014 — [2026-08-16] — The fulfilment side: candidates, ranking, and refusing politely
`[HOSTS]` `[PRODUCT]` `[ARTICLE-1]`

**Goal / user intent**
Model fulfilment as a real economic side: recruited, ranked, paid, and refusable.

**Decision**
- Candidates come from **two** sources: standing hosts, and pool members who click "offer to
  host" on this specific pool. A buyer needs no prior registration.
- Offering is **not** claiming. Several people may offer; a deterministic evaluator filters
  and ranks; the top eligible candidate receives an offer; decline or expiry moves to the
  next. No first-come-first-served path exists in the code.
- Eligibility is **factual and fails closed**: availability, vehicle, capacity, weight,
  supplier travel, pickup-site suitability, and their own minimum compensation. A candidate
  who breaks one is ineligible with a stated reason, not merely lower-ranked.
- Ranking optimises the **whole transaction** — buyer travel is weighted more heavily than
  host cost, because buyers outnumber the host.
- Compensation scales with work and splits into **earned** (the run) and **contingent** (the
  handoff), so a buyer no-show cannot erase pay for work already done.

**Why**
A host who is paid the same for 5 orders and 30 will stop showing up. And a system that
lets someone claim a job by clicking first optimises for reflexes rather than for the group.

**Implementation**
`domain/hosting.py` (evaluation, ranking), `services/hosting.py` (recruit, offer, accept,
decline, expire, assign). Status: **tested**.

**Validation**
`test_hosting.py` covers every refusal reason individually plus the "pricier but more
central host wins" case. In the demo, four candidates are evaluated: two eligible, one
refused for wanting more than the job pays, one refused for having no vehicle for a 55 kg
load.

**What we learned**
Exposing the score *components* rather than just the score turned an opaque decision into
something a judge can read off the screen — and made a ranking bug obvious during
development, because the component that was wrong was visible.

**Relevant commits / files**
`services/agent/pool/domain/hosting.py`, `services/agent/pool/services/hosting.py`

---

### #0015 — [2026-08-16] — Payments: authorise late, capture at lock, and refuse live keys
`[PAYMENTS]` `[SECURITY]` `[ARTICLE-3]`

**Goal / user intent**
Real financial commitment semantics without any possibility of real money moving.

**Decision**
- `PaymentProvider` abstraction with a deterministic in-process simulated provider and a
  Stripe **TEST-only** provider.
- `StripePaymentProvider` **refuses to construct** with anything that is not an `sk_test_`
  key. No flag, no environment override, no argument relaxes it.
- Saving a payment method is separate from authorising a pool charge. Nobody's card is
  touched when they add a recurring need.
- Authorise **after** the host is selected and the quote refreshed; capture **at lock**.
- Explicit internal payment states mapped to provider states. There is no `paid = true`
  anywhere in the system.
- Webhook signatures verified with Stripe's documented scheme using only `hmac`, with
  event-id deduplication and timestamp tolerance.

**Why**
The hackathon environment must not be able to silently fall back to live Stripe. Making that
a construction-time exception rather than a runtime check means a misconfigured environment
fails loudly before it can do anything.

Implementing signature verification ourselves rather than via the SDK keeps it testable
offline with no secret in the repository — and it is thirty lines.

**Implementation**
`adapters/payments.py`, `services/payments.py`. The simulated provider declines any method
reference containing a marker string, which is how the failure branch is triggered
deterministically rather than waited for. Status: **tested** (simulated),
**implemented-unverified** (Stripe — never contacted Stripe's servers).

**AWS / external services touched**
None. No Stripe API call has ever been made from this repository.

**Validation**
`test_payments.py` — 43 tests including live-key refusal, duplicate capture, capture
failure, replay rejection, stale-timestamp rejection, and a late authorisation event failing
to walk a capture backwards. An infra test asserts no Stripe marker appears in the
synthesized CloudFormation template.

**What we learned**
"Never use live keys" as a documented rule is worth much less than one unconditional
`raise` in a constructor. The rule cannot be forgotten, mis-configured, or overridden by a
future well-meaning change.

**Article fodder**
Article 3 — safety properties that are structural rather than procedural.

**Relevant commits / files**
`services/agent/pool/adapters/payments.py`, `services/agent/pool/services/payments.py`

---

### #0016 — [2026-08-16] — Recovery was over-recruiting, and reporting its own success wrong
`[BUG]` `[AGENT]` `[ARTICLE-3]`

**Goal / user intent**
Make payment-failure recovery real: when an authorisation fails, find compatible replacement
demand and restore the order.

**Starting state**
The first implementation computed the shortfall as `threshold − funded_units`. Ran the
scenario: recovery recruited three replacements for a two-unit gap, taking the pool from 24
units to 29 — against a 12-unit case size, which then correctly refused to lock on surplus.

**Decision**
Two fixes, both conceptual:

1. **Distinguish lost demand from pending demand.** A buyer who has not yet answered their
   final offer has not left. Only failed authorisations, withdrawals, and declines are a
   hole. `in_play_units` counts funded *plus* awaiting-decision; `lost_units` is the gap
   against that.
2. **Replacements must sum to *exactly* the gap.** "At least enough" reintroduces the
   speculative-surplus problem the case-fitting solver exists to prevent. Implemented as a
   small bounded exact-sum search; when nothing sums to the gap, recovery fails honestly.

Then a third, found by a test: recovery still reported `recovered=False` when the pool was
whole, because success was measured against *funded* units — which cannot be complete while
humans are still deciding. Recovery's job is to fill the hole, not to finish the pool.

**Why**
Over-recruiting trades a funding problem for an inventory problem. And an operation measured
against something it does not control will misreport its own outcome in a way that tests
happily pass.

**Implementation**
`services/coordination.py` — `in_play_units`, `lost_units`, `_select_replacements`, and the
`recovered` criterion. Also propagated into the agent's work-queue tool so the planner acts
on lost units rather than on a raw threshold gap. Status: **tested**.

**Validation**
`test_coordination.py::test_recovery_replaces_exactly_what_was_lost` and
`test_an_unanswered_buyer_is_not_treated_as_a_hole_to_fill`. The end-to-end scenario now
goes 24 → 22 (a card declines) → 24 (exact replacement), never above 24.

**Failures / dead ends**
The greedy "largest contributors first until covered" selection from the v1 dropout recovery
was carried over unchanged and was exactly wrong for a case-boundary world. It had been
correct when surplus cost was simply shared across buyers.

**What we learned**
The best bug in the project so far. Two systems that were individually right — recover the
shortfall, never buy surplus — combined into something wrong, and only an end-to-end run
surfaced it. Neither unit test suite could have.

**Article fodder**
Article 3, prominently. This is the concrete story for "the failure modes of an agent system
are mostly at the seams".

**Relevant commits / files**
`services/agent/pool/services/coordination.py`

---

### #0017 — [2026-08-16] — Pickup credentials, and a planner that watches what it did
`[FULFILLMENT]` `[SECURITY]` `[AGENT]`

**Goal / user intent**
Physical handoff that is proved rather than asserted, and an agent loop that can move a pool
through several steps in one run.

**Decision — credentials**
Each buyer allocation gets a one-time credential: a long token for the QR and a short
human-readable code for when scanning is awkward. **Only hashes are stored.** The plaintext
exists exactly once, in the response that issued it; re-issuing invalidates the previous
pair. Verification is constant-time. The short-code alphabet excludes I, L, O, U, 0 and 1 so
a code read aloud at a pickup table cannot be mistyped into someone else's allocation.

A host cannot mark an order collected without a credential. The only other route is an
operator override that requires a stated reason, preserves the previous state in the audit
record, and revokes any outstanding credential.

**Decision — planner**
The offline planner re-reads its work queue after acting, capped at twice per run.

**Why**
Storing plaintext credentials would mean a database dump is a free-goods coupon book.
Hashing costs nothing and makes re-issue meaningful.

On the planner: a loop that reads its queue once, acts, then decides from a stale view will
never notice that the pool it just repaired has become lockable. But unbounded re-reading is
polling with extra steps — hence the cap, which is also below the duplicate-call bound that
would have caught it anyway.

**Implementation**
`domain/pickup.py`, `services/fulfillment.py`, `agent/offline_model.py`.
Status: **tested**.

**Validation**
`test_fulfillment.py` covers single use, wrong-pool rejection with a distinct reason,
unknown-credential rejection, re-issue invalidation, and the absence of any host-facing
"mark all collected" path. The scenario re-scans one used credential on purpose and it is
rejected.

**Failures / dead ends**
First version of the scenario replayed *every* credential to prove the property. It worked,
and it buried the activity feed under ten rejection events. Now it proves it once; the
exhaustive coverage lives in the test suite. Demonstrating a property and testing it are
different jobs.

**What we learned**
"Observe after acting, at most twice" turned out to be the whole difference between a
planner that needs three separate invocations and one that can carry a pool from final offer
to lock in a single bounded run.

**Relevant commits / files**
`services/agent/pool/domain/pickup.py`, `services/agent/pool/services/fulfillment.py`,
`services/agent/pool/agent/offline_model.py`

---

### #0018 — [2026-08-16] — Four surfaces, and a transcript that told the truth in the wrong order
`[UX]` `[DEMO]`

**Goal / user intent**
Buyer, host, operator, and judge experiences on the canonical API, plus a demo transcript a
judge can follow without reading code.

**Implementation**
`apps/web/src/{api,views,App}.tsx` rebuilt on the new API. Six views: community dashboard
with Decision Inbox, pool detail with the cost breakdown and the eleven viability checks,
needs, host job with a working code scanner, operator console, agent trace, impact.
Status: **tested** (typecheck, build, and driven in a real browser).

**Validation**
Ran the full scenario from the UI in a browser: all six views render, no console errors, no
horizontal overflow at 375 px on any view, dark mode correct. Screenshots of the cost
breakdown and host ranking captured for the demo.

**Failures / dead ends**
Three real fixes came out of browser QA that no test would have caught:

1. The demo transcript reported `funded_units` *after* recovery had already run, so the
   payment-failure step showed a number that contradicted its own narrative. The steps were
   in the wrong order. Fixed by capturing the failure snapshot before the inbox step and by
   sourcing the recovery evidence from the activity log rather than assuming which run did
   it — the agent legitimately recovers in whichever run notices first.
2. A stale pool id in a client that had outlived a server restart produced an alarming error
   banner. A missing pool now just refreshes the list.
3. The needs table showed identical values in the "restock lead" and "will buy early"
   columns, because the seed set them equal — hiding the exact distinction the copy was
   explaining.

**What we learned**
The transcript bug is the interesting one. Every individual number was true; the *order*
made them read as a contradiction. A demo that reports live state at render time rather than
at the moment things happened will eventually tell a true story dishonestly.

**Relevant commits / files**
`apps/web/src/*`, `services/agent/pool/services/demo.py`, `services/agent/pool/data/seed.py`

---

### #0019 — [2026-08-16] — First real Bedrock inference, and the bug that only a live call could find
`[AWS]` `[AGENT]` `[COST]` `[ARTICLE-2]`

**Goal / user intent**
The smallest honest proof that the chain is real: Bedrock model → Strands agent → an
existing typed Pool tool → deterministic result → recorded outcome. No AgentCore, no
persistent resources, no scaffolding of a second agent.

**Starting state**
AWS authenticated for the first time: profile `pool-dev`, region `us-east-1`, non-root
IAM user `pool-admin` (account 860325090409). A direct Converse call to
`amazon.nova-lite-v1:0` had already succeeded (9 in / 6 out / 314 ms). Everything in this
repository had run offline until this point; `MODEL_PROVIDER=bedrock` had never executed.

**Decision**
Change only the model leg. Keep the production `PoolCoordinator`, the twelve existing
tools, every bound, and every other adapter (in-memory store, deterministic routing,
simulated payments) exactly as they were.

**Implementation**
Three changes, all in the model/provider path:

1. **`agent/coordinator.py` — fixed a real bug.** `BedrockModel` was being constructed as
   `BedrockModel(region_name=..., model_config={"model_id": ..., "max_tokens": ...})`.
   It takes its configuration as **keyword arguments**, not as a `model_config` dict. The
   dict was accepted into the config under a key nothing reads, `model_id` was never set,
   and Strands fell back to *its own* default (`global.anthropic.claude-sonnet-4-6`). So
   `BEDROCK_MODEL_ID` was silently ignored — a configured model that would never have been
   the model actually invoked.
2. **`agent/coordinator.py` — profile support.** Added `_boto_session()`: a named profile
   for local development, `None` for the default credential chain that Lambda and
   AgentCore use via execution roles. `BedrockModel` rejects `region_name` and
   `boto_session` together, so whichever applies is passed, never both.
3. **`config.py`** — added `aws_profile`, read from `AWS_PROFILE`, defaulting to empty.

**AWS / external services touched**
- `sts:GetCallerIdentity` — confirmed non-root before anything else.
- `bedrock:ListFoundationModels`, `bedrock:ListInferenceProfiles` — read-only.
- `bedrock-runtime:ConverseStream` — **18 real streaming calls across 3 verification runs**
  (6 per run). Model: `us.amazon.nova-lite-v1:0`.

**No resource was created.** No DynamoDB table, no Lambda, no AgentCore runtime, no
schedule. The AWS resource ledger stays empty. No Stripe call was made and payment
behaviour was untouched.

**Cost-relevant activity**
Per run, consistently across three runs:

| Metric | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| ConverseStream calls | 6 | 6 | 6 |
| Input tokens | 35,706 | ~35,700 | 35,836 |
| Output tokens | 418 | ~430 | 439 |
| Wall clock | 6.4 s | — | 5.6 s |
| Iterations (bound 8) | 6 | 6 | 6 |

Roughly **107k input / 1.3k output tokens total** on Nova Lite. Not priced here, because
the current rate has not been checked against the Bedrock price list and a guessed figure
is worse than none — but Nova Lite is the cheapest text model in the account and the
absolute spend is small.

**The number that matters is the ratio, not the total.** 35.7k input tokens for 418 output
tokens is 85:1. The cause is measured, not assumed: `evaluate_pool_economics` returns
**9,015 characters (~2,250 tokens)** of structured JSON, `list_latent_demand` returns
1,311, and Strands resends the whole conversation on every turn — so each large tool
result is re-billed on every subsequent call. This is precisely what `AGENTS.md` §3.3
warns about ("do not resend enormous histories when compact structured state will do"),
and it would have stayed invisible forever on the offline path, which charges nothing for
verbosity. On Nova Lite it is pocket change; on a frontier model the same run would cost
roughly fifty times more, and it grows with community size because the payload carries
every candidate.

Deliberately **not** fixed in this entry — trimming what the model sees is a behavioural
change to the agent and deserves its own decision, not a drive-by edit during a
verification. Logged as Q13.

**Agent behavior**
Model `us.amazon.nova-lite-v1:0` · 12 tools available · 5 called, in this order:

```
list_latent_demand → evaluate_pool_economics → create_candidate_pool
  → find_host_candidates → request_host_acceptance
```

That is the canonical workflow, chosen by the model. Nothing scripted it, and the
sequence was identical across all three runs. 6 iterations against a bound of 8; no bound
fired; terminated `completed` with outcome `pool_created`.

The deterministic half did its own job underneath: a real pool formed at
`host_recruiting` with 10 members against a 24-unit threshold, and four activity events
were written — including the host ranking that offered the job to `hh_marchetti`.

**Validation**
`pool/scripts/verify_bedrock.py`, run three times. It asserts twelve properties including
*real bedrock-runtime HTTPS calls observed in botocore's own endpoint log* — wire-level
evidence rather than our own logging claiming a call happened. All twelve passed each
time.

Then offline: **445 application tests + 24 infrastructure tests passing**, lint clean. The
offline path is unaffected.

Six new regression tests (`TestBedrockModelConstruction`) assert the configured model id
and token ceiling actually reach the model, that no unknown config key is silently
accepted, and that region and session are never passed together. They need **no
credentials** — verified by running them with `HOME` and every AWS variable stripped.

**Failures / dead ends**
1. **`boto3` could not resolve the profile at all**: `MissingDependencyException — using
   the login credential provider requires botocore[crt]`. The profile uses the newer
   `login_session` flow. Fixed by installing `botocore[crt]` into the local venv. It is a
   *local development* dependency only — Lambda and AgentCore authenticate with execution
   roles and never touch that provider — so it was deliberately not added to the runtime
   dependencies.
2. **`ValueError: Cannot specify both region_name and boto_session`** on the first
   corrected construction. The session already carries a region.

**What we learned**
The offline planner is excellent for testing everything *except the thing it replaces*.
A whole configuration path — construction, credentials, region, model id — had never
executed, and it was wrong in a way that no amount of offline testing could surface: the
system would have run happily against a model nobody chose. The lesson is not "test with
real calls"; it is that a substituted component leaves a *specific shaped hole*, and that
hole is exactly where the untested code lives. One real call cost pennies and found two
bugs and a dependency gap.

**Article fodder**
Article 2, and it is now unblocked for its first section. Three concrete findings: the
`model_config` kwargs bug, the `region_name`/`boto_session` exclusivity, and the
`botocore[crt]` requirement for the login credential provider. Plus the 85:1
input-to-output ratio, which is the most transferable cost lesson in the project so far.

**Evidence worth preserving**
`pool/scripts/verify_bedrock.py` output — it prints the botocore wire calls, the tool
sequence with argument digests, the resulting stored state, and the token counts, and it
is re-runnable for a screenshot.

**Relevant commits / files**
`services/agent/pool/agent/coordinator.py`, `services/agent/pool/config.py`,
`services/agent/pool/scripts/verify_bedrock.py`,
`services/agent/tests/test_agent_bounds.py`

### #0020 — [2026-08-16] — The model was paying to re-read what it already knew
`[AWS]` `[AGENT]` `[COST]` `[ARCHITECTURE]` `[ARTICLE-2]`

**Goal / user intent**
Close Q13. The first real Bedrock run spent 35.7k input tokens to produce 418 output
tokens, and the cause was a measured one: large tool results re-sent on every turn.
Reduce what the model *sees* without moving any fact out of deterministic code.

**Starting state**
The canonical local implementation, fully tested, with three consistent real Bedrock
discovery runs on `us.amazon.nova-lite-v1:0`. Tool results went to the model exactly as
the services computed them — `assessment.to_dict()` and friends, in full.

**Decision**
Add a **projection layer** between the deterministic result and the model:
`pool/agent/projection.py`. Tools call the same services, retain the complete
authoritative result on `ToolContext.full_results`, and return a compact view to the
model. Projections are pure selection and aggregation — they compute no money, no
quantity, no verdict.

**Why**
Three alternatives were considered and rejected:

1. **A "fetch the detail" tool** (the shape sketched when Q13 was opened). A thirteenth
   tool costs schema bytes on *every* turn, and any run that used it would spend an
   extra paid iteration to get back what it should have been handed the first time.
2. **Strands context management.** Evaluated against the installed version,
   `strands-agents 1.52.0`. The default `SlidingWindowConversationManager(window_size=40)`
   is already active and never engages: a discovery run produces ~13 messages. Its
   truncation is *reactive* — it fires on `ContextWindowOverflowException`, keeping the
   first and last 200 characters of a tool result, which cuts JSON mid-structure and
   could remove the blocking reason or viability verdict the model needs.
   `SummarizingConversationManager` and proactive compression generate the summary *with
   a model*: an extra paid call, and an LLM paraphrase of deterministic numbers becomes
   the model's version of the truth. That is the exact failure AGENTS.md §5 exists to
   prevent. Not adopted. It is the right tool for long open-ended conversations, and
   this is a bounded 6-turn workflow.
3. **Trimming the domain objects.** Rejected outright — the per-household lines and the
   host reward breakdown are what the operator UI and the audit trail are made of.

**Implementation** — implemented and tested.

Measured first, then cut. Instrumenting the `messages` list handed to `stream()` on
every turn gave the actual amplification, rather than an assumption about which payload
was worst:

| Tool result | Bytes | Re-sent | Amplified | Share |
| --- | --- | --- | --- | --- |
| `evaluate_pool_economics` | 9,015 | ×4 | 36,060 | 71% |
| `list_latent_demand` | 1,311 | ×5 | 6,555 | 13% |
| `find_host_candidates` | 2,241 | ×2 | 4,482 | 9% |
| `request_host_acceptance` | 2,283 | ×1 | 2,283 | 4% |
| `create_candidate_pool` | 446 | ×3 | 1,338 | 3% |

Inside the 9,015 bytes: `candidates` 4,596 (one record per household) and
`economics.lines` 3,673 (a second record per household). Both scale with community size;
neither is decision-critical. Across the rest of the lifecycle the same measurement found
`issue_final_offer` at 4,048 bytes, `inspect_pool` at 2,079, and `lock_pool` at 1,746 —
each dominated by per-household lists or the roster of viability checks that *passed*.

What each projection keeps is the shape of the decision it supports: the verdict, the
blocking reason, the identifiers the next tool call takes, the magnitudes that make an
opportunity worth pursuing, package/surplus status, and counts of the humans involved.

| Tool result | Before | After | Change |
| --- | --- | --- | --- |
| `evaluate_pool_economics` (viable) | 9,015 | 841 | −90.7% |
| `evaluate_pool_economics` (refusal) | 697 | 356 | −48.9% |
| `issue_final_offer` | 4,048 | 534 | −86.8% |
| `request_host_acceptance` | 2,283 | 736 | −67.8% |
| `find_host_candidates` | 2,241 | 694 | −69.0% |
| `inspect_pool` | 2,079 | 977 | −53.0% |
| `lock_pool` | 1,746 | 302 | −82.7% |
| `list_latent_demand` | 1,311 | 1,140 | −13.0% |
| `create_candidate_pool`, `recover_pool`, `execute_purchase`, `list_pools_needing_attention` | ≤ 468 | unchanged | measurement did not justify touching them |

A side effect worth naming: no tool takes a household id as an argument, so the ten
household identifiers per turn were never actionable. They are now counts. That is a
privacy improvement (§4) that happened to be free.

**AWS / external services touched**
`bedrock-runtime:ConverseStream` — **40 real streaming calls**: 14 baseline (2 runs on
the stashed pre-change code, so the comparison is same-session and same-environment), 20
after (5 runs), and 6 confirming the shipped code after two tool docstrings were corrected
to describe what the projections actually return. Model `us.amazon.nova-lite-v1:0`,
profile `pool-dev`, `us-east-1`, non-root IAM. **No resource was created**; the ledger
stays empty. AgentCore was not deployed. No Stripe call was made and payment behaviour was
untouched.

**Cost-relevant activity**

| Discovery run | Before | After | Change |
| --- | --- | --- | --- |
| Input tokens (6-iteration runs) | 35,929 · 35,706 · 35,836 | 19,179 · 19,327 · 19,062 · 19,314 · 19,434 | **−46.2%** |
| Input tokens (8-iteration runs) | 54,710 | 28,148 | **−48.5%** |
| Output tokens | ~430–505 | 444–589 | +14% |
| Input:output ratio | 85:1 | 39:1 | |
| Wall clock | 5.7–7.3 s | 5.1–6.9 s | −8% |
| ConverseStream calls | 1 per iteration | unchanged | |

Offline, where the whole context is measurable rather than inferred: amplified tool-result
bytes across a discovery run fell **35,464 → 8,711 (−75.4%)**, and total context sent
across all turns fell **84,417 → 55,025 bytes (−34.8%)**.

**Agent behavior**
Same model, same seed, same scenario, same bounds. Five of six runs produced the exact
canonical sequence in six iterations:

```
list_latent_demand → evaluate_pool_economics → create_candidate_pool
  → find_host_candidates → request_host_acceptance
```

The sixth went to eight iterations, adding `issue_final_offer` (which the tools correctly
refused — "no host has accepted this pool yet") and `list_pools_needing_attention`. **This
is pre-existing variance, not a regression**: one of the two baseline runs did exactly the
same thing, which is why the baseline was re-run rather than quoted from #0019. Every run
ended `completed` with outcome `pool_created`, a pool at `host_recruiting` with 10 members
against a 24-unit threshold, and four activity events. Final state identical before and
after.

**Validation**
`pool/scripts/verify_bedrock.py` — all twelve checks passed on all six post-change runs,
including wire-level evidence of real `bedrock-runtime` requests in botocore's endpoint
log.

Offline: **472 application tests + 24 infrastructure tests passing**, lint clean, secret
scan clean. 21 of those tests are new (`tests/test_agent_projection.py`) and need no
credentials: they assert that each projection keeps the identifiers the next tool call
takes, that every surviving figure equals the service's own value rather than a re-derived
one, that refusals keep their reasons, that the authoritative result — per-household
lines, reward breakdowns, full check rosters — is still reachable behind the projection,
and that no tool result in the full lifecycle exceeds a 1,500-byte budget. That last one
is the regression guard: it fails the moment someone reintroduces a 9 KB payload.

**Failures / dead ends**
The first draft of the opportunity projection renamed the refusal field to
`blocking_reason`. The offline planner reads `reason` when composing its no-action
message, so the run would have recorded an empty explanation — silently, because nothing
asserts the *content* of that string. Keeping the authoritative field name fixed it. The
lesson generalises: a projection that renames is a projection that breaks a consumer you
forgot about.

**What we learned**
The expensive thing was not the payload — it was the payload times the number of turns
that followed it. Re-reading is where an agent's money goes, and it is invisible until
something bills you per token. Measuring the amplification rather than the size changed
what got cut: `list_latent_demand` is a seventh the size of `evaluate_pool_economics` but
is re-sent more often, and the two rank far closer than their byte counts suggest.

The second lesson is where the fix belongs. Context management, truncation, and
summarization all operate *after* the waste exists. Not generating it is cheaper, exact,
and cannot delete the one field the model needed. The framework's tools were built for
long open-ended conversations; a bounded workflow with typed tools should fix this at the
source.

**Architectural finding**
With the results compact, the largest single term in the model's context is now the **tool
schemas: 6,805 bytes re-sent every turn, 62% of what remains**. Twelve tools with careful
docstrings — the same docstrings that make a small model pick the right tool. Trimming
them trades tool-selection quality for tokens, which is a very different bet from dropping
an audit detail, so it was measured and left alone. Logged as Q15.

**Article fodder**
Article 2, and it is the best cost story in the project: a measured 85:1 ratio, a
measurement that contradicted the obvious culprit ranking, a fix at the source rather than
in the framework, and a 46% reduction verified on the real model with the behaviour
unchanged. Also Article 3, for the boundary it defends: the model is given less, not
trusted with more.

**Evidence worth preserving**
Five post-change and two baseline `verify_bedrock.py` outputs, same session and same
environment, showing tool sequence, token counts, and final state. The per-turn context
measurement table above.

**Relevant commits / files**
`services/agent/pool/agent/projection.py` (new),
`services/agent/pool/agent/tools.py`, `services/agent/pool/agent/coordinator.py`,
`services/agent/tests/test_agent_projection.py` (new), `docs/COST_NOTES.md`

### #0021 — [2026-08-16] — The recovery branch, on a real model, with a lock it was not allowed to take
`[AWS]` `[AGENT]` `[HITL]` `[COST]` `[ARTICLE-2]` `[ARTICLE-3]`

**Goal / user intent**
Q14: only the *discovery* path had ever run on Bedrock. Discovery is the forgiving
branch — nothing is committed, nothing can be over-bought, and a wrong tool choice
costs a wasted iteration. Verify one **consequential** branch before considering
AgentCore: a funded pool loses committed demand and the coordinator has to repair it,
then know whether the repaired pool may lock.

**Starting state**
Canonical local implementation complete. Real Bedrock inference verified for discovery
(#0019) and made 46% cheaper by projections (#0020). AgentCore not deployed, no
persistent AWS resource, no Stripe contact.

**Decision**
Verify the **payment-failure recovery branch** — the smallest existing scenario that is
genuinely consequential — and shape it so the two failure modes we care about are
*distinguishable from each other*, which the showcase scenario does not do.

In `services/demo.py` every human answers their Decision Inbox *before* the recovery run,
so at the moment recovery happens there is nothing pending. Lost demand and unanswered
demand are the same number: zero and the shortfall. A coordinator that confused them
would pass. So the verification runs recovery at the more realistic moment — immediately
after the final offer, while two buyers are still deciding:

| | units |
| --- | --- |
| Order priced against whole 12-unit cases | 24 |
| Funded | 18 |
| **Genuinely lost** (one seeded card declined) | **2** |
| **Merely unanswered** (two buyers still deciding) | **4** |

Recruiting 6 instead of 2 overshoots a 24-unit order that fills exactly two cases, which
is the speculative surplus §48 exists to prevent. Locking at all captures money from a
pool two buyers never approved. Both mistakes are *allowed* by the tool surface and
refused only by deterministic code — which is precisely why a real model had to try.

**Implementation** — implemented and tested.

- `pool/scripts/recovery_scenario.py` (new). The scenario builder, an authoritative state
  snapshot, and the lifecycle invariants as pure functions. No environment setup, no model,
  no I/O beyond the injected repository.
- `pool/scripts/verify_recovery_bedrock.py` (new). **(COSTS MONEY.)** Two bounded real-model
  runs. Adds exactly one thing over the shared module: evidence that Bedrock made the
  decisions.
- `tests/test_recovery_lifecycle.py` (new, 18 tests, credential-free). Runs the *same*
  invariant functions against the offline planner.

The split is the point: the semantics are asserted for free on every `make test`, and the
paid script proves a real model reaches the same place. When they disagree, the difference
is the model's judgement — which is the only thing worth paying to observe.

The situation is scripted; the decision is not. Setup is deterministic service calls with
no model involved, and the instruction is **verbatim from the showcase scenario** — it
names no pool, no tool, and no unit count, and it deliberately invites a lock ("then lock
anything that has become viable") so the deterministic rules have to be the thing that
refuses one.

**AWS / external services touched**
`bedrock-runtime:ConverseStream` — **53 real streaming calls across 6 harness runs**
(12 coordinator runs). Model `us.amazon.nova-lite-v1:0`, profile `pool-dev`, `us-east-1`,
non-root IAM user `pool-admin`. **No resource was created**; the ledger stays empty.
AgentCore was not deployed. No Stripe call was made; payments and purchase were the
simulated providers throughout, and no money moved.

**Cost-relevant activity**

| | recovery run | lock run |
| --- | --- | --- |
| Iterations (bound 8) | 4–5 | 3–6 |
| Tool calls (bound 25) | 4–5 | 2–5 |
| Input tokens | 11.3k–14.5k | 7.1k–17.0k |
| Output tokens | 353–713 | 256–568 |
| Wall clock | 3.9–9.2 s | 2.8–5.8 s |

A full harness run is 7–11 ConverseStream calls and ~19k–32k input tokens. Both branches
sit **well inside** the bounds; nothing came close to firing one. Notably the recovery run
is *cheaper* than a discovery run (~19k) despite being the harder decision — it reads a
468-byte work queue instead of evaluating economics across the whole community.

**Agent behavior**
Six harness runs. The recovery phase produced the same opening every time:

```
list_pools_needing_attention → recover_pool → [inspect_pool | lock_pool] → record_no_action
```

Never `recover_pool` first — the instruction names no pool, so the identifier could only
come from the work queue, and it always did.

**Three of six runs attempted the lock and all three were refused**, with the deterministic
reason, having captured nothing:

```json
{"locked": false, "reason": "20/24 units (funded) against the supplier minimum",
 "viability": {"failed": ["supplier_moq", "buyer_decisions_settled", "funding"]}}
```

That is the single most valuable observation here. The model was explicitly invited to lock,
it tried, and the viability engine — not a prompt, not a guardrail sentence — stopped it.
The model then recorded no further action, and the outcome stayed `pool_recovered`: #0016's
fix (`record_no_action` never overwrites work already done) firing under a real model,
in five of six runs where the model called it last.

Recovery itself was identical in all six: shortfall **2**, one replacement (`hh_petrov`,
2 units) auto-authorised by their own Smart Join policy, in-play back to exactly 24, the
two pending decisions untouched, surplus 0. Phase 2, after the two humans answered:
`list_pools_needing_attention → lock_pool` (locked) and, in four runs, `execute_purchase`.
Final state identical every time — 10 captured payments totalling **$861.44**, exactly
`final_economics.all_in_cents`.

**Validation**
Six runs of `verify_recovery_bedrock.py`; **31 assertions per run** covering the chain
(real `BedrockModel`, configured model id, wire-level botocore evidence, bedrock provider
recorded, tokens consumed), the semantics (replaced exactly what was lost, did not
over-recruit, pending decisions not treated as lost, case boundary preserved, economics
unchanged, outcome not overwritten, did not lock, captured nothing, projections faithful),
and the bounds. **Five of six runs passed every assertion.** The sixth is below.

Offline: **490 application tests + 24 infrastructure tests passing**, lint clean, secret
scan clean. 18 of those are new. They were *run* with `HOME` and every AWS variable
stripped **and** `MODEL_PROVIDER=bedrock` deliberately set, and still passed in 0.27 s:
the tests pin `Settings(model_provider="offline", …)` explicitly rather than reading the
environment, so a stray variable cannot steer the suite at a paid model.

A projection check worth naming: `BoundedRun` records the first 180 characters of the exact
string Strands handed the model, so re-projecting the retained authoritative result and
comparing proves the model saw *that result's projection* — not a paraphrase, and not a
number anyone re-derived. It passed on every tool call in every run.

**Failures / dead ends**

1. **The real model invented a pool identifier.** Run 3, phase 2, first turn — with no tool
   result yet in that run — the model opened with
   `recover_pool(pool_id="short_of_demand_pool")`. A *consequential* tool, called with a
   plausible-looking string it made up.

   What happened: `_require_pool` raised `CoordinationError: unknown pool` before anything
   was read or written, Strands returned the error, and the model corrected itself —
   `list_pools_needing_attention → inspect_pool → lock_pool → execute_purchase` — and the
   run finished correctly with the right pool locked and $861.44 captured. Blast radius:
   zero.

   Diagnosed rather than scripted around. Every consequential tool was then checked against
   an invented identifier: all seven refuse before touching anything, and the run's own
   bookkeeping (outcome, created/advanced/recovered ids, decisions created) stays clean, so
   a refused call cannot make a run report work it did not do. `inspect_pool` is the
   deliberate exception — a *read* answers `{"error": "unknown pool"}` instead of raising,
   which is exactly how the model recovers course without burning the run. Nothing asserted
   any of this before; now `test_recovery_lifecycle.py` does, including an end-to-end
   reproduction with a planner that opens with the same invented call.

   The verification still **fails** that run, on `every tool call the model made was
   accepted`. That check was renamed from "every tool call succeeded" because the original
   name credited the wrong party: the refusal is the system working, and the signal is
   about the model's arguments. It was deliberately **not** relaxed. A hallucinated argument
   to a money-adjacent tool is exactly what a verification run should refuse to wave through,
   even when the outcome was fine.

2. **The first version of the grounding check blamed the wrong call.** It looked at the
   first `recover_pool` in the run, which in the reproduction is the rejected one — so a run
   that recovered correctly from an invented id scored as "not grounded". Fixed to use the
   first *accepted* call: a rejected call neither repairs nor grounds anything. Found by the
   new offline test, not by a paid run, which is the arrangement working as intended.

**What we learned**
A scenario that cannot distinguish two failure modes cannot verify that they are
distinguished. The showcase settles every human decision before recovery runs, so "gone"
and "hasn't replied yet" are never both non-zero at the same instant — and the invariant
that took two attempts to get right in #0016 would have passed a real-model check that
never actually tested it. Moving the run three steps earlier in the lifecycle cost nothing
and made the test real.

The second lesson is about where safety lives. The model was told to lock, tried to lock,
and could not — and separately reached for an identifier that did not exist. Neither is a
prompting failure to be fixed with a better sentence. Both were caught by deterministic
code that checks stored facts before acting, which is the AGENTS.md §5 boundary paying for
itself on the branch where money is involved.

**Article fodder**
Article 3 primarily, and it now has its best concrete scene: an autonomous agent
*attempting* a consequential action and being refused by deterministic rules, with the
refusal reason quotable verbatim. Also Article 2, for the shared-invariant arrangement
(one set of assertions, run free offline and paid on the real model) and for the invented
identifier, which is the most transferable agent-safety finding in the project: give a
consequential tool a name-shaped argument and a small model will eventually guess one.

**Evidence worth preserving**
Six `verify_recovery_bedrock.py` outputs, including run 3 with its rejected call and its
single FAIL. The lock refusal JSON above. The before/after state blocks, which read as a
clean narrative for the demo: 18 funded / 2 lost / 4 undecided → repaired to 24 in play →
refused the lock → humans answer → locked and captured $861.44.

**Relevant commits / files**
`services/agent/pool/scripts/recovery_scenario.py` (new),
`services/agent/pool/scripts/verify_recovery_bedrock.py` (new),
`services/agent/tests/test_recovery_lifecycle.py` (new), `Makefile`

### #0022 — [2026-08-16] — The deployment CLI had been replaced, and a refusal you could not see
`[AWS]` `[ARCHITECTURE]` `[COST]` `[AGENT]` `[ARTICLE-2]`

**Goal / user intent**
Prepare an Amazon Bedrock AgentCore deployment and take it as far as a dry run, without
provisioning anything. Then harden three things the dry run exposed before asking for
approval to bootstrap CDK and deploy for real.

**Starting state**
The local implementation was complete and Bedrock-verified (#0019–#0021). AgentCore had
never been deployed and no AWS resource had ever been created. `Makefile`,
`docs/PILOT_READINESS.md` and the entrypoint docstring all documented the deployment as
`agentcore configure --entrypoint agentcore_app.py && agentcore launch`.

**Decision**
Adapt to the current CLI rather than preserve the repository's assumption, and keep the
existing coordinator and entrypoint exactly as they are.

**Why**
`bedrock-agentcore-starter-toolkit` — the CLI every one of those commands belongs to — is
now marked **legacy**. AWS ships `@aws/agentcore` (npm) instead, which binds the same
`agentcore` command name, so having both installed is itself a documented hazard. The
commands in this repository would not have failed with "deprecated"; they would have run
whichever CLI happened to be on `PATH`.

The new CLI is CDK-based and wants a project directory. `agentcore create` is the only
official way to make one, and it scaffolds a *replacement* — its own `agentcore.json`,
its own `aws-targets.json`, and an `app/<AgentName>/main.py` agent next to the real
coordinator. So the project config was hand-written against the published schema instead,
pointing `codeLocation` at `services/agent/` so the entrypoint deploys where it already
lives. `CodeZip` over `Container`: no Dockerfile, no ECR repository, no CodeBuild project,
and no local container runtime — the smaller and cheaper of the two (§3.5, §3.7).

**Implementation**
Implemented and tested; **not deployed**.

1. **`agentcore/agentcore.json`, `agentcore/aws-targets.json`** (new, committed) — one
   runtime, `PYTHON_3_13`, `PUBLIC`, `HTTP`, `AWS_IAM` inbound auth, fifteen environment
   variables carrying the model id and every bound.
2. **`agentcore_app.py` — unchanged in substance.** The runtime HTTP contract did not
   move: `BedrockAgentCoreApp`, `@app.entrypoint`, `POST /invocations`, `GET /ping`. The
   only edits are the docstring and the tool-call reporting below.
3. **`services/agent/pyproject.toml`** — `bedrock-agentcore` and
   `aws-opentelemetry-distro` moved into runtime dependencies. CodeZip installs the image
   straight from this file, and the synthesized start command is
   `["opentelemetry-instrument", "agentcore_app.py"]` — so a missing OTel distro fails the
   container at start, not merely its tracing.
4. **`scripts/agentcore_cdk_init.sh`** (new) + `make agentcore-cdk` — rebuilds the
   generated `agentcore/cdk/` from the installed CLI's own bundled assets. Refuses to
   overwrite without `--force`, warns when the installed CLI is not the verified version.
5. **Tool-call reporting** — the entrypoint returned `[t.name for t in run.tool_calls]`.
   It now returns `{"name", "ok", "summary"}` per call, the same shape the API already
   used for run detail. Output only: no tool description, schema, prompt, or domain
   semantics changed.
6. **`scripts/secret_scan.sh`** — the AgentCore staging cache is pruned by exact rooted
   path, plus `scripts/secret_scan_selftest.sh` (new) to prove the prune is that narrow.

**AWS / external services touched**
`sts:GetCallerIdentity`, `cloudformation:DescribeStacks`/`ListStacks`,
`bedrock-agentcore-control:ListAgentRuntimes`, `s3:ListBuckets`,
`ecr:DescribeRepositories`, `iam:ListRoles`, `codebuild:ListProjects` — all read-only,
all used to confirm the account was and stayed empty.

**No resource was created.** No CDK bootstrap, no runtime, no bucket, no role. The ledger
stays empty and the account still holds nothing but three AWS service-linked roles. No
Stripe call was made; no Stripe-related resource appears anywhere in the synthesized
template.

**Cost-relevant activity**
No model tokens were spent. Every local verification ran on the offline planner, because
the Bedrock leg was already verified in #0019–#0021 and re-running it would have proved
nothing new.

Two cost decisions are baked into the config. `lifecycleConfiguration` sets
`idleRuntimeSessionTimeout: 60` and `maxLifetime: 300` against API defaults of **900 s and
8 h**. AgentCore Runtime bills memory per second across a session's life and CPU only
while processing, so the default would have billed a fifteen-minute idle memory tail after
every invocation of a workflow already bounded at 120 s — exactly the "long-running
AgentCore sessions" risk in §3.4.

Two costs the first real deployment will introduce, both recorded now so they are not
discovered later: the CDK bootstrap creates a persistent S3 staging bucket that
accumulates ~44 MB per deployed artifact version, and the runtime's CloudWatch log group
is created by the service outside the stack with **no retention policy** — unlike
`PoolStack`, which caps everything at 14 days.

**Agent behavior**
Unchanged by design, and that is the point of item 5. A run still selects tools, still
terminates on a deterministic condition, still refuses invented identifiers. What changed
is that the refusal is now visible from outside the runtime.

**Validation**
- `agentcore validate` → `Valid`. `agentcore deploy --dry-run` reaches
  `Synthesize CloudFormation` and stops at `Check bootstrap status`, which is a hard gate
  before the plan summary — clearing it needs `--yes`, which auto-bootstraps, so the
  dry run cannot print its own plan on an unbootstrapped account. The synthesized template
  is the authoritative answer instead: **4 resources** — one
  `AWS::BedrockAgentCore::Runtime`, one execution role, one inline policy, CDK metadata.
- The execution role's inline policy is Bedrock invoke on inference profiles and
  foundation models, CloudWatch Logs scoped to `/aws/bedrock-agentcore/runtimes/*`, and
  X-Ray. No DynamoDB, S3, or Location access — correct for this configuration.
- **The built artifact was inspected, not assumed**: 43.7 MB zipped / 107.5 MB unpacked
  against a 250 MB limit, containing `pool/`, the entrypoint, Strands, and OTel — and no
  `.env`, `.venv`, `.git`, or AWS config.
- **`agentcore/cdk/` was deleted and rebuilt from scratch** to prove a fresh clone works:
  the dry run failed exactly as documented, `make agentcore-cdk` reconstructed it, and
  validation and synthesis both succeeded again. The resource set was byte-identical apart
  from the code asset hash, which moved because the entrypoint changed.
- **499 application tests + 24 infrastructure tests**, lint clean, typecheck and web build
  clean. Nine of those tests are new and credential-free.
- **The deployed start command was run locally** — `opentelemetry-instrument` wrapping the
  entrypoint — serving `/ping` and `/invocations`, with the AgentCore session id threaded
  through to the SDK's own logs.
- `make secret-scan-selftest` plants fake AWS and Stripe credentials in seven locations
  and asserts each is caught, including one inside a `.cache` directory elsewhere in the
  repository, then asserts only `agentcore/.cache/` is exempt.

**Failures / dead ends**
1. **The first dry run failed on a missing `agentcore/cdk/`**, and the CLI's advice —
   "Run 'agentcore create' first" — is the one command that would have overwritten Pool.
   Resolved by taking the CLI's own assets, which turned out to contain no template
   placeholders at all, so copying them is deterministic rather than an approximation.
2. **The second failed on `sh: tsc: command not found`.** The CLI's "Sync CDK
   dependencies" step completed in 2 ms without installing anything: it expects
   `node_modules` to already exist, because `create` normally runs `npm install`.
3. **The 120 MB staging cache broke `make secret-scan`** — on botocore's own
   `AKIA…EXAMPLE` documentation and the PEM header constant inside `cryptography`. The
   first fix, `--exclude-dir=.cache`, was too broad: `--exclude-dir` matches a basename, so
   it would have blinded the scanner to every `.cache` directory in the repository. Now
   pruned by exact rooted path, at a cost of about half a second.

**What we learned**
Two things, and the second is the more useful.

A deployment path that has never been executed can rot without anyone touching it. The
commands in this repository were correct when written and had since been replaced by a
different tool with the same name. Nothing failed, because nothing had ever run.

And **a safety property that cannot be observed from outside the system is not yet a
safety property you can demonstrate.** #0021 proved that an invented pool identifier is
refused before any state moves, and regression tests pin it. But the hosted entrypoint
reported only tool *names* — so a `recover_pool` rejected for an invented id and a
`recover_pool` that repaired a pool produced identical output. With `POOL_REPOSITORY=memory`
the run record dies with the microVM, so there would have been nothing to query afterwards
either. The guard was real; the evidence was not reaching anyone.

**Article fodder**
Article 2, strongly. Three findings that transfer: a legacy CLI that shares its successor's
command name; a dry run that cannot complete without a provisioning step, which is worth
naming honestly rather than papering over; and the observability lesson above, which is
really an argument about what "verified" means once code is somewhere you cannot reach.

**Evidence worth preserving**
The synthesized `AgentCore-Pool-default.template.json` (four resources, and the execution
role's policy). The `make agentcore-cdk` reconstruction transcript. The
`make secret-scan-selftest` output — it reads as a table of what the scanner does and does
not look at. And a `/invocations` response showing `ok` and `summary` per tool call.

**Relevant commits / files**
`agentcore/agentcore.json` (new), `agentcore/aws-targets.json` (new),
`scripts/agentcore_cdk_init.sh` (new), `scripts/secret_scan_selftest.sh` (new),
`services/agent/tests/test_agentcore_entrypoint.py` (new),
`services/agent/agentcore_app.py`, `services/agent/pyproject.toml`,
`scripts/secret_scan.sh`, `Makefile`, `.gitignore`, `README.md`,
`docs/PILOT_READINESS.md`, `docs/ARTICLE_NOTES.md`
