# Pool

**Neighbours buying together, without anyone having to organise it.**

Pool is an autonomous neighbourhood group-buying coordinator built for the AWS *Agents for
Humans* hackathon, entered in the **Good Neighbor Agents** track.

---

## The problem

Buying in bulk is dramatically cheaper. Most households can't, because a 150 lb minimum
order is not something one family needs — and getting eight families to buy it together is
real work: recruiting people, splitting quantities, comparing suppliers, working out
whether the saving is even worth it, arranging a pickup, chasing replies, and starting
over when someone drops out.

That work is unpaid, tedious, and always lands on one exhausted volunteer. It is the
reason neighbourhood buying clubs mostly don't exist — not the lack of an app.

## The idea

**People should not have to organise a buying group. Pool should discover that the buying
group can exist.**

Households declare what they routinely buy, once, with their own limits. Then they close
the app. Pool runs in the background: it notices overlapping demand nobody announced,
checks whether aggregating it clears a supplier's minimum, prices the result exactly,
solves the pickup logistics, forms the group, and repairs it when someone withdraws —
contacting a human only when a decision genuinely requires one.

## Why this is an agent, not a marketplace

A marketplace waits for a human to start something. A CRUD app stores what humans typed.
Pool's core loop is search over a space nobody asked about:

- **The opportunity is latent.** Nobody said "let's buy rice together". Eight households
  separately said they buy rice. Discovering that a viable group *could* exist requires
  looking for something no one requested.
- **Feasibility is multi-constraint and shifting.** Price tiers, case sizes, supplier
  minimums, individual budget ceilings, substitution tolerance, timing windows, travel
  limits, and who is willing to host.
- **Failure is normal and recovery is bespoke.** Someone drops out at 80% commitment. What
  to do depends on the specific pool, the specific shortfall, and who could absorb it.
- **Most decisions should never reach a human**, and the ones that do should arrive
  already worked out.

---

## What it actually does — the demo scenario

One command runs the whole thing:

```bash
make demo
```

1. **Discovery.** A background scan finds eight households in the same few blocks who each
   declared a jasmine rice need. Nobody posted a listing.
2. **Evaluation.** Aggregated, their 155 lb clears a wholesaler's 150 lb minimum, unlocking
   25 lb bags at $0.69/lb against $1.35/lb retail. Deterministic tools compute the exact
   split: **$99.00 saved across the group, 42.3% below buying alone.**
3. **Autonomy split.** Seven households pre-authorised joins within their own limits and
   are committed silently. Two are on *Ask Me* and receive one worked-out question each.
4. **A real dropout.** The largest participant withdraws, releasing 30 lb. The pool falls
   to 125/150 — below the supplier minimum. The deal is dead.
5. **Automatic recovery.** A second coordination run searches the wider neighbourhood,
   finds a household whose own Smart Join policy permits the join, adds them, and restores
   the threshold. **Nobody else is contacted.**

> **Pool recovered automatically.**
> A participant withdrew. Pool matched another compatible household and preserved the
> group discount. No action required.

Every number above is computed by Pool's pricing tools from stored offers and committed
quantities. None of it is generated text, and none of it is hardcoded — `make test-demo`
asserts the whole sequence actually executes.

---

## Architecture

![Pool architecture](docs/architecture.svg)

Source: [`docs/architecture.mmd`](docs/architecture.mmd) · Full explanation:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

### The central principle

> **AI decides what to do. Deterministic systems decide what is true.**

| The model may decide | Deterministic code determines |
| --- | --- |
| which opportunity to investigate | every monetary amount |
| which tool to call next | quantities and allocations |
| whether a result is worth acting on | discount percentages |
| what recovery strategy to try | whether a threshold mathematically passes |
| whether a human must be consulted | commitment and membership state |
| when to stop | route distances and travel times |
| | authorization and Smart Join eligibility |

The agent never invents a value from the right-hand column. If a number reaches a
household, a tool computed it. This is the difference between an agent you can put in
front of someone's money and a demo.

### Agent tools

Seven narrow, typed tools — no generic database or shell escape hatch.

| Tool | Kind | What it does |
| --- | --- | --- |
| `list_unmet_demand` | read | Declared needs no active pool is serving |
| `evaluate_opportunity` | read | Full costing: matching, best bulk tier, exact allocations, routing, per-household policy verdicts |
| `create_buying_pool` | consequential | Forms a pool; auto-joins only where policy permits; idempotent |
| `list_pools_needing_attention` | read | Pools below their supplier minimum |
| `recover_pool` | consequential | Finds replacements, repairs the threshold, avoids disturbing existing members |
| `record_no_action` | terminal | Concludes a run with nothing to do — a good outcome |

### Smart Join — the autonomy boundary

Each household sets machine-verifiable rules. A pure function evaluates all six and
returns a full audit trail; the model reads the verdict, it never makes it.

```
Auto-join only if:
  savings ≥ 30%          AND  total cost ≤ $25
  pickup travel ≤ 8 min  AND  exact product (or an explicitly accepted substitute)
  pickup site is public  AND  Smart Join is enabled
```

Where a household's standing policy and a specific need disagree, the **stricter** value
wins. Actions that always need a human unless explicitly pre-authorised: committing money,
raising a budget, accepting a substitute, offering a private residence as a pickup point,
or accepting materially worse terms — including a re-price that pushes an existing
member's share past their own cap during a recovery.

---

## Cost safety

This project runs on a student's promotional AWS credits, so bounds are enforced in code,
not documented as intentions.

| Guard | Default | Enforced by |
| --- | --- | --- |
| Model iterations per run | 8 | Strands `BeforeModelCallEvent` hook — raises, terminating the run |
| Total tool calls per run | 25 | `BeforeToolCallEvent` circuit breaker |
| Identical repeated tool calls | 2 | Argument digest; the call is cancelled with an explanation |
| Tool retries | 3 | Bounded with backoff |
| Wall clock per run | 120 s | Checked on every model and tool call |
| Route matrix size | 100 cells | Checked *before* any Location API call |

Every bound is an env var, so it can be tightened without a code change. A run that hits
one terminates **loudly** — recorded as a `loop_fault` with the reason — never as a silent
truncation dressed up as a normal result.

Infrastructure is serverless, on-demand, and destroyable: DynamoDB pay-per-request with a
TTL on demo data, 14-day log retention, no EC2/RDS/NAT/load balancer, and the background
schedule **ships disabled**. `infra/test_stack.py` asserts all of that against the
synthesized template so it cannot quietly stop being true.

Full detail: [`docs/COST_NOTES.md`](docs/COST_NOTES.md).

---

## Running it

### Local (free — no AWS account, no model tokens)

```bash
make install
make demo          # the whole scenario, printed
make test          # 219 tests
make dev           # API on :8000, web on :5173
```

The default configuration uses an in-memory store, deterministic routing, and an **offline
planner** in place of the LLM. That planner substitutes for the model *only* — the real
Strands event loop, the real tools, the real domain math, the real state machine, and the
real approval boundary all execute. It exists so the test suite and local demo cost
nothing, because cheap tests are tests that actually get run.

### With Bedrock

```bash
export MODEL_PROVIDER=bedrock
export BEDROCK_MODEL_ID=<verify against your account, see below>
export AWS_REGION=us-east-1
make api
```

> **Verify the model id first.** Strands reaches Bedrock through the boto3
> `bedrock-runtime` Converse API, whose identifiers are inference-profile-scoped and vary
> by account and region. The default in `pool/config.py` has **not** been verified against
> a live account. List what yours actually has:
>
> ```bash
> aws bedrock list-inference-profiles --region "$AWS_REGION" \
>   --query 'inferenceProfileSummaries[?contains(inferenceProfileId, `anthropic`)].inferenceProfileId'
> ```

### Deploying

```bash
make whoami        # identity check — refuses to proceed on root credentials
make synth         # offline; produces the CloudFormation template
make deploy        # DynamoDB + Lambda + API Gateway + EventBridge (disabled) + S3/CloudFront
make deploy-web    # build and upload the web app
make deploy-agent  # AgentCore Runtime via the official starter toolkit
make smoke API_URL=https://…
```

Cleanup, and the commands to check nothing was left running:

```bash
make cost-check    # lists project resources and flags anything recurring
make schedule-off  # stop scheduled runs without tearing down
make destroy       # remove the stack
```

### Environment

See [`.env.example`](.env.example). The variables that matter most:

| Variable | Default | Meaning |
| --- | --- | --- |
| `MODEL_PROVIDER` | `offline` | `offline` \| `bedrock` |
| `BEDROCK_MODEL_ID` | *(unverified)* | Inference profile id — verify against your account |
| `POOL_REPOSITORY` | `memory` | `memory` \| `dynamodb` |
| `ROUTING_PROVIDER` | `deterministic` | `deterministic` \| `aws_location` |
| `SCHEDULES_ENABLED` | `false` | Background scans are off unless deliberately enabled |
| `MAX_AGENT_ITERATIONS` | `8` | Hard iteration cap |

---

## Testing

```bash
make test        # everything
make test-demo   # just the end-to-end showcase
make qa          # lint + typecheck + tests + build + secret scan
```

219 tests, all offline. Coverage is deliberately concentrated where a bug would be
expensive:

- **Money** — allocations sum to the total exactly, at every total; savings can go
  negative when a deal is bad rather than being clamped
- **Matching** — exact vs. substitute, timing, radius, and the reason each rejection happened
- **Smart Join** — every one of the six rules gets a test proving it can block an auto-join
- **State machine** — every illegal transition raises; terminal states have no exits
- **Idempotency** — duplicate create, withdraw, approve, and recover are all called twice
- **Agent safeguards** — a model designed to loop forever is stopped by the iteration cap;
  a model repeating one call is cancelled by duplicate detection
- **Privacy** — the map endpoint can never return precise household coordinates
- **Infrastructure** — the schedule is disabled, logs are bounded, nothing is always-on

---

## Privacy

Pool is a neighbourhood product, so its default dataset is *where people live*.

- Household coordinates are snapped to a ~110 m grid before leaving the server, and map
  markers carry no name or address.
- Pool membership shows a display name and a neighbourhood, never a location.
- Public community sites are preferred for pickup unconditionally; offering a private
  residence is a consequential action requiring its owner's approval.
- Agent run records store tool names, counters, and termination reasons — never model
  reasoning, and tool arguments only as a hash.
- All demo data is synthetic. No real household, supplier, or organisation is represented.

---

## Limitations

Stated plainly, because a submission that hides these is less trustworthy than one that
doesn't:

- **No payments.** Pool models commitment, allocation, cost, and approval, but takes no
  money. Checkout is explicitly labelled as simulated.
- **Synthetic suppliers.** The catalog is invented. A sourcing adapter interface exists for
  real integrations; live scraping was deliberately not built — it is brittle, expensive,
  and not the interesting claim.
- **Cloud deployment is unverified.** No AWS credentials were available during development.
  The infrastructure is written, synthesizes cleanly, and is asserted by tests, but has
  never been applied to a live account. See *Status* below.
- **Routing defaults to a model, not a map.** The deterministic adapter estimates travel
  from great-circle distance. The Amazon Location integration is written and its response
  parsing is tested against the real service model, but has not run against live AWS.
- **One neighbourhood.** No multi-region, no supplier portal, no reputation system.

## Status

| Component | Coded | Locally tested | Deployed | Cloud verified |
| --- | :-: | :-: | :-: | :-: |
| Domain, matching, allocation, policy | ✅ | ✅ | n/a | n/a |
| Strands agent + bounded loop | ✅ | ✅ | — | ❌ |
| Bedrock model provider | ✅ | ❌ | — | ❌ |
| DynamoDB repository | ✅ | ✅ (fake client) | — | ❌ |
| Amazon Location routing | ✅ | ✅ (recorded shape) | — | ❌ |
| API + web app | ✅ | ✅ | — | ❌ |
| CDK stack | ✅ | ✅ (synth + assertions) | — | ❌ |
| AgentCore Runtime entrypoint | ✅ | — | — | ❌ |

Nothing in this repository claims to be running in the cloud. When it is, this table and
[`BUILD_HISTORY.md`](BUILD_HISTORY.md) get updated with evidence.

## Future direction

Pool's long-term thesis moves from *neighbours splitting an existing bulk package* toward
*consumer demand aggregation*, where Pool negotiates directly with distributors on behalf
of aggregated, verified demand. Nearer-term: a supplier portal, pickup-host compensation,
reputation, recurring subscriptions, and apartment-building and campus deployments.

## Repository

```
services/agent/     Python — domain, tools, Strands agent, API, tests
apps/web/           React + TypeScript — the consumer app
infra/              AWS CDK stack + cost-safety tests
docs/               Architecture, scorecard, demo script, Devpost draft, article notes
scripts/            Preflight, secret scan, smoke test, cost check, cleanup
AGENTS.md           Operating manual for coding agents on this repo
BUILD_HISTORY.md    Truthful engineering journal
```

## License

MIT — see [LICENSE](LICENSE).

## Disclosure

Built during the AWS *Agents for Humans* submission period. Developed with heavy AI coding
assistance; every result was validated by running it. All demonstration data is synthetic —
no real users, no real transactions, no traction claimed.
