# Devpost submission draft

Draft copy for the submission form. Every claim here must be true at the moment of
submission — check the status table at the bottom before pasting anything.

---

## Tagline

**Pool notices when nearby people could save by buying together, then does the
coordination needed to make it actually happen.**

## Track

Good Neighbor Agents. The value is structurally collective: one person alone cannot
create it.

---

## Inspiration

This already happens on every campus, and it always goes the same way:

> "I can buy 50 tubs of protein powder way cheaper than the store. DM me if you want one."

It works, badly. One person guesses the demand, fronts their own money, buys stock before
anyone has committed, then answers thirty messages, chases payment, arranges meetups, and
eats the leftovers. They aren't paid for any of it, so it happens once and stops.

The software isn't what's missing. What's missing is that the *coordination labour* is
unpaid, tedious, and lands on one exhausted volunteer.

That labour is exactly what an agent is for:

- **The opportunity is latent, not stated.** Nobody said "let's buy protein powder
  together". Eight people separately said they buy it monthly. Discovering that a viable
  group *could* exist means searching a space nobody asked about.
- **Feasibility is multi-constraint and moves.** Supplier minimums, case sizes, budget
  ceilings, substitution tolerance, timing windows, who can carry thirty kilos, who's
  free on Saturday.
- **Failure is normal.** A card declines at 90% commitment. What to do next depends on
  the specific pool, the specific shortfall, and who could plausibly fill it.
- **Most of it should never reach a human at all** — and the bits that do should arrive
  already worked out.

## What it does

People declare what they routinely need. Pool does the rest:

1. **Finds latent overlap** — community-scoped, verification-gated, timing-aware.
2. **Evaluates real supply** — supplier minimums, case structure, quote freshness.
3. **Recruits fulfilment** — from standing hosts *and* pool members who volunteer,
   ranked deterministically on the whole transaction.
4. **Computes the complete landed price** — merchandise + host pay + card processing +
   Pool's fee. Nothing hidden.
5. **Respects each person's own rules** — Smart Join authorises within stated limits;
   everyone else gets one question with the answer already worked out.
6. **Recovers from failure** — when an authorisation fails, it finds compatible
   replacement demand that fills the gap exactly.
7. **Locks only when it works for everyone** — buyer, supplier, host, and Pool.
8. **Proves the handoff** — one-time pickup credentials, stored as hashes, single use.

**Nobody creates the group. Pool discovers that the group can exist.**

## How I built it

**Strands is load-bearing.** The agent loop — which opportunity to investigate, whether
to recruit a host, which recovery to attempt, when to stop — runs through Strands, with
twelve narrow typed tools and no shell or arbitrary query escape hatch.

**The central rule:** the model decides *what to do*; deterministic code decides *what is
true*. The model may choose to investigate a product. It may never invent a price, a
quantity, an eligibility, or a viability verdict. Every number that reaches a human came
from a tool.

**A pure domain layer.** `domain/` performs no I/O and imports no adapter. Economics,
viability, Smart Join, host ranking, timing, case fitting, and the state machine are pure
functions — which is why the whole thing is testable without fixtures and why swapping in
DynamoDB or Stripe changes nothing about what a price is.

**AWS, used where it earns its place:** Bedrock for inference, AgentCore Runtime to host
the agent, DynamoDB as authoritative state, API Gateway + Lambda, S3 + CloudFront,
EventBridge for the background scan (created disabled), Amazon Location for routing,
CloudWatch for run records.

**Bounded by construction.** Iterations, tool calls, duplicate calls, wall clock, and
route-matrix size are enforced in the event loop as a hook provider — not by asking the
model nicely. Every run terminates in a recorded outcome.

## Challenges

**Case rounding nearly broke the honesty of the whole thing.** Suppliers sell cases;
demand doesn't divide evenly. The tempting fix is to buy the extra units and spread the
cost. That is exactly the speculative-inventory problem the product exists to remove. So
Pool solves it properly: a bounded exact search picks the buyer set whose quantities fill
whole cases, preferring people whose need is already due over demand pulled forward. If no
combination lands on a boundary, the pool doesn't lock, and it says why.

**The fee and the processing charge are both circular if you're careless.** The platform
fee is a share of savings, but savings depend on the total, which includes the fee. And
card processing is charged on the amount you charge — including the processing. Both are
resolved deterministically: the fee is defined against *gross* savings, and processing is
grossed up per buyer so the charge covers the processor's cut of that charge. Computing
processing the naive way under-recovers by a few cents per buyer — a silent platform
subsidy, which is the thing the model is not allowed to do.

**Recovery over-recruited.** The first version treated any funding gap as demand to
replace, including buyers who simply hadn't answered yet. It filled a hole that wasn't
there and left the pool oversubscribed — trading a funding problem for surplus stock. The
fix was to distinguish demand that is *lost* from demand that is *pending*, and to require
replacements that sum to exactly the gap.

**The agent needed to see the consequences of its own actions.** A planner that reads the
work queue once, acts, and then decides from a stale view will never notice that the pool
it just repaired has become lockable. It re-reads after acting — capped, so alternation
never becomes polling.

## What I learned

The interesting boundary in an agent product isn't "can the model do it". It's **which
decisions must never be the model's**. Writing that boundary down as two columns — what
the model may decide, what deterministic code must determine — turned out to be the single
most useful design artifact in the project. It made the tool surface obvious, it made the
tests obvious, and it's the reason a wrong price is structurally difficult rather than
merely unlikely.

The second thing: **an agent that does nothing is often correct.** A pool whose bulk price
barely beats retail should bother nobody. Building "found nothing worth doing" as a
first-class recorded outcome — rather than a failure — changed how the whole loop reads.

## What's next

- Cloud verification: real Bedrock inference, AgentCore deployment, a live demo URL.
- Stripe TEST-mode verification against Stripe's actual servers.
- A controlled pilot in one dense community: operator-entered verified offers, a founder
  fallback fulfiller, a hard cap on order value.
- The unresolved questions are legal, not technical — merchant of record, custody of buyer
  funds, host classification. They're written down in `PILOT_READINESS.md` rather than
  guessed at in code.

---

## Built with

`python` · `strands-agents` · `amazon-bedrock` · `bedrock-agentcore` · `aws-lambda` ·
`amazon-dynamodb` · `amazon-api-gateway` · `amazon-eventbridge` · `amazon-location-service` ·
`amazon-s3` · `amazon-cloudfront` · `aws-cdk` · `fastapi` · `react` · `typescript` ·
`stripe` · `vite`

---

## Honesty checklist — verify before submitting

| Claim | Status when written |
| --- | --- |
| Strands is load-bearing | **True.** The real event loop, twelve real tools. |
| Bounded agent loop | **True.** Enforced in hooks, covered by tests. |
| Deterministic truth boundary | **True.** `domain/` has no I/O; tests assert the behaviour. |
| End-to-end lifecycle works | **True locally.** `make demo`, and asserted by tests. |
| Payments | **Simulated, or Stripe TEST.** Stripe refuses non-test keys. Never verified against Stripe's servers. |
| Supplier purchase | **Simulated.** Every record flagged. No supplier contacted. |
| Bedrock inference | **Implemented, NOT verified.** No credentials were configured. |
| AgentCore deployment | **Implemented, NOT deployed.** |
| DynamoDB | **Implemented, NOT verified live.** Pinned by a fake-client test. |
| Amazon Location | **Implemented, NOT verified.** |
| Live demo URL | **Does not exist yet.** |
| Users, savings, traction | **None. All data is synthetic.** |

Do not describe anything in the bottom half as working until it has been observed
working. Update this table, then the copy — in that order.
