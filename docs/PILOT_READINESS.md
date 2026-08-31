# Pilot readiness

What would have to be true before Pool coordinated a purchase for real people with real
money — and what is deliberately unresolved.

The point of this document is to keep two things apart: **things that are a coding task**
and **things that are a decision**. Guessing at the second category and writing the guess
into the code would be the worst outcome, because it would look settled.

Status vocabulary, used precisely (AGENTS.md):

| Term | Means |
| --- | --- |
| **Ready** | Implemented and covered by executed tests. |
| **Needs configuration** | The code path exists; it needs credentials, keys, or values. |
| **Needs legal / operations review** | A decision, not an implementation. Do not encode a guess. |
| **Not implemented** | Deliberately absent. |

---

## Ready

Implemented, and verified by tests that were actually run.

| Area | Evidence |
| --- | --- |
| Community model, membership as a separate entity, multi-community schema | `test_matching.py`, `test_persistence_and_termination.py` |
| Verification abstraction (demo + email-domain providers) | `test_adapters.py` |
| Recurring needs with restock lead and authorised-early windows | `test_timing.py` |
| Latent-demand discovery, community-scoped, verification-gated | `test_matching.py` |
| Structured substitution policies | `test_matching.py` |
| Exact-cent arithmetic, largest-remainder splits | `test_money.py`, `test_economics.py` |
| Complete landed economics with processing gross-up | `test_economics.py` |
| Case fitting — no speculative surplus | `test_economics.py`, `test_coordination.py` |
| Host evaluation, ranking, offer/accept/decline/expire | `test_hosting.py`, `test_coordination.py` |
| Host compensation, earned vs contingent | `test_economics.py`, `test_fulfillment.py` |
| Central viability engine, both stages | `test_viability.py` |
| Smart Join three-verdict boundary | `test_policy.py` |
| Payment state machine, idempotency, failure recovery | `test_payments.py`, `test_coordination.py` |
| Webhook signature verification, replay rejection | `test_payments.py` |
| Simulated purchase with provenance | `test_fulfillment.py` |
| One-time pickup credentials, single use, re-issue invalidation | `test_fulfillment.py` |
| Operator override with mandatory reason and audit | `test_fulfillment.py` |
| Exception-driven communication and privacy boundaries | `test_communication.py`, `test_api.py` |
| Bounded agent loop | `test_agent_bounds.py` |
| End-to-end lifecycle | `test_demo_scenario.py` |

---

## Needs configuration

Some of this has since been run against a real account and some has not. The table says
which, because the distinction is the whole value of this document.

### AWS

| Item | Status | What is needed |
| --- | --- | --- |
| Non-root IAM identity | ✅ done | An IAM user or role with the deploy permissions. Never root access keys. |
| Bedrock model access | ✅ verified | Model access granted in the region, then `BEDROCK_MODEL_ID` set to an inference profile the account actually has. |
| First real inference | ✅ verified | `make verify-bedrock`, then `make verify-recovery` for the consequential branch. |
| DynamoDB | ✅ verified | `POOL_REPOSITORY=dynamodb`. The full lifecycle has run on a real table. |
| AgentCore Runtime | ✅ verified | `agentcore deploy` (official `@aws/agentcore` CLI; config in `agentcore/`). Requires a CDK bootstrap in the account first. |
| Public judge demo | ✅ verified | `make deploy-demo` — one Lambda, one Function URL, one table. A CloudFront distribution in front of the Function URL is **implemented and not yet deployed** (#0065): `*.lambda-url.*.on.aws` is blocked as a category by filtered resolvers. |
| Amazon Location | ⬜ never called | `ROUTING_PROVIDER=aws_location`. Uses `geo-routes`, so no calculator resource to provision. |
| EventBridge background scan | ⬜ never enabled | Ships **disabled**. Enabling it starts recurring model invocations. |
| Pilot-shaped stack (API Gateway, S3, CloudFront) | ⬜ never deployed | `make deploy` then `make deploy-web`. The public demo needs none of it — note that the demo stack now has a CloudFront distribution of its own, for reachability rather than for hosting, and it is a separate resource in a separate stack. |

Verification order and the exact commands are in the README and `docs/COST_NOTES.md`.

### Stripe

| Item | What is needed |
| --- | --- |
| TEST keys | `STRIPE_API_KEY=sk_test_…` and `STRIPE_WEBHOOK_SECRET=whsec_…`, set out of band — never in a CDK stack. |
| Saved payment methods | The SetupIntent path is implemented; the current official docs should be re-checked before a pilot relies on it. |
| Manual capture | The PaymentIntent manual-capture flow is implemented against Stripe's documented shapes but has never touched Stripe's servers. |
| Webhook endpoint | Signature verification is implemented from Stripe's documented scheme using only `hmac`; the endpoint needs registering. |

The Stripe provider **refuses to construct with anything but a `sk_test_` key**, with no
override. A misconfigured environment fails loudly rather than charging a real card.

---

## Needs legal / operations review

These are the real blockers. None of them is a coding problem, and encoding a guess would
make an unsettled question look settled.

### Money

- **Merchant of record.** Who is the seller? Pool, the supplier, or the buyers as a
  collective? This determines nearly everything below.
- **Custody of buyer funds.** Funds are captured before the supplier is paid. Holding
  other people's money has regulatory consequences that vary by jurisdiction.
- **Supplier payment mechanism.** Who pays the wholesaler, with what instrument, on what
  terms? `PurchaseExecutor` is a seam precisely because this is undecided.
- **Host payouts.** Stripe Connect test-mode transfers are documented as future work. Live
  payouts need identity verification and tax reporting.
- **Sales tax.** Rate, nexus, and who remits — all downstream of merchant of record.
- **Refunds and disputes.** A chargeback on a completed group order has no obvious owner
  today.
- **Marketplace obligations.** Facilitator rules may apply depending on the structure
  chosen.

### People

- **Host classification.** Contractor or something else? This affects pay structure,
  insurance, and tax.
- **Host identity verification.** Someone is collecting hundreds of dollars of goods
  belonging to other people.
- **Liability and insurance.** Goods damaged, lost, or mishandled in transit.
- **Food and product regulation.** Even sealed consumer goods have handling and storage
  rules; anything perishable is out of scope by design.

### Places

- **Pickup permission.** Every pickup site in this build is marked `DEMO`. A real
  university space is not authorised for commercial pickup because a database says
  `VERIFIED` — that is a conversation with a building.
- **Institutional relationship.** Verifying an email domain proves control of an address.
  It is not an endorsement, and must never be presented as one.

### Goods

- **Unclaimed goods.** The lifecycle stops at `UNCLAIMED` and operator review on purpose.
  What actually happens to an uncollected paid-for item after a secondary window is a
  policy question with legal edges.
- **Returns and recalls.** `IssueCase` records the problem and routes it to an operator.
  The resolution process is deliberately not automated.

### Documents

- Terms of service, privacy policy, host agreement, supplier agreement. None exist.

---

## Not implemented

Deliberately absent rather than stubbed. A stub that looks callable is the kind of thing
that gets called by accident.

| Item | Why |
| --- | --- |
| Institutional SSO verification | Requires the institution's agreement. |
| Account authentication | Judge Mode needs none. Cognito is the likely fit and is kept separate from Community membership by design. |
| Live retailer scraping | Brittle, expensive, and not the interesting claim. The thesis is aggregated demand, not finding coupons. |
| Supplier self-service portal | Operator-entered offers are the realistic cold start. |
| Stripe Connect host payouts | Secondary to the buyer flow. An internal compensation ledger exists instead. |
| Multi-hub fulfilment | One pool, one fulfiller in v1. `FulfillmentRun` holds a list so batching stays possible. |
| Cross-community pooling | Out of scope; pools form within a Community. |
| Operator-placed and supplier-direct purchase executors | Both need the merchant-of-record decision first. |

---

## Concurrency: what is serialised, and what is not

Worth stating precisely, because the honest answer is "most of it, and deliberately not
all of it".

**Serialised today.** Every coordinator that scans-then-writes a workspace takes one
conditional-write lease keyed by that workspace: first-load seeding, reset, the showcase
scenario, a local coordinator run, and the live AgentCore invocation. Two of those can
no longer interleave, on one machine or across Lambda containers. The writes the lease
protects are *also* conditional where a duplicate would be visible — candidate-pool
creation claims its idempotency key, and pickup redemption claims its credential — so
the invariant does not rest on the lease alone.

**Not serialised, and a pilot blocker.** Participant actions — answering a decision,
withdrawing, volunteering to host, opening distribution, issuing or redeeming a pickup
credential, declaring a need — do **not** take the lease. That is a deliberate trade for
the demo: the lease can be held for the length of a live agent run, and refusing a
member's own action for that long would break the product to protect it.

The residual race is real and narrow. `issue_final_offer` reads its membership set once;
a withdrawal landing after that read is included in the offer and its state overwritten.
It needs genuine concurrency — two tabs, or a script — and the synthetic demo has no
money in it. For real users it is not acceptable, and the fix is not a wider lease:

- entity version numbers on `Membership`, `Pool`, and `PaymentRecord`, with conditional
  writes that fail on a stale read, so a lost update is an error rather than silence;
- a transaction around the final-offer write set, so membership and economics commit
  together or not at all.

That is the entity-versioning work listed under **Not implemented**. It touches the
domain broadly, which is why it belongs to pilot readiness rather than to a submission
freeze — but it is a blocker for real money, not a nice-to-have.

---

## Would a pilot require rewriting the core?

No — and that was the design constraint. The seams that would move are all adapters:

```
PaymentProvider      simulated → Stripe TEST → Stripe live
PurchaseExecutor     simulated → operator-placed → supplier-direct
SourcingProvider     synthetic → manually verified → supplier portal
VerificationProvider demo → email domain → institutional SSO
Repository           in-memory → DynamoDB
RoutingService       deterministic → Amazon Location
Model                offline planner → Bedrock
```

The domain layer — economics, viability, policy, hosting, timing, state — has no I/O and
would not change at all. That is the whole reason it is shaped that way.

What a first controlled pilot would actually look like: one dense Community, explicit
membership rules, operator-entered verified offers, a founder available as the fallback
fulfiller, and a hard cap on order value. The buyer side is the part being validated;
everything else is scaffolding until it works.
