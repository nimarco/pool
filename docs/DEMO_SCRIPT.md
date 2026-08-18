# Demo rehearsal script — about 4:50

This is a navigation and timing rehearsal, not a final word-for-word voiceover. The
presentation pass happens later.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

The defining technical rule is equally simple:

> **One live AgentCore invocation.** The `Find opportunities` run is the same stored run
> shown later under `Technical proof for this run`. Never invoke the runtime again in the
> recording.

## Before recording

1. Run `make qa` and the release checks.
2. Use the deployed URL, open a fresh disposable workspace, and reset Demo University.
3. Confirm the drawer says: discovery uses AgentCore / Bedrock; the lifecycle uses the
   deterministic planner; payments and supplier ordering are simulated.
4. Leave the Product on **Needs**, signed in as Rosa.
5. Keep one continuous browser journey. A short edit over the real AgentCore wait is
   fine; switching to a different run or workspace is not.

## 0:00–0:18 — The input is a recurring need

**Product → Needs → Rosa's whey declaration → Change.**

Establish only the product inversion: Rosa states what she buys anyway. She does not
create a group, invite anyone, or know who else wants it.

## 0:18–0:37 — Change one real constraint

**Change minimum savings from 20% to 21% → Save.**

The saved declaration is re-read from the server. This makes the later opportunity an
answer to current stored preferences, not a pre-rendered scenario.

## 0:37–0:55 — Independent latent demand

**Go to Home.**

Point to the standing needs and convergence figure. Each member declared independently;
no member noticed or organised the overlap.

## 0:55–1:18 — One live discovery run

**Click `Find opportunities` exactly once.**

The wait state should say that Pool's coordinator is running on Amazon Bedrock AgentCore
against this demo session's DynamoDB workspace. Show roughly three seconds of the honest
wait, then cut or fast-forward. Resume only when that same request returns.

Do not open Showcase's live page and do not press `Run again` later.

## 1:18–1:38 — The resulting pool

**Open the opportunity returned by that run.**

Show 10 people, 24 units, and the whole-case result with no speculative surplus. The pool
exists because the live coordinator created it, not because the browser drew a result.

## 1:38–1:58 — Host first, then final terms

**Demo University drawer → Gio accepts the fulfilment job → Let Pool work the queue.**

Offering to host did not claim the job: Pool ranked candidates and offered it to the best
eligible one. Only after acceptance can host compensation enter the exact buyer price.

## 1:58–2:24 — Exact economics

**Pool → Economics.**

Show the final ledger: $861.44 all-in versus $1,127.76 retail, $266.32 collective
savings, after merchandise, host compensation, processing and Pool's fee. Say that these
figures are deterministic outputs. Payments and the supplier order are simulated.

## 2:24–2:50 — Failure retained, recovery visible

**Pool → People.**

Show 10 buyers and 11 memberships on the record: one exact-amount authorization failed,
the failed membership remains visible, and one compatible replacement restores exactly
24 units. Do not say the failed buyer paid.

## 2:50–3:20 — Decisions, lock, order, pickup

Use only the existing drawer controls:

1. remaining buyers answer their questions;
2. let Pool work the queue;
3. open the pickup window;
4. everyone collects their order.

These controls call participant and scheduler endpoints; they do not set lifecycle state
directly. Authorizations, simulated captures, the simulated supplier order, and one-time
handoff credentials remain distinct.

## 3:20–3:42 — Fulfilment completes

**Pool → Fulfilment.**

Show 10/10 handoffs. Host compensation is earned and recorded in the simulated
transaction; Pool does not claim that a payout rail exists.

## 3:42–4:20 — Same-run technical proof

**Pool → Activity.** Briefly show the stored recovery event, then click
**`Technical proof for this run`**.

Show, without invoking anything:

- Amazon Bedrock AgentCore Runtime live, region, model provider and model;
- the exact run id and resulting pool id;
- `Pool created_by_run`, equal to that run id;
- the exact stored tool sequence, outcome and termination;
- authoritative run + pool readback from the same workspace;
- browser → Lambda → AgentCore → Strands / Bedrock → typed tools → deterministic
  services → DynamoDB → browser.

`Run again` is collapsed and secondary. Do not open it.

## 4:20–4:50 — Community infrastructure and impact

**Community.**

Close on the visible model:

> **Community enables → Pool coordinates → Members choose and collect.**

Pool is designed as recurring purchasing infrastructure for existing communities: a
campus, apartment building, neighbourhood, workplace or community organisation can
supply a membership boundary and possible pickup sites. Pool remains responsible for
demand discovery, viable economics, host coordination and transaction state. Demo
verification and pickup permissions are synthetic and imply no institutional
partnership.

End with the collective outcome, not feature inventory:

> The buyers get viable bulk economics without organising the group. The host earns
> recorded compensation for the fulfilment work represented in the workflow. The
> supplier receives one clean bulk order. Nobody organised the group. Pool noticed.

## Continuity rules

- One workspace, one `Find opportunities` click, one live AgentCore invocation.
- A video cut may shorten the wait; it must not replace the run or its result.
- Never say “deployed,” “paid,” “captured,” “final,” or “permission” more strongly than
  the screen supports.
- Never say a number not visible on screen.
- If the live call fails, keep the honest failure visible and stop the rehearsal. Do not
  spend a second invocation trying to manufacture a clean take.
- Do not record until the rehearsal confirms the exact run id, pool id and
  `created_by_run` relationship survive the entire journey.

## Backup

`make demo` produces a deterministic lifecycle transcript from the same domain and tool
code. It is a truthful fallback for explaining the lifecycle, but it is not a substitute
for the single live discovery proof required by the primary recording.
