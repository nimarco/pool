# Architecture

What is actually built. Anything not implemented is in the clearly-marked future section
at the end, or in `PILOT_READINESS.md` — never on the diagram.

---

## The shape

```
                    ┌──────────────────────────────────────────┐
   browser ────────▶│  FastAPI  (uvicorn local · Lambda cloud)  │
                    └───────────────────┬──────────────────────┘
                                        │
                          ┌─────────────▼─────────────┐
                          │      services/            │  orchestration:
                          │  coordination · hosting   │  everything the agent
                          │  payments · fulfillment   │  can *do* to the world
                          │  communication · demo     │
                          └─────────────┬─────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
      ┌───────▼────────┐      ┌─────────▼─────────┐      ┌────────▼────────┐
      │    domain/     │      │     adapters/     │      │     agent/      │
      │  no I/O at all │      │  the outside world│      │  Strands loop   │
      │                │      │                   │      │                 │
      │ economics      │      │ repository        │      │ coordinator     │
      │ viability      │      │ routing           │      │ tools (×12)     │
      │ policy         │      │ payments          │      │ bounds          │
      │ hosting        │      │ purchase          │      │ offline planner │
      │ matching       │      │ sourcing          │      └─────────────────┘
      │ timing         │      │ verification      │
      │ substitution   │      └───────────────────┘
      │ pickup · money │
      │ state          │
      └────────────────┘
```

The layering is the point, and it is one rule: **`domain/` performs no I/O and imports no
adapter.** Everything that must be *correct* — cents, quantities, package maths, policy
verdicts, viability — is a pure function of its inputs. That is why the whole domain layer
is testable without a fixture, and why swapping in DynamoDB, Bedrock, or Stripe changes
nothing about what a price is.

The deployed discovery request and its proof make one round trip:

```text
browser → Lambda → AgentCore Runtime → Strands + Bedrock → typed Pool tools
        → deterministic services → DynamoDB → Lambda readback → browser
```

The final arrow is load-bearing: the UI displays the stored run and pool relationship,
not a model-authored claim about what happened.

---

## AI decides what to do. Deterministic code determines what is true.

| The model may decide | Deterministic code determines |
| --- | --- |
| which latent demand deserves investigation | cents, quantities, package maths |
| whether to search or refresh supplier offers | MOQ, allocations, offer freshness |
| whether a candidate pool is worth forming | timing eligibility, product compatibility |
| whether to recruit a host | host eligibility, ranking, compensation |
| which recovery strategy to attempt | buyer landed price, platform fee, funding state |
| whether to surface a human decision | pickup-credential validity, state transitions |
| when there is nothing worth doing | Smart Join verdicts, final viability |

The model never invents a value from the right column. If a number reaches a human, it
came from a tool. The tools return structured results, and what is stored and displayed is
the tool's value — not the model's paraphrase of it.

### The tool surface

Twelve narrow, typed tools. No shell, no arbitrary query, no generic mutation. A run
answering a coordination event is given a different three instead of two of them —
see *The strategy surface* below — so no run ever holds more than twelve.

Four effect kinds, because three could not describe the surface honestly. `read` writes
nothing at all. `record` writes Pool's own working state — an evaluation it wants to be
able to show its reasoning from, or a lifecycle status catching up with facts that are
already true — but commits nothing anyone can observe. `act` is consequential. `end`
closes the run.

| Tool | Kind |
| --- | --- |
| `list_latent_demand` | read |
| `evaluate_pool_economics` | read |
| `inspect_pool` | read |
| `list_pools_needing_attention` | read |
| `create_candidate_pool` | act — commits no money |
| `find_host_candidates` | record — opens recruiting, stores each candidate's evaluation |
| `request_host_acceptance` | act |
| `issue_final_offer` | act — refreshes the quote, authorises or asks |
| `recover_pool` | act |
| `lock_pool` | act — irreversible for buyers |
| `execute_purchase` | act — externally consequential, simulated in this build |
| `record_no_action` | end |

### The strategy surface

A run caused by a **coordination event** — a member created or meaningfully changed a
declaration — is a search rather than a sweep, and is given three different tools *instead
of* latent demand. Never alongside: `create_candidate_pool` is not guarded by
`ensure_actionable` and `create_candidate_pool_from_strategy` is, so a run holding both
would have an unguarded way past the guard.

| Tool | Kind |
| --- | --- |
| `list_cohort_strategies` | record — up to six options, none carrying a verdict |
| `evaluate_cohort_strategy` | record — the authoritative verdict, and evidence of it |
| `create_candidate_pool_from_strategy` | act — commits no money |

The listing carries what generation established: an exact product, its curated
attributes, how much compatible demand its own rules admit, how that splits between now
and demand pulled forward, aggregate refusal codes, a pickup candidate, and the lowest
quantity a supplier will sell. It carries **no verdict and no price**, because at that
point neither exists — which supplier tier wins, whether the demand fills whole cases,
what the group pays and whether that beats buying alone are all facts about a chosen buyer
set, and choosing one is what evaluation does.

The mutation takes **two identifiers and nothing else**. There is no parameter for a
member, a quantity, a price, a supplier term or a product fact; everything the pool is
made of is re-derived from stored state, re-costed from scratch, and refused if anything
it rested on moved. For a member-anchored question it additionally refuses an order that
would not include the declaration that asked it — viable for the neighbours is a real
outcome and a different one.

| Strategy bound | Default | On hit |
| --- | --- | --- |
| `MAX_STRATEGY_LISTINGS` | 1 | Refused with a reason; the options have not changed |
| `MAX_STRATEGY_EVALUATIONS` | 3, against up to 6 options | Refused; the run must choose rather than sweep |
| `MAX_STRATEGY_POOL_CREATIONS` | 1 | Refused; one order per declaration |

`find_host_candidates` was published as a `read` — here, in the API, and on the Showcase
page — while opening host recruiting and persisting a candidate record per evaluation.
The tool did not change; the label did, because the label was what was wrong. The lesson
generalised into a test: `test_agent_effects.py` snapshots the entire workspace around
every tool declared `read` and fails if anything moved, so an effect label is now proved
rather than asserted.

Every `act` tool is idempotent by an explicit key, because agent systems retry and a
retried `create_candidate_pool` must not produce two pools.

### What the model is shown, and what is kept

The larger results are **projected** before they reach the model
([`agent/projection.py`](../services/agent/pool/agent/projection.py)). Strands resends the
whole conversation every turn, so a tool result is billed once per remaining turn — the
first real Bedrock run spent 35.7k input tokens for 418 output tokens, and
`evaluate_pool_economics` alone was 9,015 bytes of per-household detail (#0019, #0020).

A projection keeps the verdict, the blocking reason, the identifiers the next tool call
takes, the magnitudes that make the decision, and counts of the humans involved. It drops
per-household rosters, score components, reward breakdowns, and the list of viability
checks that passed. The **complete authoritative result is retained** on the tool context
for the API, the operator UI, auditing, and tests.

This is a cost boundary, not a truth boundary. Projections select and aggregate values
deterministic code already computed; they compute nothing. Notably, this is *not* LLM
summarization — a model-written summary of a price would make the model the source of
truth, which is the one thing the layering above exists to prevent. Measured effect on the
same model, seed, scenario and bounds: **35.8k → 19.2k input tokens, identical tool
sequence and outcome.**

---

## Declaration to coordination

Declaring a need and coordinating one are different transactions. The write side records
that work is **owed**; a dispatcher decides when it happens.

    declaration written -> CoordinationEvent (pending) -> dispatch -> one bounded run
                                                                   -> candidate pool
                                                                      or honest no-action

An event's id is a digest of the declaration and its material content, so one cause
produces one event: a duplicate submission, a page reload, or an edit that changed nothing
all resolve to the row that already exists, and none of them buys a second model call.
A change that alters what Pool would coordinate produces a different digest and a new
event. Claiming is a state transition, so a second dispatcher finds the work taken.

Nothing is scheduled and nothing polls. An event is dispatched because something asked —
an explicit request today, a queue consumer later. Synchronous dispatch on the declaration
write path exists and is **off by default**: turning it on makes every declaration a model
call, which is right for demonstrating the path end to end and wrong for seeding a
workspace.

**Atomicity is bounded honestly.** The declaration and the event are two writes against a
repository interface with no transaction — two `PutItem` calls on DynamoDB. The event is
written second on purpose, so a crash between them leaves the member's input intact and
coordination merely not yet owed; the reverse ordering would leave an event pointing at a
declaration that does not exist. Making the pair atomic requires `TransactWriteItems` and
the IAM to match. That is a **production requirement and is not implemented**, and
exactly-once event semantics are not claimed.

---

## The lifecycle

One diagram, generated from one adjacency table
([`domain/state.py`](../services/agent/pool/domain/state.py)). There is no second copy to
drift.

```
FORMING ──▶ HOST_RECRUITING ──▶ HOST_SELECTED ──▶ FINAL_OFFER ──▶ FUNDING ──▶ LOCKED
   │              │  ▲                │               │             │           │
   │              │  └────────────────┘               │             │           ▼
   │              ▼                                   ▼             ▼    PURCHASE_READY
   │          FORMING                            RECOVERING ◀───────┘           │
   │                                                  │                         ▼
   │                                                  └──▶ FUNDING · LOCKED  PURCHASED
   │                                                       FINAL_OFFER          │
   │                                                       HOST_RECRUITING      ▼
   └──────────────────────▶ FAILED · EXPIRED ◀──────────────────────────  DISTRIBUTING
                                                                                │
                                                                                ▼
                                                                            COMPLETED
```

Two properties are asserted by tests rather than assumed:

- Nothing reaches `LOCKED` except from `FUNDING` or `RECOVERING` — a pool cannot lock
  before authorisations exist.
- Nothing rewinds out of a post-capture state into a forming one. Once the money is
  captured and the supplier order is committed, there is no undo.

### Why the order is fixed

Host selection must precede the final offer, because host compensation is part of the
buyer's price. Quote refresh must precede the final offer, because a final price may never
rest on a quote nobody re-checked. Authorisation must precede lock, because funded demand
is what makes a pool viable. Capture happens at lock and not before.

```
host accepts → quote refreshed → exact landed cost → final offer
  → buyer policy evaluated → authorisation → funded → viability → LOCK → capture
```

---

## Economics

Computed in [`domain/economics.py`](../services/agent/pool/domain/economics.py), in this
order, because two components would otherwise be circular.

```
1.  merchandise        = cases × case price          (cases chosen to fill exactly)
2.  host compensation  = base + per-order + distance + excess weight + optional handoff
3.  platform fee       = share of GROSS savings      (retail − merchandise − host)
4.  split (1+2+3) across buyers by units, largest-remainder
5.  processing         = per-buyer gross-up: ceil((share + fixed) × 10000 / (10000 − bps))
6.  all-in             = merchandise + host + fee + processing
7.  net savings        = retail baseline − all-in
```

**Step 3** defines the fee against gross savings so it does not refer to the total it
belongs to. Pool earns only when the group is genuinely better off.

**Step 5** grosses up so the buyer's charge covers the processor's cut *of that charge*.
Computing the fee on the pre-fee share instead under-recovers by a few cents per buyer —
a silent platform subsidy, and precisely what the model forbids.

Everything is integer cents. Floats never touch money.

### Case fitting

Cases do not divide evenly into demand, so `fit_to_cases` chooses the buyer subset whose
quantities sum to a multiple of the case size and clear the minimum. It is a bounded exact
search over reachable totals, capped a few cases above the minimum, preferring members
whose need is already due over demand pulled forward from the future.

If no combination lands on a case boundary, the pool does not lock and says so. Pool does
not buy stock nobody ordered.

### The viability engine

One evaluator, two stages, every check run (never short-circuited) so the UI and the agent
trace can show *every* reason a pool is not viable:

```
supplier_moq · offer_active · quote_fresh · package_allocation
host_assigned · host_compensation · buyer_savings · buyer_authorisation
platform_economics · timing · pickup_site
                                   + funding, buyer_decisions_settled  (FINAL_LOCK only)
```

`PRE_FUNDING` asks "is this worth issuing a final offer for". `FINAL_LOCK` asks "may we
take these people's money", runs against stored facts, and is the only gate to a capture.

---

## Data

DynamoDB, single table, on-demand, TTL on demo workspaces.

```
pk = "<workspace>#<TYPE>"     sk = "<entity id>"
```

Listing a type is one query on `pk`. Children use a composite sort key
(`"<pool_id>#<household_id>"`), so a pool's members, host candidates, allocations, and
credentials are each a `begins_with` query rather than a scan.

Workspaces isolate each demo visitor, so two judges cannot corrupt each other's run, and a
TTL sweeps them away.

Entities: `COMMUNITY` · `COMMUNITY_MEMBERSHIP` · `HOUSEHOLD` · `PRODUCT` · `NEED` ·
`SUPPLIER` · `OFFER` · `SITE` · `POOL` · `MEMBERSHIP` · `HOST_PROFILE` · `HOST_CANDIDATE` ·
`HOST_ASSIGNMENT` · `PAYMENT` · `PURCHASE` · `FULFILLMENT_RUN` · `ALLOCATION` ·
`PICKUP_TOKEN` · `ANNOUNCEMENT` · `THREAD` · `MESSAGE` · `ISSUE` · `DECISION` · `ACTIVITY` ·
`RUN`.

**Application state is authoritative.** Agent memory is never authoritative for balances,
commitments, quantities, membership, deadlines, payments, or permissions. Stripe is
authoritative for provider payment facts; what Pool stores is its explicit mapping of them.

Floats do not round-trip through the resource API's serialiser, so coordinates are stored
as tagged strings and restored on read. Money is already integer cents and stores exactly.

---

## Bounds

Enforced in the Strands event loop as a hook provider, not by asking the model nicely.

| Bound | Default | On hit |
| --- | --- | --- |
| `MAX_AGENT_ITERATIONS` | 8 | Raises → run recorded as `loop_fault` |
| `MAX_TOOL_CALLS_PER_RUN` | 25 | Cancels the tool with an explanatory result |
| `MAX_DUPLICATE_TOOL_CALLS` | 2 | Identical name+args cancelled as a loop |
| `WORKFLOW_TIMEOUT_SECONDS` | 45 deployed; 120 local default | Cooperative check between model/tool steps → raises; cannot interrupt a call already running |
| `MAX_ROUTE_MATRIX_CELLS` | 100 | Checked *before* the call is made and billed |

The three strategy budgets above are enforced in the tools rather than in the hook,
because "how many options may be costed" is a question only the tool that costs one can
answer. A test asserts every configured bound is read by the enforcement it names, across
both sites — a bound nothing reads is a guarantee nobody keeps.

Tool-level bounds cancel so the model can wind down cleanly; run-level bounds raise,
because at that point the run is no longer trusted to wind itself down. Every run ends in
a recorded outcome — there is no path where it simply stops.

Tool arguments are stored as a hash, not as text, so a run record can never carry a
member's details into an artifact that gets published.

---

## Security and privacy

- **No response contains a precise location.** Coordinates are snapped to a ~110 m grid
  before leaving the process.
- **No response contains a phone number, email, or payment reference.** Members appear to
  each other as display names. A test asserts this across every read endpoint.
- **Pickup credentials are stored as hashes only.** The plaintext exists once, in the
  response that issued it. Re-issuing invalidates the previous pair. Verification is
  constant-time.
- **Webhooks are verified before they are parsed**, deduplicated by event id, and a replay
  is a no-op. A client-submitted "payment succeeded" is never trusted.
- **The Stripe adapter refuses any key that is not `sk_test_`**, unconditionally.
- **Secrets never enter the CDK template**, because that would put them in `cdk.out` and
  possibly in version control. An infra test asserts it.
- **The model reaches the world through twelve typed tools** and nothing else.

---

## Local, deployed judge path, and pilot-only implementation

| Concern | Local default | Deployed judge path | Implemented pilot stack, not deployed |
| --- | --- | --- | --- |
| Opportunity discovery | Deterministic planner in the real Strands loop | AgentCore Runtime + Bedrock + Strands | Same AgentCore entrypoint |
| Remaining lifecycle | Deterministic planner in the real Strands loop | Deterministic planner in Lambda | Deterministic planner unless configured otherwise |
| State | In-memory | DynamoDB, one table, per-workspace TTL | DynamoDB |
| Routing | Pure function of coordinates | Same deterministic adapter; labelled simulated | Amazon Location `geo-routes` adapter available |
| Payments | Simulated provider | Simulated provider | Stripe **TEST** adapter available; live keys refused |
| Purchase | Simulated executor | Simulated executor | Simulated executor |
| API / web | uvicorn + Vite | One Lambda Function URL serves SPA + 35 of 54 API paths | API Gateway + Lambda; S3 + CloudFront |
| Background | Manual trigger only | **Absent: zero EventBridge rules deployed** | EventBridge definition exists and defaults disabled if this stack is ever deployed |

The offline planner replaces the LLM and only the LLM: the same Strands event loop, the
same tools, the same domain maths, the same state machine, the same policy engine. It
exists so the entire suite runs for free — and cheap tests are tests that actually get run.
It is never presented as evidence that Bedrock works; every run records its
`model_provider`.

### AWS status

Four legs are **cloud-verified** — observed working on a real account, not merely
synthesizing:

| Service | Status |
| --- | --- |
| Amazon Bedrock | **Verified.** `us.amazon.nova-lite-v1:0` drives the real Strands loop and the real tools on both the discovery path (`make verify-bedrock`) and the consequential recovery-and-lock path (`make verify-recovery`). |
| Bedrock AgentCore Runtime | **Verified.** `agentcore_app.py` deployed, `READY` in `us-east-1`, invoked from a public browser through the demo bridge. |
| DynamoDB | **Verified.** The complete lifecycle runs on a real table with identical economics; the first live write found a `Decimal` bug no fake could have. |
| Lambda Function URL | **Verified.** The public judge demo — the SPA and the reduced API from one function, on one origin. |

Still **implemented but never called against the live service**: the EventBridge
definition in the un-deployed pilot stack and the Amazon Location adapter. The judge
account has zero EventBridge rules; “disabled” is not used as shorthand for a resource
that does not exist. Neither component is on the judge path. Nothing in this repository
claims a deployment that has not happened; `docs/HACKATHON_SCORECARD.md` carries the
evidence per item.

Not in the CDK stack, deliberately:

- **AgentCore Runtime** — deployed with its own official tooling, which owns the container
  build and IAM. Duplicating that in CDK would be the fragile custom path.
- **A route calculator** — `geo-routes` needs none, so there is one less billable resource
  to create and forget.

### The runtime and the API share one table

The deployed coordinator runs against **the same DynamoDB partition the browser is
reading**, so the pool a visitor sees was formed by the run on AWS rather than replayed
from its answer. Candidate-pool creation stamps `created_by_run`; the API follows that
exact id to the stored run in the same workspace and returns a causal proof containing
the run id, pool id, tool sequence, outcome, termination and same-workspace readback. It
never substitutes “latest run.” Two stacks, deployed by two different tools, therefore
have to agree about one resource:

| Constant | Where |
| --- | --- |
| Table name `pool-demo-state` | `infra/demo_app.py` creates it; `agentcore/agentcore.json` names it |
| The runtime's grant on it | `services/agent/iam/agentcore-dynamodb.json`, attached via `additionalPolicies` |
| Strongly consistent reads | Both sides, so a refresh after a live run is read-your-writes |

`infra/test_demo_stack.py::TestSharedWorkspaceContract` asserts the three agree, because
neither tool can express the dependency and a drifted name fails silently — the agent
would write to a table nobody reads.

**Authority is deliberately asymmetric.** The API owns workspaces: it seeds them, resets
them, and rations how many can be opened per day. The runtime is only ever a participant
inside one that already exists — it refuses to seed a shared store, and its execution
role holds `GetItem`, `PutItem`, `Query` and nothing else. `Repository.reset()` needs
`DeleteItem` and `BatchWriteItem`, so emptying a visitor's session is not something the
agent can do incorrectly; it is something it cannot do.

Concurrency is handled by a conditional-write lease, one per workspace, taken by
**every** coordinator that mutates it: first-load seeding, reset, the showcase scenario,
a local coordinator run, and the live AgentCore invocation. They are mutually exclusive
because they all write the same partition, and which two overlap is an accident of what
a visitor clicked. Unrelated workspaces never contend — the lease key *is* the workspace.

The lease is coordination, not the invariant itself, so the writes it protects are also
conditional where a duplicate would be visible: candidate-pool creation claims its
idempotency key with a conditional put and hands the loser the winner's pool id, and
single-use pickup redemption is claimed with a conditional update so two simultaneous
scans of one credential complete exactly one handoff.

Three deadlines nest, innermost first: the agent's 45 s wall-clock bound, the bridge's
60 s read timeout, and Lambda's 90 s timeout. The innermost one is **cooperative** —
checked before each model and tool call — so it stops scheduling another step and records
a fault when it fires. It cannot interrupt a call already in progress; the two outer
rungs own the process-level deadlines.

---

## Future — not built

Kept separate so the diagram above stays honest.

- Supplier self-service portal and negotiated direct quotes
- Stripe Connect host payouts (an internal compensation ledger exists instead)
- Multi-hub fulfilment and multi-pool runs batched into one supplier trip
  (`FulfillmentRun` holds a list of pools so this stays possible)
- Institutional SSO verification
- Account authentication (likely Cognito, kept separate from Community membership)
- Cross-community pooling
- Operator-placed and supplier-direct purchase executors
