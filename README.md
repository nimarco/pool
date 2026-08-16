# Pool

**Pool notices when nearby people could save by buying together, then handles the
coordination needed to make the group purchase actually happen.**

Built for the [AWS Agents for Humans hackathon](https://agentsforhumans.devpost.com/) —
**Good Neighbor Agents** track. The value here is structurally collective: one person
alone cannot create it.

---

## The problem, in one exchange

This already happens on every campus:

> "I can buy 50 tubs of protein powder in bulk for way cheaper than the store. DM me if
> you want one."

The informal version works, badly. Someone guesses the demand, fronts hundreds of
dollars of their own money, buys speculative stock, advertises afterwards, answers
thirty messages, tracks who paid, arranges meetups, and eats the leftovers.

Pool runs the same job in reverse:

```
people independently declare recurring needs
  → Pool discovers compatible demand nobody grouped
  → Pool evaluates a bulk offer, its minimum, and its case structure
  → a candidate pool appears, with an honest savings range
  → Pool recruits and ranks someone to collect and hand it out
  → the exact landed price becomes known
  → buyers authorise that exact amount
  → minimum, funding, host, timing and economics all pass
  → the pool locks, payments capture, one bulk order is placed
  → everyone collects in one concentrated pickup window
```

**Nobody creates the group. Pool discovers that the group can exist.** If the product
ever becomes "create a group and invite your friends", the whole thesis is gone.

The host is not a speculative reseller. They are a **paid fulfilment provider for
pre-coordinated demand** — the goods are already sold before anyone buys them.

---

## Three sides, one agent

```
CONSUMER DEMAND          "I want this, cheaper."
        ↕
      POOL
        ↕
BULK SUPPLY              "I can supply this quantity at this price."
        ↕
FULFILMENT LABOUR        "I'll collect and hand it out if the job pays enough."
```

A pool only locks if **all** of them work — plus Pool's own economics. That last
constraint is deliberate: a platform that quietly subsidises a transaction is a platform
that will stop existing.

---

## Run it

Everything below is free, offline, and deterministic. No AWS account, no API key, no
tokens spent.

```bash
make install     # Python agent, web app, CDK deps
make qa          # lint, typecheck, tests, build, secret scan
make demo        # the full lifecycle end to end, printed as a transcript
make dev         # API on :8000, web on :5173
```

Then open <http://localhost:5173> and press **Run the full scenario**.

---

## Community is the boundary, campus is the wedge

A **Community** is the local trust-and-density boundary Pool coordinates inside: a
campus, an apartment complex, a neighbourhood, a workplace. Campuses are the first
polished experience because they have high density, overlapping recurring needs,
walkability, public pickup points, and predictable weekly schedules — not because the
domain is university-shaped. A university is one `CommunityKind`, not a global
assumption. Pools form *within* a Community; cross-community pooling is out of scope for
this build.

**Account authentication and Community membership are separate questions.** You can have
a Pool account without being a verified member of anything, and membership is per
Community, so one account belonging to both a campus and an apartment block is a schema
fact rather than a future migration.

Verification is an abstraction with two working providers:

| Provider | What it proves |
| --- | --- |
| `DemoVerificationProvider` | Nothing. Admits anyone to a synthetic Community. Judge Mode uses this. |
| `EmailDomainVerificationProvider` | Control of an address on a Community-approved domain. Stores the *domain* and a hash — never the address. |
| `FutureInstitutionalSSOProvider` | Documented, not implemented. Requires an institution's agreement, which is not a coding task. |

**Pool never asks anyone for their institution's password**, never scrapes a login page,
and never claims an integration that does not exist.

---

## The canonical lifecycle

```
RECURRING NEEDS → LATENT DEMAND → CANDIDATE POOL
  → SUPPLIER / MOQ EVALUATION → HOST RECRUITING → HOST SELECTED
  → SUPPLIER QUOTE REFRESHED → FINAL LANDED ECONOMICS → FINAL OFFER
  → SMART JOIN / HUMAN DECISION → PAYMENT AUTHORISATION → FUNDED
  → FINAL VIABILITY CHECK → LOCKED → CAPTURE → PURCHASE_READY
  → SIMULATED PURCHASE → PURCHASED → DISTRIBUTING → ONE-TIME QR → COMPLETED
```

Implemented as `PoolStatus` with an explicit adjacency table in
[`domain/state.py`](services/agent/pool/domain/state.py). Two properties are asserted by
tests rather than assumed: nothing reaches `LOCKED` except through `FUNDING` or
`RECOVERING`, and nothing rewinds out of a captured state.

Failure is normal, so the branches are real: no viable host, host declines, host offer
expires, quote goes stale, quote materially changes, authorisation fails, buyer withdraws
pre-lock, capture fails, purchase fails, buyer no-shows, credential re-used.

---

## The parts that are easy to get wrong

### Provisional participation is not financial commitment

A candidate pool counts **provisional** demand so the opportunity can be discovered and
shown. Only **authorised** demand counts toward the funded threshold. Adding a recurring
need never touches anyone's card.

```
ELIGIBLE → PROVISIONAL → FINAL_OFFERED → AUTHORIZED → LOCKED
```

### The host is chosen before anyone is charged

Host compensation is part of the buyer's price, so the order is fixed: host accepts →
quote refreshed → exact landed cost → final offer → buyer policies evaluated →
authorisation → lock. Pool never authorises $42 and later charges $47. If the price
moves before lock, the stale hold is released and the buyer is asked again.

### The price includes everything

```
  bulk merchandise
+ host / runner compensation
+ payment processing
+ Pool platform fee
= all-in Pool cost

retail comparison − all-in Pool cost = net savings
```

Smart Join is evaluated against **net** landed savings. Two subtleties are load-bearing:
the platform fee is a share of *gross* savings, so it is defined without referring to the
total it belongs to; and card processing is **grossed up** per buyer, so the charge
covers the processor's cut of that very charge. Computing it the naive way would
under-recover by a few cents per buyer — a silent platform subsidy, which is exactly what
the model forbids.

If fair host pay erases the saving, the pool should not form. That is a correct outcome,
not a bug.

### Pool does not buy stock nobody ordered

Cases do not divide evenly into demand. Rather than quietly buying the leftovers and
billing someone for them, Pool **chooses the buyer set that fills whole cases exactly**
([`fit_to_cases`](services/agent/pool/domain/economics.py)), preferring people whose need
is already due over demand pulled forward. If no combination lands on a case boundary,
the pool does not lock and says why.

### Future demand moves only with permission

Each need carries two different timing numbers: a **routine restock lead** (when someone
normally buys) and an **earliest acceptable purchase date** (how far ahead they are
willing to buy if it saves money). The agent may decide to *investigate* whether more
demand exists; the deterministic timing engine decides *who is actually eligible*. A
member who authorised no early purchase is never pulled forward, however convenient it
would be for the case count.

In the demo this is not decoration: current demand reaches 18 units against a 24-unit
minimum, and only permitted pull-forward demand completes the order.

### Offering to host is not claiming the job

Candidates come from two places: standing hosts who opted in earlier, and ordinary pool
members who click "Offer to host" on this specific pool. Several people can offer at
once. A deterministic evaluator checks facts — availability, vehicle, capacity, weight,
supplier travel, pickup-site suitability, their own minimum pay — and ranks the eligible
ones on the whole transaction, not the cheapest line. The top candidate gets an offer.
If they decline or the window expires, the next one does. There is no
first-come-first-served path.

Compensation scales with the work: base + per order + distance + exceptional weight +
an optional handoff component. A buyer no-show cannot erase pay for a run already done —
only the handoff slice is contingent.

### Pickup is proved, not asserted

Every buyer allocation gets its own one-time credential: a long token for the QR and a
short human-readable code for when scanning is awkward. **Only hashes are stored.** The
plaintext exists exactly once, in the response that issued it; re-issuing invalidates the
previous pair. The credential carries no payment details, phone number, or email. A host
cannot mark an order collected without one — the only other route is an operator override
that requires a stated reason and is audited.

### Communication is exception-driven

Routine communication is automated; human messaging is the exception. There is no pool
group chat. Buyers get structured exceptions first ("running late", "can't pick up
today"), most of which Pool resolves with nobody's attention; a product problem becomes an
operator case rather than an argument at the pickup table; only what is left opens a
private, transaction-scoped buyer ↔ host thread that archives with the pool. No phone
number or email is ever exposed.

---

## AI decides what to do. Deterministic code determines what is true.

| The model may decide | Deterministic code determines |
| --- | --- |
| which latent demand deserves investigation | cents, quantities, package maths |
| whether to search or refresh offers | MOQ, allocations, offer freshness |
| whether a candidate pool is worth forming | timing eligibility, product compatibility |
| whether to recruit a host | host eligibility and compensation |
| which recovery strategy to attempt | buyer landed price, platform fee |
| whether to surface a human decision | payment and funding state |
| when there is nothing worth doing | pickup-code validity, state transitions |
| | Smart Join verdicts and final viability |

The agent reaches the world through twelve narrow typed tools and nothing else — no
shell, no arbitrary SQL, no generic mutation. Every tool is either a safe read or a
single consequential operation with idempotency and an approval boundary built in.

**Smart Join** returns one of three verdicts, never "close enough":

```
AUTO_APPROVED   HUMAN_APPROVAL_REQUIRED   NOT_ALLOWED
```

`NOT_ALLOWED` is reserved for situations no prompt can fix — a product outside the
member's substitution authority, or a scheduling conflict with the pickup day.

---

## Bounded by construction

Every run is bounded in the Strands event loop, not by asking the model nicely:

| Bound | Default | Behaviour on hit |
| --- | --- | --- |
| `MAX_AGENT_ITERATIONS` | 8 | Terminates the run as a recorded loop fault |
| `MAX_TOOL_CALLS_PER_RUN` | 25 | Global circuit breaker |
| `MAX_DUPLICATE_TOOL_CALLS` | 2 | Identical name+args cancelled as a loop |
| `WORKFLOW_TIMEOUT_SECONDS` | 120 | Wall-clock kill switch |
| `MAX_ROUTE_MATRIX_CELLS` | 100 | Checked *before* any routing call is billed |

A run that hits a bound ends loudly with a `loop_fault` outcome — never a silent
truncation that looks like a normal result. Background schedules ship **disabled**.

---

## Local mode, and what is not real

| Layer | Local / demo | Would a pilot change it? |
| --- | --- | --- |
| Model | Deterministic offline planner, real Strands loop | Swap to `BedrockModel` |
| Persistence | In-memory | DynamoDB single table (adapter exists) |
| Routing | Deterministic function of coordinates | Amazon Location `geo-routes` (adapter exists) |
| Payments | `LocalSimulatedPaymentProvider` | Stripe **TEST** provider (refuses non-test keys) |
| Purchase | `SimulatedPurchaseExecutor` — every record flagged synthetic | A merchant-of-record decision, not a code change |
| Community | Demo University, entirely invented | A real Community with real verification |

The offline planner replaces **the LLM and only the LLM**. The Strands event loop, the
tools, the domain maths, the state machine, the policy engine, the payment state machine,
and the human-in-the-loop boundary are all the real thing. That is what makes the whole
test suite free to run — and cheap tests are tests that actually get run.

It is not evidence that Bedrock works, and it is never presented as such: every run
records `model_provider`, and the UI shows it.

**Not real, and labelled as such everywhere:** the Community, the members, the suppliers,
the offers, the money, and the purchase. No goods move. No traction is claimed.

---

## AWS

**Bedrock inference is verified**: a real model drives the real Strands loop and the real
Pool tools (`make verify-bedrock`). Everything else is implemented and synthesizing but
**not yet verified against a live account**. Nothing in this repository claims a deployment
that has not happened.

| Service | Role | Status |
| --- | --- | --- |
| Bedrock | Model inference via Strands | **Verified** — `us.amazon.nova-lite-v1:0`, 5 Pool tools called from a real run |
| AgentCore Runtime | Hosted agent entrypoint | `agentcore_app.py`, deployed with the official toolkit |
| DynamoDB | Authoritative application state, single table, on-demand, TTL | Implemented, pinned by a fake-client test |
| API Gateway + Lambda | Public API | In the CDK stack |
| S3 + CloudFront | Public web app | In the CDK stack |
| EventBridge | Background scan | In the stack, **created disabled** |
| Amazon Location | `geo-routes`, no provisioned calculator | Implemented, unverified |
| CloudWatch | Structured run records, retention capped at 14 days | In the stack |

```bash
make whoami   # which principal am I? run this first
make synth    # synthesize the template — no credentials needed
make deploy   # (COSTS MONEY)
make cost-check
make destroy
```

See [`docs/COST_NOTES.md`](docs/COST_NOTES.md) for the resource ledger and
[`AGENTS.md`](AGENTS.md) §3 for the cost rules every change is held to.

---

## Repository

```
services/agent/pool/
  domain/          pure, deterministic, no I/O — the things that must be *correct*
    models.py        entities and enums
    economics.py     landed price, host reward, fees, case fitting
    viability.py     the central four-party viability engine
    policy.py        Smart Join
    hosting.py       host evaluation and ranking
    matching.py      latent-demand discovery
    timing.py        Pool Days, windows, pull-forward authority
    substitution.py  structured product substitution
    pickup.py        one-time credentials
    money.py         exact-cent arithmetic
    state.py         the lifecycle adjacency table
  services/        orchestration over the domain — everything the agent can *do*
  adapters/        repository, routing, payments, purchase, sourcing, verification
  agent/           Strands coordinator, tools, bounds, result projection, offline planner
  api/             FastAPI
  data/seed.py     the synthetic Demo University dataset
apps/web/          React app: buyer, host, operator, judge
infra/             CDK stack + cost-safety tests
docs/              architecture, pilot readiness, thesis, demo script, scorecard
```

---

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — what is actually built, and how
- [`docs/PILOT_READINESS.md`](docs/PILOT_READINESS.md) — what a real pilot still needs, including the parts that are legal questions rather than coding ones
- [`docs/STARTUP_THESIS.md`](docs/STARTUP_THESIS.md) — the business argument and its assumptions
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the five-minute story
- [`docs/HACKATHON_SCORECARD.md`](docs/HACKATHON_SCORECARD.md) — evidence per judging criterion, honestly graded
- [`docs/COST_NOTES.md`](docs/COST_NOTES.md) — every resource that can accrue cost
- [`BUILD_HISTORY.md`](BUILD_HISTORY.md) — decisions, rejected approaches, and what broke
- [`AGENTS.md`](AGENTS.md) — the operating manual any agent working here must follow

## Licence

MIT — see [`LICENSE`](LICENSE).
