# Pool — architecture

![Pool architecture](architecture.svg)

Source: [`architecture.mmd`](architecture.mmd). Regenerate with:

```bash
npx -y @mermaid-js/mermaid-cli@11 -i docs/architecture.mmd -o docs/architecture.svg -b transparent
```

Only services Pool actually uses appear in the diagram. There is no AgentCore Browser, no
web search, no vector database, and no message queue, because none of them solve a problem
Pool has.

---

## The organising principle

> **AI decides what to do. Deterministic systems decide what is true.**

This is not a slogan; it is the reason the codebase is shaped the way it is. Pool handles
other people's money. A model that can invent a price, a quantity, or a threshold is a
model that will eventually tell a household it owes $18.40 when it owes $24.60 — and the
error is invisible until someone is out of pocket.

So the split is enforced structurally:

- **The agent** receives structured facts and chooses the next action.
- **The tools** compute, validate, and persist. They are pure functions over stored state
  wherever possible.
- **Anything a household is shown** originates in a tool result, never in generated text.

Concretely, `pool/agent/tools.py` returns JSON produced by `pool/services/coordination.py`,
which in turn calls `pool/domain/{money,allocation,matching,policy,state}.py`. None of
those modules import an LLM client. They cannot be influenced by a model at all.

---

## Layers

### 1. Domain (`services/agent/pool/domain/`)

Pure Python. No I/O, no AWS, no model. Fully unit tested.

| Module | Responsibility | Why it matters |
| --- | --- | --- |
| `money.py` | Integer-cent arithmetic; largest-remainder allocation; basis-point savings | Float money is a rounding bug waiting to become a wrong number in a message |
| `matching.py` | Product compatibility, substitution consent, timing windows, geographic filters | This is where *latent* demand is discovered — the core insight |
| `allocation.py` | Case-based bulk pricing, exact per-household splits, surplus accounting | Buying whole cases means real surplus; the maths shows it rather than hiding it |
| `policy.py` | Smart Join evaluation; the autonomous/consequential action split | The autonomy boundary, as a pure function |
| `state.py` | Pool state machine with an explicit legal-transition table | The model can request a transition; this decides if it is legal |
| `models.py` | Entities with explicit `to_dict`/`from_dict` | One shape travels to DynamoDB, the API, and tool results |

**Money design note.** `allocate_cost` uses the largest-remainder method so per-household
shares always sum to exactly the group total — no cent is created or lost, and the split
is deterministic and order-stable so two households comparing notes see consistent
figures.

**Pricing design note.** A bulk offer sells whole cases. To serve 155 lb the pool buys
`ceil(155/25) = 7` cases (175 lb) and pays for all of them. That surplus cost is shared
across the units households actually requested, which is what happens in a real
split-a-case buy. Savings are always measured against the retail baseline each household
would have paid alone.

### 2. Services (`services/agent/pool/services/`)

`coordination.py` is the only module that mutates the world. Every consequential operation
is idempotent by explicit key, because agent systems retry:

| Operation | Idempotency mechanism |
| --- | --- |
| `create_pool` | `idempotency_key = product:site:pickup_date`; a repeat returns the existing pool |
| `withdraw_household` | Already-withdrawn membership returns `already_withdrawn` without re-subtracting |
| `respond_to_decision` | A non-pending decision short-circuits; a contradictory second answer is ignored |
| `recover_pool` | Replacements are keyed by `(pool, household)`, so a retry overwrites rather than adding |
| `refresh_threshold` | Pure recomputation; safe to call any number of times |

### 3. Adapters (`services/agent/pool/adapters/`)

One interface, two implementations each — so tests are free and the cloud path is real.

```
Repository        → InMemoryRepository | DynamoDBRepository
RoutingService    → DeterministicRouting | AmazonLocationRouting   (both behind CachingRouting)
Model             → DeterministicPlannerModel | BedrockModel
```

**Routing.** Pool uses the `geo-routes` Routes API rather than the older `location`
service specifically because geo-routes needs **no provisioned route calculator** — one
less billable resource to create, forget, and pay for. Matrix size is checked *before* any
call, because a route matrix is `origins × destinations` cells and is billed per cell. If
the API fails, the adapter **raises**; it never substitutes a plausible-looking number. A
hallucinated route is precisely the failure this architecture exists to prevent.

**DynamoDB.** Single table, `pk = "<workspace>#<TYPE>"`, `sk = "<entity id>"`. Listing a
type is one Query; a pool's memberships use a composite sort key so they are a
`begins_with` query rather than a scan. Workspaces isolate demo visitors from each other
and carry a TTL.

### 4. Agent (`services/agent/pool/agent/`)

**One agent, not a swarm.** Pricing, matching, routing, and policy are tools, not agents,
because they need to be *correct*, not *creative*. Inventing a `PricingAgent` would add
latency, cost, and a new way for a number to be wrong, in exchange for nothing.

`coordinator.py` builds a Strands `Agent` with the tool set, the system prompt, and the
bounds hook, then runs it once and records the outcome. The same method serves the
EventBridge schedule, the AgentCore entrypoint, the demo button, and the tests — there is
no separate demo path.

**`bounds.py`** is the interesting part. It is a Strands `HookProvider`:

| Hook | Bound | Behaviour on breach |
| --- | --- | --- |
| `BeforeModelCallEvent` | max iterations, wall clock | **raises** — the run unwinds into a recorded `loop_fault` |
| `BeforeToolCallEvent` | max tool calls, duplicate calls | sets `cancel_tool` with an explanation the model can act on |
| `AfterToolCallEvent` | — | records tool name, ok/failed, and a truncated summary |
| `AfterModelCallEvent` | — | accumulates token usage |

Tool-level bounds cancel gracefully so the model can wind down; run-level bounds raise,
because at that point the run is no longer trusted to stop itself.

Two implementation findings, both recorded in `BUILD_HISTORY.md`:

1. Strands wraps a hook exception in `EventLoopException`, so `except BoundExceeded` never
   fires at the caller. The coordinator walks the `__cause__`/`__context__` chain instead.
   Misclassifying a fired bound as a crash would have hidden the thing we most need to see.
2. Token usage is not on `stop_response.usage`; it rides in
   `stop_response.message["metadata"]["usage"]`. Reading it per model call (rather than
   from `AgentResult` at the end) means an aborted run still records what it spent — and an
   aborted run is exactly the one whose cost matters.

**`offline_model.py`** implements the Strands `Model` interface with a deterministic
planner. It replaces the LLM and nothing else: the real event loop, tools, domain math,
state machine, and approval boundary all execute. Runs using it are labelled
`model_provider="offline"` in the run record and the UI, so a demo can always distinguish
model-driven runs from free ones.

### 5. API and web

FastAPI under uvicorn locally and Lambda via Mangum in the cloud. The browser never holds
AWS credentials and never calls an AWS service directly.

Privacy is enforced at the boundary, not by convention: `coarse()` snaps coordinates to a
~110 m grid before they leave the process, and `test_api.py` asserts the map endpoint can
never return a precise household position.

---

## Request flows

### Background scan

```
EventBridge (disabled by default) ──▶ Lambda ──▶ PoolCoordinator.run()
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
              Strands event loop  ◀──▶  Bedrock (choose next tool)
                    │                        ▲
                    │                        │ BoundedRun hook enforces limits
                    ▼
              list_unmet_demand ──▶ evaluate_opportunity ──▶ create_buying_pool
                                          │                        │
                              matching + allocation +      state machine + policy
                              routing + policy                     │
                                          ▼                        ▼
                                      DynamoDB              Decision Inbox
```

### Dropout recovery

```
withdraw_household ──▶ refresh_threshold ──▶ status: recovering
                                                   │
PoolCoordinator.run("recover…") ───────────────────┘
        │
        ├─ list_pools_needing_attention   (finds the shortfall)
        └─ recover_pool
                ├─ widen the search radius (2 km → 8 km)
                ├─ rank candidates: largest first, then nearest  ← fewest people disturbed
                ├─ re-price the whole pool with replacements included
                ├─ auto-join only where Smart Join deterministically passes
                ├─ re-price existing members — but if a share rises past someone's own
                │  cap, ask rather than silently changing their commitment
                └─ refresh_threshold ──▶ threshold_met
```

The radius asymmetry is deliberate and is the reason the scenario works: **form tight,
repair wide.** The initial pool stays close so travel burden is low; only a repair widens
the net, and even then every candidate is still bounded by their own travel policy.

---

## What is deliberately absent

| Not used | Why |
| --- | --- |
| Multi-agent swarm | Deterministic domains are tools. More agents would add cost and failure modes, not capability |
| AgentCore Browser / Web Search | No product need. Synthetic supplier data demonstrates the coordination claim; scraping demonstrates scraping |
| Vector database / RAG | Nothing here is a semantic retrieval problem |
| Route calculator resource | `geo-routes` needs none — one less billable thing to forget |
| Payments | Pool models commitment and approval. Real charging is not the innovation and would make a public demo unsafe |
| EC2 / RDS / NAT / load balancer | Bills continuously. Asserted absent in `infra/test_stack.py` |
