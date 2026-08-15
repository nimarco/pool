# AGENTS.md — Operating Manual for Coding Agents on Pool

This file is the durable operating manual for any AI coding agent (Claude, Codex, or otherwise)
working in this repository. It assumes **no chat history**. If you are an agent starting fresh,
read this file top to bottom before making changes.

**How to use this file**

- Sections 1–2 tell you *what we are building and why*.
- Section 3 (AWS Cost Safety) and Section 4 (Security & Privacy) are **hard constraints**. Treat
  them as blocking.
- Sections 5–9 tell you *how the system must be shaped*.
- Section 10 and the closing checklist tell you *what you owe the record* when you finish.

**Precedence when instructions conflict**

1. An explicit instruction from the human in the current conversation wins for that task.
2. Except: if a request would violate Section 3 (cost) or Section 4 (security/privacy), do not
   silently comply. State the specific rule, state the risk, and get an explicit confirmation
   first. "The user asked me to" is not a sufficient record for burning AWS credits or committing
   a secret.
3. Otherwise, this file governs.

**Status vocabulary — use these words precisely, everywhere**

| Term | Means |
| --- | --- |
| **Planned** | Decided, not written. |
| **Implemented** | Code exists and is runnable. Says nothing about correctness. |
| **Tested** | Verified by an actual executed test, fixture, or reproduced scenario. |
| **Deployed** | Actually running on AWS, verified by an observed response or trace. |

Never use a stronger word than the evidence supports. This vocabulary is shared with
`BUILD_HISTORY.md` and is the backbone of an honest record.

---

## 1. Project mission

### What Pool does

Pool is an **autonomous neighborhood group-buying coordinator**.

Households declare recurring purchasing needs and preferences — the things they buy anyway, at
roughly the cadence they buy them. Pool then works in the background to find **overlapping latent
demand** among nearby households, evaluate whether a bulk purchase is actually worthwhile,
determine feasible allocations, evaluate pickup and logistics options, and assemble a candidate
buying pool. It contacts humans only when a decision genuinely requires one.

### Who it is for

Neighborhoods and small local groups: residential blocks, apartment buildings, community
organizations, food banks, schools, libraries, small nonprofits. The target user is a household
that would benefit from bulk pricing but will never do the organizing work required to get it.
This maps to the hackathon's **Good Neighbor Agents** track: the system helps a *group* of people,
not a single user.

### Why this is an agent problem, not a marketplace or CRUD app

A marketplace waits for a human to start something. A CRUD app stores what humans typed. Group
buying fails in the real world not because the software is missing, but because the *coordination
labor* is unpaid, tedious, and lands on one exhausted volunteer: recruiting neighbors, comparing
quantities, chasing non-responders, re-planning when someone drops out, arranging pickup.

The work that kills neighborhood group buying is exactly the work that suits an agent:

- **The opportunity is latent, not stated.** Nobody has said "let's buy 40 kg of rice together."
  Five households have separately said they buy rice monthly. Discovering that a viable group
  *could* exist requires searching a space nobody has asked about.
- **Feasibility is multi-constraint and shifting.** Price breaks, minimum quantities, budget
  ceilings, substitution tolerance, timing windows, pickup capacity, and who is willing to drive.
- **Failure is normal and recovery is bespoke.** Someone drops out at 80% commitment. What now
  depends on the specific pool, the specific shortfall, and who could plausibly absorb it.
- **Most decisions should not reach a human at all,** and the ones that do should arrive already
  worked out.

### The core product distinction

**The user should not have to create the buying group. Pool should discover that a useful group
can exist.**

Encode this as a design constraint, not a tagline. Concretely, it means:

- A "create a group and invite your neighbors" flow is a **product failure**, not a feature.
- The primary user input is a standing declaration of need and constraints, not an organizing act.
- If a feature requires a human to notice the opportunity first, we have built the wrong thing.
- Success looks like a household being *offered* a worked-out, feasible pool they never asked to
  organize.

### Behavioral posture

Pool is **quiet by default**. It runs in the background and surfaces only decisions that are
useful to the human receiving them. Every notification costs the user attention, and attention is
the resource the product exists to conserve. A Pool that pings you six times to assemble one order
has reproduced the problem it was built to remove.

Bias toward: fewer messages, later messages, messages that arrive pre-resolved and answerable in
one tap.

### Build it like a real product

This is a hackathon submission, but the architecture must be a plausible real system, not a demo
harness with a UI painted on. Concretely:

- Real workflows execute. See Section 8 — no fake demo logic.
- Synthetic *data* is fine and expected. Synthetic *behavior* is not.
- Shortcuts taken for scope reasons must be labeled as shortcuts in `BUILD_HISTORY.md`, so we can
  speak accurately about them in the demo and the articles.

### Provisional vocabulary

Reconcile these with the code once the domain model lands; update this table rather than letting
it drift.

| Term | Meaning |
| --- | --- |
| **Pool** (capitalized) | The product/system itself. |
| **pool** / buying pool | One concrete group purchase instance. |
| **household** | The account unit. May be one person or a family. |
| **need declaration** | A standing statement of a recurring need plus constraints. |
| **latent demand** | Declared need not yet attached to any pool. |
| **opportunity** | A candidate bulk purchase the system believes may be worthwhile. |
| **allocation** | Who gets what quantity, at what cost, in a given pool. |
| **commitment** | A household's binding agreement to an allocation. |
| **Smart Join** | Preauthorization policy letting a household join qualifying pools without a prompt. |

---

## 2. Hackathon-aware engineering

### Verified competition facts

Verified against <https://agentsforhumans.devpost.com/> on **2026-08-15**. Anything below is a
snapshot. **Re-verify against the official source before relying on it for a submission decision**,
and do not invent requirements or scoring rules that are not recorded here or on that page.

- **Deadline: 2026-09-14, 5:00pm PDT.** AWS promotional credit request form closed earlier —
  2026-09-11, 12:00pm PT.
- **Strands Agents SDK is mandatory.** It is a stage-one pass/fail viability gate.
- **Projects must be newly created during the submission period.** Pre-existing projects are not
  eligible; incorporated prior code must be disclosed. Practical consequence: this repository's
  history is part of the eligibility story — do not import a prior codebase without disclosure.
- Public repository, **MIT or Apache license visible**, README, and an **architecture diagram**.
- **Demo video, 5 minutes maximum**, covering the problem, the intended users, and why it matters.
- AWS Builder ID required to submit.
- Judging: five criteria, **equally weighted at 20% each** — Technological Implementation, Design,
  Potential Impact, Creativity & Originality, Presentation. A published builder.aws.com post is
  worth up to +0.6 bonus.
- Amazon Bedrock AgentCore deployment is **optional but favorable**. A live demo link strengthens
  Technological Implementation.

### What that implies for engineering

- **Strands must be load-bearing.** The core agent loop — tool selection, escalation decisions,
  recovery reasoning — should run through Strands. A thin wrapper around code that would work
  identically without it does not satisfy the spirit or the gate.
- **Treat AgentCore deployment as an important target,** and a **public working demo** likewise.
  Schedule them as real milestones, not end-of-project hopes.
- **The architecture must be explainable and observable.** If we cannot narrate why Pool created a
  given opportunity, we cannot demo it or write about it.
- **Use AWS services where they genuinely improve the system.** Do not add services to increase
  the logo count on the architecture diagram. An architecture that is small and justified beats one
  that is broad and decorative — and it is far cheaper (Section 3).
- **Keep agent reasoning and deterministic application logic cleanly separated** (Section 5). This
  is both an engineering requirement and the most interesting thing we will have to write about.
- **Leave evidence behind.** Decisions must be reconstructable later for the README, the
  architecture diagram, the demo script, and three Builder Center articles. Capture it as it
  happens (Section 10).

Note the scoring shape: Design and Presentation together are 40%. Engineering effort that never
becomes visible or explicable is under-rewarded. This is not permission to fake behavior — it is a
reason to make real behavior legible.

---

## 3. AWS COST SAFETY — READ THIS BEFORE TOUCHING AWS

> **This project runs on a student's promotional AWS credits.** Exhausting them ends the project.
> Cost safety outranks convenience, elegance, and speed of iteration. When a cheap path and a
> convenient path conflict, take the cheap path and note it.
>
> **If you discover an architecture choice that could unexpectedly consume substantial credit,
> stop and explain it before proceeding. We would rather lose five minutes asking than burn the
> credits.**

### 3.1 Never create uncontrolled loops

- Never implement an agent loop that can run indefinitely.
- **Every autonomous loop has a hard maximum iteration count.** No exceptions, including loops you
  are "sure" will terminate.
- **Every retry mechanism has a hard retry limit.** Use exponential backoff where appropriate.
- Every workflow has a **defined terminal state**, reached by a deterministic condition wherever
  possible — not by the model deciding it feels finished.
- **Detect repeated identical tool calls and repeated states, and terminate.** A model calling the
  same paid tool with the same arguments is a bug, not deliberation.
- Never let an LLM call a paid tool repeatedly until it is satisfied.
- Expose loop and retry limits as **configuration with safe defaults**, so they can be tightened
  without a code change.

Suggested starting defaults — tune deliberately and record the change:

| Bound | Default | Notes |
| --- | --- | --- |
| `MAX_AGENT_ITERATIONS` | 8 | Per workflow invocation. |
| `MAX_TOOL_RETRIES` | 3 | With exponential backoff. |
| `MAX_TOOL_CALLS_PER_RUN` | 25 | Global circuit breaker across all tools. |
| `MAX_DUPLICATE_TOOL_CALLS` | 2 | Identical name+args → terminate as a loop fault. |
| `WORKFLOW_TIMEOUT_SECONDS` | 120 | Wall-clock kill switch. |

A run that hits a bound must terminate loudly — a recorded loop-fault outcome, not a silent
truncation that looks like a normal result.

### 3.2 Never create uncontrolled polling

- Do not poll AWS services continuously.
- No second-by-second or minute-by-minute polling for development convenience.
- **Prefer event-driven behavior** over scheduled scanning.
- For hackathon simulation, **manual invocation or an intentionally slow schedule** beats
  background traffic. A demo can trigger a cycle on a button press.
- **Scheduled jobs default to disabled** unless actively being tested. Gate every schedule behind a
  single, obvious kill switch (e.g. `SCHEDULES_ENABLED=false` by default) so nothing recurring can
  be enabled by accident or by a partial deploy.
- If a recurring EventBridge schedule is created for testing: lowest practical frequency, easy to
  disable, easy to destroy, and **recorded in the resource ledger in `BUILD_HISTORY.md`**.
- **Do not leave test schedules running after they are needed.** A forgotten schedule spends
  credits while nobody is at the keyboard — the single most likely way this project dies.

### 3.3 Bound AI usage

- Every model-driven workflow has explicit boundaries before it is allowed to run.
- Avoid unnecessarily large prompts and context windows.
- **Do not resend enormous histories when compact structured state will do.** Pass the agent a
  summarized, structured view of the world, not a transcript.
- Do not use a powerful, expensive model where a cheaper model — or a deterministic function —
  suffices. Model choice is an explicit decision, and changing it deserves a `BUILD_HISTORY` entry.
- **Use deterministic code** for calculations, constraint matching, financial math, database
  invariants, and validation. **Use AI** for reasoning, ambiguity resolution, prioritization, and
  tool selection. See Section 5.
- Do not make multiple model calls where one call can safely do the same reasoning.
- **Do not generate fake "thinking" steps** to make the architecture look sophisticated. That is
  both a cost bug and a form of the dishonesty banned in Section 8.
- **Track token and request usage** where supported, so expensive behavior is visible rather than
  discovered on a bill.

### 3.4 Bound paid tools

Be especially careful with anything that performs:

- web search
- browser automation
- repeated model inference
- long-running AgentCore sessions
- large observability or log ingestion
- high-frequency routing or geocoding
- high-frequency Lambda or EventBridge invocation

**Do not add AgentCore Browser, AgentCore Web Search, or any other nontrivial usage-based service
without a concrete product need** documented first.

For the initial product, **synthetic supplier and product data is preferable** to live web
scraping. Live sourcing is brittle, expensive, and — critically — *not the interesting part*. The
demonstrable claim of this project is autonomous coordination, not price scraping. If live sourcing
is added later, it must be a deliberate decision with its own entry.

### 3.5 Infrastructure approval boundary

Before creating any AWS resource or architecture component that could incur meaningful recurring
cost:

1. Determine whether it is actually needed **now**.
2. Document why, in `BUILD_HISTORY.md`.
3. Estimate or characterize the cost model if practical.
4. Prefer serverless / pay-per-use.
5. Prefer infrastructure that is easy to destroy.
6. **Explicitly call out anything that can keep accruing cost while nobody is developing.**

**Do not silently provision expensive infrastructure.** If you are uncertain whether something can
generate material charges, **stop and surface the uncertainty** rather than guessing. Uncertainty
is a reason to ask, not a reason to proceed carefully.

### 3.6 Safe development defaults

**Prefer:** local tests · mocked AWS services · synthetic datasets · deterministic fixtures ·
explicit manual test triggers · low-volume integration tests · one-shot agent executions ·
serverless resources · bounded test datasets.

**Over:** permanent compute instances · high-frequency schedules · autonomous crawling · giant
inference test suites · uncontrolled stress tests · persistent unattended test agents.

When testing agent *logic*, use deterministic fixtures and mocked tool responses. Only make real
model calls when actual AWS integration is the thing under test — and make those calls intentional
and bounded.

### 3.7 No "just in case" infrastructure

Do not provision services because we might use them later. **Build the smallest real architecture
the current milestone needs.** Unused infrastructure is pure cost, extra attack surface, and a
misleading architecture diagram.

### 3.8 Cleanup

Every temporary AWS resource must be **recorded in the resource ledger at the top of
`BUILD_HISTORY.md`** when created. Each one must then either:

- be destroyed after testing (record the destruction), **or**
- carry a documented reason for remaining.

Do not leave forgotten experimental infrastructure running. Before ending a work session that
touched AWS, re-read the ledger and confirm every entry is either destroyed or deliberate.

### 3.9 Rules that bind *you*, the coding agent, right now

Do not:

- start an autonomous cloud agent and leave it running
- create recurring high-frequency jobs without explicit need
- repeatedly invoke Bedrock to test trivial UI changes
- run load tests against paid APIs without approval
- crawl websites repeatedly
- use AWS Browser/Search in uncontrolled loops
- create persistent compute because it is easier than designing a serverless flow
- create duplicate cloud resources while debugging and leave them behind
- invoke an LLM on every frontend render or page reload
- retry paid operations indefinitely
- create an agent that can recursively invoke itself
- let one failure trigger an unbounded cascade of model calls
- create expensive infrastructure "for later"

---

## 4. Security, credentials, and privacy

### Credentials

- **Never commit AWS credentials.** Not in code, not in config, not in tests, not in fixtures, not
  "temporarily."
- Never commit access keys, secret keys, session tokens, API keys, passwords, or private URLs that
  embed credentials.
- **`.env` files containing secrets must never enter version control.** Keep an `.env.example` with
  key names and empty values instead.
- Prefer **AWS-native identity and role mechanisms** (IAM roles, short-lived credentials) over
  long-lived static keys.
- **Never print full secrets into logs**, traces, or error messages. Redact to a short prefix at
  most.
- Redact sensitive values from screenshots, traces, logs, `BUILD_HISTORY.md`, the README, and the
  articles. Assume every artifact in this repository is public — because the submission requires
  the repository to be public.
- If a secret is ever committed or exposed, treat it as compromised: rotate it, then record the
  incident in `BUILD_HISTORY.md` **without the secret**.

### Personal and location privacy

Pool is a neighborhood product, so the default data set is *where people live*. Treat that as
sensitive by default.

- **Exact home addresses are sensitive data.** Do not expose exact residential locations
  unnecessarily — in the UI, in logs, in traces, in model context, or in demo material.
- **Public maps and any shared view should use approximate or aggregated neighborhood-level
  visualization** until an exact location is genuinely required (e.g. a confirmed pickup between
  parties who have agreed to it).
- Minimize PII reaching the model: the agent should reason over **coarse location and derived
  distances** supplied by deterministic tools, not over raw addresses. Precise location should be
  retrievable only through a narrow, authorized tool at the moment it is actually needed.
- Demo and article material must use synthetic households. Never use real neighbors' data.

### Authorization boundaries for tools

- **Consequential tools require authorization boundaries.** A tool that spends money, commits a
  household, or reveals an address is not the same kind of object as a tool that reads a catalog.
- **Never give the LLM unrestricted database mutation, arbitrary shell access, or broad cloud
  permissions when narrower tools can accomplish the task.** Expose specific, typed, minimal
  operations — not a generic `execute_sql` or `run_command` escape hatch.
- Every tool should be able to answer: what can this do at worst, if the model calls it with the
  most damaging plausible arguments?

---

## 5. Agent architecture principles

### AI decides; deterministic tools verify and execute

This is the central architectural rule of the project.

| The model **may decide** | Deterministic code **must determine** |
| --- | --- |
| what information it needs next | monetary calculations |
| which safe tool to call | quantities |
| whether an opportunity deserves investigation | discount percentages |
| whether a situation requires escalation | inventory and allocation totals |
| how to recover from an unexpected but bounded scenario | commitment state |
| how to prioritize among competing options | whether thresholds mathematically pass |
| how to phrase a message to a human | transactional database writes |
| when to stop and ask | authorization decisions |
| | route metrics returned by routing services |
| | validation and invariants |

**The agent must never invent a value from the right-hand column.** If a number appears in a
message to a human, it came from a deterministic tool. If the model needs a total, it calls a tool
that computes the total. A model-authored number that looks right is the worst failure mode this
system has, because it is invisible until someone is out of pocket.

Practical enforcement: tools return structured values, and the values that reach humans or the
database are the tool's, not the model's paraphrase of it. Where feasible, validate outbound
figures against their source before sending.

### Human-in-the-loop

Consequential actions have **explicit authorization semantics**. The autonomy policy — the eventual
Smart Join — must be **explicit and machine-verifiable**, evaluated by deterministic code against
a stored policy. It must not be an informal judgment the model makes in prose.

**Ordinarily require human approval** (unless specifically preauthorized):

- committing money
- increasing a budget
- accepting a materially different substitute
- volunteering a private residence as a pickup point
- accepting materially worse terms

**May proceed autonomously** (lower risk):

- evaluating compatible demand
- comparing offers
- calculating possible routes
- forming a candidate pool
- sending ordinary status notifications
- looking for a replacement participant
- rearranging internal planning state

When in doubt about which list an action belongs to, treat it as consequential and ask. Also
prefer the *quietest sufficient* escalation: recovering a dropout by asking one household with
matching latent demand is better than broadcasting to everyone in the pool.

---

## 6. Source of truth

**Application and database state is authoritative.** Agent memory is not.

Agent memory is **never** authoritative for:

- balances
- commitments
- quantities
- inventory
- pool membership
- deadlines
- payments
- permissions

AgentCore Memory (if used) is appropriate for:

- household preferences
- interaction context
- learned tendencies (e.g. this household reliably declines substitutions)
- durable context that improves reasoning quality

**Memory must not silently shadow transactional state.** If memory and the database disagree, the
database wins, and the disagreement is a bug worth an entry. Never write a commitment, a
quantity, or a permission to memory and treat it as recorded.

---

## 7. Development discipline

For every meaningful change:

1. **Inspect the existing architecture** before making major changes.
2. **Understand the requested change** — including what is deliberately out of scope.
3. **Make the smallest coherent implementation** that actually does the job.
4. **Test it.**
5. **Inspect failures instead of papering over them.** A silenced exception is a deferred outage.
6. **Avoid broad unrelated refactors.** Note them for later instead.
7. **Keep the repository runnable.** Never leave `main` in a broken state.
8. **Preserve backward compatibility** unless the change is intentionally breaking — and say so.
9. **Update documentation when the architecture changes**, including this file.
10. **Update `BUILD_HISTORY.md` after meaningful work** (see Section 10 and the closing checklist).

### Do not declare something working merely because code was written

"Implemented" is not "tested" and neither is "deployed" (see the status vocabulary at the top).
Acceptable evidence:

- unit or integration tests that were actually executed
- real API responses
- real AgentCore traces
- verified deployment
- screenshots
- deterministic fixture results

If you did not run it, say you did not run it. An honest "implemented, untested" is useful. A
false "working" costs hours later and poisons the record we are writing articles from.

---

## 8. No fake demo logic

**Do not implement UI animations or hardcoded agent decisions that imply the agent did work it did
not do.**

- **Synthetic data is acceptable** — synthetic households, synthetic suppliers, synthetic catalogs.
- **Scripted input scenarios are acceptable** — a seeded situation designed to trigger a behavior.
- **Fabricated system behavior is not acceptable.**

If the demo shows Pool recovering from a dropout, the recovery workflow must actually execute:
real detection, real re-planning, real allocation update, real notification decision. A progress
animation with a `setTimeout` and a canned result is a lie told to judges and readers.

If any part of a demo is simulated, **label clearly what is simulated and what is real** — in the
UI where practical, and always in `BUILD_HISTORY.md` and the demo script. This protects us: we can
speak confidently about what is genuine precisely because we tracked what was not.

---

## 9. Observability

Design so we can later answer:

- Why did Pool create this buying opportunity?
- Which tools did the agent call, in what order, with what arguments?
- Which values came from deterministic tools rather than the model?
- Where did human approval occur, and what was approved?
- How many iterations and model calls occurred?
- How long did the workflow take?
- Why did it terminate — success, bound hit, or error?
- How much paid AI and tool activity was involved?

These are the same questions the demo, the architecture diagram, and Article 2 need answered, so
observability work is never overhead — it is source material.

Avoid logging private information unnecessarily (Section 4). Prefer structured, queryable records
over prose logs, and prefer logging identifiers over payloads.

---

## 10. Documentation and article preservation

We will write three AWS Builder Center articles, expected to center on:

1. **Article 1** — turning neighborhood group buying into an autonomous-agent problem
2. **Article 2** — building Pool with Strands, Bedrock, AgentCore, and AWS
3. **Article 3** — deciding when an autonomous agent should act versus ask a human

After meaningful work, preserve evidence of: important product decisions · important architecture
decisions · alternatives considered · why an approach changed · bugs encountered · surprising AWS
behavior · limitations · cost considerations · agent safety decisions · interesting traces ·
screenshots worth capturing · real lessons learned · failed attempts · performance observations.

**Do not fabricate a development journey later. Capture it while it happens.** A reconstructed
narrative written the week before the deadline will be generic, and it will be partly false.

### Working with AI assistance, honestly

This project is built with heavy AI coding assistance, and the documentation should not pretend
otherwise.

- **Do not write fake first-person narratives** implying a human hand-typed code that an AI agent
  produced.
- **Equally, do not reduce the history to "Claude implemented X."** That is neither interesting nor
  informative.
- The record should focus on: **what problem we were solving · what decisions were made · what
  implementation resulted · what failed · what was learned · what was verified.** Those are
  authorship-neutral and they are the actual engineering content.
- **AI assistance does not transfer responsibility.** Whoever ships the result validated it.

---

## Closing checklist — run this at the end of every meaningful task

1. **Does the repository still run?**
2. **Did I verify, or only write code?** Use the status vocabulary honestly.
3. **Did I create any AWS resource?** If yes: is it in the ledger in `BUILD_HISTORY.md`, and is it
   destroyed or deliberately retained?
4. **Did I create anything recurring?** Schedules, retries, background jobs — bounded and disabled
   by default?
5. **Any secrets, keys, or real addresses in code, logs, fixtures, or screenshots?**
6. **Did documentation drift?** If the architecture changed, update this file too.
7. **The history question:** *Did this work produce anything that would matter when explaining how
   Pool was designed, built, debugged, secured, deployed, or made cost-efficient?* If yes, update
   `BUILD_HISTORY.md` **in the same change**.

Do not create noisy entries after every tiny edit.

**Worth an entry:** first working Strands loop · deciding what state belongs in DynamoDB vs agent
memory · first AgentCore deployment · implementing bounded-loop protections · first background
EventBridge execution · implementing Smart Join · adding human approval · implementing dropout
recovery · switching models for cost or quality · first real routing integration · fixing an
infinite or repeated tool-call bug · discovering an AWS limitation · major frontend UX redesign ·
first complete end-to-end pool · a deployment incident and its fix.

**Not worth an entry:** renaming a variable · fixing a typo · running a formatter · moving a button
four pixels.
