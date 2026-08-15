# Devpost submission — draft

**Not submitted.** Factual draft. Nothing below claims users, traction, partnerships, or
deployed services that do not exist.

---

## Project name

**Pool**

## Tagline

Neighbours buying together, without anyone having to organise it.

## Track

Good Neighbor Agents

---

## Inspiration

Bulk pricing is one of the few genuinely free lunches in household spending — often 30–45%
off. Most households never touch it, because a 150 lb minimum is not something one family
needs.

Eight families together clear that minimum easily. So why don't neighbourhood buying clubs
exist everywhere?

Because someone has to run them. Recruit the eight families. Split the quantities. Compare
suppliers. Work out whether the saving justifies the hassle. Book a pickup. Chase the four
people who didn't reply. Then someone drops out and the whole thing collapses.

That work is unpaid, tedious, and always lands on one exhausted volunteer. It is the real
barrier — not the absence of an app. Every group-buying product we looked at still assumes
a human organiser and just gives them better tools.

We wanted to remove the organiser entirely. Which turns out to be an agent problem, because
the hard part is *searching a space nobody asked about*: nobody says "let's buy rice
together", they just separately buy rice.

## What it does

Households declare what they routinely buy — once — with their own limits: quantity,
cadence, minimum saving, maximum spend, maximum travel, substitution tolerance, and how
much authority Pool has to act for them. Then they close the app.

Pool runs in the background and:

1. **Discovers latent overlap.** Finds households with compatible declared demand nearby.
   Nobody posted a listing.
2. **Evaluates whether it's worth it.** Compares bulk tiers, checks supplier minimums,
   computes exact per-household allocations and savings against a retail baseline.
3. **Solves the logistics.** Picks the public pickup site that serves the most households,
   computes real travel times, and checks each household's travel limit.
4. **Forms the group.** Households whose Smart Join policy deterministically passes are
   committed without being interrupted. Everyone else gets one worked-out question.
5. **Repairs itself.** When a participant withdraws and the pool falls below the supplier
   minimum, Pool widens its search, finds a compatible replacement, and restores the
   threshold — without disturbing the people who did nothing wrong.

In the demo scenario: eight households, 155 lb of rice, **$99.00 saved (42.3% below
retail)**, seven commitments made without interrupting anyone, two questions asked. Then
the largest participant withdraws — 30 lb gone, pool dead at 125/150 — and Pool
automatically finds a replacement and restores it. Nobody else is contacted.

## The idea, in one line

**People should not have to organise a buying group. Pool should discover that the buying
group can exist.**

## How we built it

### One agent, many deterministic tools

A single **Strands Agents** coordinator on **Amazon Bedrock**, with seven narrow, typed
tools. We deliberately did not build a swarm: pricing, matching, routing, and policy need
to be *correct*, not creative, so they are tools rather than agents.

The organising principle: **AI decides what to do; deterministic systems decide what is
true.**

The agent chooses which opportunity to investigate, which tool to call, whether a result is
worth acting on, how to recover a broken pool, whether a human is needed, and when to stop.
It never computes a price, a quantity, a threshold, a route, or an authorization — those
come from pure Python modules that cannot import a model client. If a number reaches a
household, a tool computed it.

### Smart Join — a machine-verifiable autonomy boundary

Each household sets explicit rules. A pure function evaluates six of them and returns a
full audit trail:

```
Auto-join only if:
  savings ≥ 30%   AND  total cost ≤ $25   AND  travel ≤ 8 min
  AND exact product (or an explicitly accepted substitute)
  AND pickup site is public   AND Smart Join is enabled
```

Where a standing policy and a specific need disagree, the stricter value wins. The model
reads the verdict; it never makes it. Committing money, raising a budget, accepting a
substitute, or offering a private residence as a pickup point always require a human unless
explicitly pre-authorised.

A subtlety we're proud of: during recovery, adding a replacement changes everyone's share.
If that pushes an existing member past their own cap, Pool **asks them** rather than
silently repricing a commitment they already made.

### Cost safety as engineering, not intention

This ran on a student's promotional credits, so every bound is enforced in the event loop
via a Strands `HookProvider`: 8 model iterations, 25 tool calls, duplicate-call detection
by argument digest, 3 retries, a 120 s wall clock, and a 100-cell cap on route matrices
checked *before* any Location API call. A run that hits a bound terminates loudly as a
recorded `loop_fault` — never a silent truncation dressed up as success.

Infrastructure is serverless and destroyable, and `infra/test_stack.py` asserts against the
synthesized CloudFormation that the schedule ships disabled, DynamoDB is on-demand with a
TTL, logs expire in 14 days, and nothing always-on exists.

### Tech

Strands Agents SDK · Amazon Bedrock · Bedrock AgentCore Runtime · DynamoDB · EventBridge ·
Amazon Location (geo-routes) · Lambda + API Gateway · S3 + CloudFront · CDK · FastAPI ·
React + TypeScript.

## Challenges we ran into

- **A hook exception doesn't arrive as itself.** Strands wraps anything a hook raises in
  `EventLoopException`, so our `except BoundExceeded` never fired and a tripped safety bound
  was being recorded as a generic crash. We now walk the `__cause__` chain. Misclassifying a
  fired bound as an error hides exactly the signal you most need.
- **Token usage isn't where the type hints suggest.** It rides in
  `stop_response.message["metadata"]["usage"]`, not `stop_response.usage`. We read it per
  model call rather than from the final result, so an *aborted* run still records what it
  spent — and an aborted run is the one whose cost matters.
- **Our own agent looped, and the guard caught it.** A planner bug re-issued a terminal
  tool forever. The iteration cap stopped it and recorded a `loop_fault`. That was the
  safety net working — but a planner that needs the net every run is a bug, so we fixed the
  planner and added a regression test.
- **Making a dropout genuinely break the pool.** Early tuning left so much surplus demand
  that no single withdrawal mattered, which made the recovery demo hollow. We reshaped the
  supplier minimum and introduced a deliberate radius asymmetry — *form tight, repair
  wide* — so the failure is real and the repair has to find someone genuinely new.
- **No AWS credentials.** Everything cloud-facing is written, synth-verified, and
  unit-tested against recorded service shapes, but none of it has run live.

## What we learned

- Cost safety and testability turn out to be the same problem. Building a deterministic
  planner behind the Strands `Model` interface let the entire test suite and demo exercise
  the real agent loop for free — and cheap tests are the tests that actually get run.
- The interesting part of an autonomy boundary isn't the happy path, it's who gets
  disturbed when things change. "Don't silently reprice someone who already committed"
  taught us more about HITL design than any amount of prompt engineering.
- The strongest constraint we adopted was refusing to let the model produce numbers. It
  eliminated a whole category of failure before it could exist.

## What's next

- Deploy to AgentCore Runtime and publish the live demo (blocked only on account access)
- Smart Join editing in the UI
- A supplier portal and negotiated pool-specific offers
- Pickup-host compensation and reputation
- Longer term: consumer demand aggregation — Pool negotiating directly with distributors on
  behalf of verified aggregated demand

## Try it

```bash
git clone <repo> && cd pool
make install
make demo     # the whole scenario, printed
make test     # 219 tests
make dev      # API + web locally
```

No AWS account needed to run the demo: the default configuration uses an in-memory store,
deterministic routing, and an offline planner in place of the LLM. That planner replaces
the model *only* — the real Strands loop, tools, domain math, state machine, and approval
boundary all execute.

## Important disclosures

- **All data is synthetic.** Every household, supplier, price, and pickup site is invented.
  No real people, no customers, no traction.
- **No payments.** Pool models commitment, allocation, cost, and approval. No money moves;
  checkout is labelled as simulated.
- **Cloud deployment is unverified.** No AWS credentials were available during development.
  The infrastructure is written and synthesizes cleanly but has never been applied to a live
  account. The README carries a per-component status table.
- **Built with heavy AI coding assistance**, with every result validated by running it.

## Built with

`strands-agents` `amazon-bedrock` `bedrock-agentcore` `dynamodb` `eventbridge`
`amazon-location-service` `aws-lambda` `api-gateway` `cloudfront` `aws-cdk` `python`
`fastapi` `react` `typescript` `vite`
