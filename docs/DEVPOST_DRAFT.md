# Devpost submission draft

Draft copy only. Recheck every claim against the deployed commit immediately before
submission.

## Tagline

**Pool notices when people in one community could save by buying together, then does the
coordination needed to make a viable transaction.**

## Track

Good Neighbor Agents. The value is structurally collective: one person alone cannot
create it.

Pool is designed as recurring purchasing infrastructure for existing communities. A
campus is the first wedge; apartment buildings, neighbourhoods, workplaces and community
organisations have the same useful ingredients: a membership boundary, recurring needs,
and possible shared pickup sites. The Community enables the setting; Pool coordinates;
members choose and collect.

## Inspiration

Informal bulk buying already happens:

> “I can buy 50 tubs of protein powder much cheaper than the store. Message me if you
> want one.”

It works badly. One volunteer guesses demand, fronts money, buys speculative stock,
answers messages, tracks commitments, arranges handoffs and absorbs whatever is left.
The coordination labour is tedious, risky and usually uncompensated.

That labour is a good agent problem:

- **The opportunity is latent.** People state individual recurring needs; nobody first
  notices and organises the group.
- **Feasibility moves.** Minimums, cases, budgets, timing, substitution authority,
  pickup capacity and host availability must all line up.
- **Failure is normal.** A declined authorization should trigger a bounded, specific
  repair rather than a broadcast to the group.
- **Attention is expensive.** Most decisions should never reach a person; consequential
  exceptions should arrive already worked out.

## What it does

People declare what they routinely need. Pool then:

1. finds compatible latent demand inside one Community;
2. evaluates supplier minimums, case structure and quote freshness;
3. creates a candidate pool with estimated terms and no financial commitment;
4. ranks eligible hosts and offers the job to one candidate;
5. refreshes the quote and computes the exact landed price only after host acceptance;
6. evaluates each member's deterministic Smart Join policy or asks for approval;
7. repairs lost demand with compatible replacement demand that fills the exact gap;
8. locks only after buyer, host, supplier and platform viability all pass;
9. records a simulated capture and supplier order; and
10. proves handoffs with hashed, one-time pickup credentials.

**Nobody creates the group. Pool discovers that the group can exist.**

## How I built it

**Strands is load-bearing.** The coordinator uses a real Strands event loop to choose
which of twelve typed tools to call, whether an opportunity deserves investigation,
which bounded recovery to attempt, and when to stop. It has no shell, arbitrary SQL or
generic mutation.

**The central boundary:** the model decides *what to do*; deterministic code determines
*what is true*. Money, quantities, eligibility, timing, package fitting, policy verdicts,
state transitions and final viability never come from model prose. Tool results are the
values stored and shown to people.

**Two paths, and the difference is stated everywhere it appears.**

*The public self-test* — the one at `/verify`, the one a judge drives — runs on deployed
**AWS Lambda** and **DynamoDB**, executing the real Strands coordinator loop against a
**deterministic offline planner**. That is a deliberate choice, not a shortfall: it makes
every judge's run reproducible and costs them no model tokens, and the function serving it
holds no permission to call a model at all. Saving a declaration writes a durable
coordination event; one bounded run answers it in-process; the surface afterwards labels
the provider it actually ran on and counts *planner iterations* at zero tokens.

*The live agent path* — a separate, explicitly requested action — goes browser → Lambda →
**Amazon Bedrock AgentCore Runtime** → Strands → **Amazon Bedrock Nova Lite** → the same
typed tools → the same deterministic services → the same DynamoDB state. We deployed that
Strands agent to AgentCore and verified Nova Lite against the same table and the same tool
contracts.

**Both paths are causal and inspectable.** Candidate-pool creation stores
`created_by_run`. The API reads that exact pool and run back from the same workspace and
displays their ids, tool sequence, outcome and termination. It never assumes the latest
run created the first pool, and there is no code path that fabricates a run.

**What the visible public trace shows is the implemented causal result**, and it is the
same on either path because the tools and the domain are the same: heterogeneous demand,
a coarse option that looks strongest on the facts available, a deterministic refusal on
landed economics that no prompt can talk past, a second cohort investigated in response,
and a provisional group order that fills whole cases with nothing left over.

**The domain is pure.** `domain/` performs no I/O and imports no adapter. Economics,
viability, Smart Join, timing, host ranking, matching and case fitting can therefore be
tested without cloud services.

**Runs are bounded.** The deployed loop allows at most 8 iterations, 25 tool calls and 2
identical calls. Its 45-second wall-clock bound is cooperative: checked between model and
tool steps, not falsely described as an interrupt for a call already in progress. The
AgentCore bridge and Lambda provide outer 60- and 90-second deadlines.

## Challenges

**No speculative surplus.** Supplier cases rarely divide evenly into demand. Pool uses a
bounded exact search for a buyer set whose requested quantities fill whole cases,
preferring needs already due. If no exact allocation exists, the pool does not lock.

**Exact landed economics are easy to get subtly wrong.** The platform fee depends on
savings, while processing depends on the amount charged. Pool defines the fee against
gross savings and grosses up processing per buyer in integer cents, preventing a silent
platform subsidy.

**Recovery must replace lost demand, not pending demand.** An early implementation
over-recruited because it treated unanswered authorizations as missing units. The state
model now distinguishes pending from lost and admits replacements only for the exact lost
gap.

**Shared cloud state needed explicit causality and concurrency.** The public Lambda and
AgentCore runtime use the same DynamoDB table. Per-workspace leases serialize mutating
coordinators, idempotency claims prevent duplicate pools, and stored `created_by_run`
proves which runtime execution produced which visible record.

## What I learned

The useful question in an agent system is not “can the model do this?” It is “which
decisions must never be the model's?” Writing that boundary down made the tool surface,
authorization semantics and tests much clearer.

An agent doing nothing can also be correct. A pool whose complete landed price is not
worthwhile should bother nobody, so “no action” is a first-class recorded outcome.

## What's next

- one controlled pilot with synthetic rehearsal first, then operator-entered verified
  offers and strict order-value limits;
- a merchant-of-record and funds-custody decision before any real purchasing;
- a real host payout design before calling recorded compensation “paid”;
- Stripe TEST-server verification; and
- real Community verification and pickup permission workflows without implying an
  institutional partnership before one exists.

## Built with

Deployed: Python, Strands Agents SDK, AWS Lambda Function URL, Amazon DynamoDB, Amazon
CloudWatch, FastAPI, React, TypeScript, Vite and AWS CDK — carrying the public self-test,
which runs the Strands loop against a deterministic planner. Amazon Bedrock AgentCore
Runtime and Amazon Bedrock (Nova Lite) are deployed and verified live alongside it, and
carry the live agent action against the same DynamoDB state and the same bounded tools.

Implemented but not deployed on the judge path: API Gateway, S3, CloudFront, EventBridge,
the Amazon Location `geo-routes` adapter, and a Stripe TEST-only adapter. The deployed
account has zero EventBridge rules. Routing, payments and the supplier purchase shown in
the demo are simulated.

## Honesty checklist — verify before submitting

| Claim | Current evidence |
| --- | --- |
| Strands is load-bearing | **Tested and deployed.** The coordinator runs through Strands and twelve typed tools. |
| Bounded agent loop | **Tested and deployed.** Bounds and repeated-call faults have executed tests. |
| Deterministic truth boundary | **Tested.** Domain and service suites assert money, policy, matching, state and viability. |
| End-to-end lifecycle | **Tested and deployed.** The deterministic 13-stage scenario was observed against the public DynamoDB-backed demo. |
| Same-run discovery proof | **Deployed and rehearsed.** One Product invocation created one pool whose stored `created_by_run` matched the displayed run after the full lifecycle. |
| Payments | **Simulated in the demo.** Stripe adapter accepts TEST keys only; Stripe servers have not been verified. |
| Host compensation | **Computed and recorded; not paid out.** No payout rail exists. |
| Supplier purchase | **Simulated.** Every purchase record is flagged; no supplier is contacted. |
| Bedrock inference | **Verified live 2026-08-22** with Nova Lite through Strands, reached via AgentCore — `us.amazon.nova-lite-v1:0`, 2 of 8 iterations, 5,513 in / 133 out tokens, terminated `completed`. The **outcome was a truthful `no_action`**: the member's only declaration had already been served by the in-process run their save caused, so the objective was correctly empty. It establishes the deployment, the tool surface and the bounds on real infrastructure. It is **not** a live trace of the Kestrel→Harbourstone adaptation, and must never be described as one. |
| AgentCore Runtime | **Deployed and verified live 2026-08-22**, `READY` in `us-east-1`, running the current release. |
| The public `/verify` trace | **Produced by the deterministic offline planner**, on deployed Lambda + DynamoDB, inside the real Strands loop. Zero model tokens. Never to be presented as Nova output. |
| Lambda Function URL | **Deployed and verified 2026-08-22** as the public same-origin web/API surface, running the current release. |
| DynamoDB | **Deployed and verified 2026-08-22** as authoritative shared workspace state. |
| EventBridge | **Implemented only in an un-deployed pilot stack; zero deployed rules.** |
| Amazon Location | **Adapter implemented; live service unverified and absent from judge path.** |
| Public demo URL | **Deployed and observed.** Recheck in a private browser before submission. |
| Users, savings, traction | **None claimed.** All people, suppliers, needs and impact figures are synthetic. |

Do not copy this draft into Devpost until the final rehearsal, video, public repository
and human-only submission checks are complete.
