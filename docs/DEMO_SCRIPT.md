# Demo rehearsal script — about 4:45

This is a navigation and timing rehearsal, not a final word-for-word voiceover. The
presentation pass happens later.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

The defining technical rule is equally simple:

> **One live AgentCore invocation.** The `Run Pool now` run is the same stored run shown
> later under `Technical proof for this run`. Never invoke the runtime again in the
> recording.

## Before recording

1. Run `make qa` and the release checks.
2. Use the deployed URL, open a fresh disposable workspace, and reset Demo University.
3. Confirm the drawer says: discovery uses AgentCore / Bedrock; the lifecycle uses the
   deterministic planner; payments and supplier ordering are simulated.
4. Leave the Product on **Home**, signed in as Rosa. A fresh reset gives her one standing
   need (paper towels) and **no whey declaration** — she makes that one on camera, which is
   the whole opening.
5. Keep one continuous browser journey. A short edit over the real AgentCore wait is
   permitted but no longer wanted — see 0:52. Switching to a different run or workspace
   is never permitted.

## 0:00–0:20 — Tell Pool something you buy

**Product → Home.**

Rosa's home screen opens on one instruction and one box: *Anything else you buy
regularly?* Type `vanilla whey`.

Four products appear with their actual photographs. Pick the Optimum Nutrition tub. This
is the whole point of the opening — she said what she buys in her own words, recognised
the thing, and tapped it. She never saw a product code, a supplier, or a minimum order.

Say once, over the results: these are real products from a public catalogue; the supplier
prices later in the demo are invented, and the app says so on its About page.

## 0:20–0:36 — The two questions that matter

**The form opens on the chosen product.**

Two tubs, about every 30 days, needed in a fortnight — and the one line that does real
work: *Pool may buy any time in the 14 days before that, if it saves money.* That window
is permission, and it is the exact constraint the coordinator consults minutes later when
it pulls two other people forward.

Open **Fine-tune when Pool may act on this need** once to show the savings floor and spend
ceiling exist and are already set. Close it again. Save.

Say plainly: that saved nothing to anybody's card, created no group, and invited nobody.

## 0:36–0:48 — Thirty-three declarations, no groups

**Needs → `Show all 33`.**

Rosa's new declaration is now one row among thirty-three, made by twenty-four people who
have never spoken to each other. This is the premise, and it is the one thing the
interface cannot say in a sentence.

## 0:48–0:56 — Independent latent demand

**Go to Home.**

The convergence figure, and one line: nobody chose the same week, their restocks did.
Do not read the expanded arithmetic aloud; it is behind a disclosure for that reason.

## 0:56–1:14 — One live discovery run

**Click `Run Pool now` exactly once.**

Say the honest version of this button, because the screen already does: in the real
product Pool watches these declarations on the community's pool day; nothing is scheduled
in the demo account, so the coordinator starts when you press it.

Hold the wait. It names Amazon Bedrock AgentCore, names the region, runs a real elapsed
clock, resolves the one thing the browser actually observed — that it sent the request —
and says on screen that nothing between is being animated. Roughly seventeen seconds of
that is the strongest AWS evidence in the recording, and cutting it throws that away.

Do not open Showcase's live page and do not press `Run again` later.

## 1:14–1:34 — The resulting pool, from her side

**Stay on Home.**

The card is scoped to Rosa: her two tubs, about $71.93 against $93.98 buying alone, with
nine others, collecting from North Hall lobby. The tail says **Not final yet — a
fulfiller's pay is part of the price**, which is the invariant, not a missing number.

The pool exists because the live coordinator created it, not because the browser drew a
result.

## 1:34–1:54 — Host first, then final terms

**Demo University drawer → Gio accepts the fulfilment job → Let Pool work the queue.**

Offering to host did not claim the job: Pool ranked candidates and offered it to the best
eligible one. Only after acceptance can host compensation enter the exact buyer price,
which is why the estimate above was labelled an estimate.

## 1:54–2:12 — The one question, and why it was asked

**Home.**

Rosa is asked to approve $71.83 against $93.98. Under it, in the policy engine's own
words: *member is on Ask Me — commitment requires explicit approval*. Answer it.

Then point at the strip below: **things Pool did on its own**, **times it had to ask a
person**. Eight of the ten buyers were never asked at all.

## 2:12–2:36 — Exact economics

**Pool → Economics.**

Show the final ledger: $861.44 all-in versus $1,127.76 retail, $266.32 collective
savings, after merchandise, host compensation, processing and Pool's fee. Say that these
figures are deterministic outputs. Payments and the supplier order are simulated.

## 2:36–3:00 — Failure retained, recovery visible

**Pool → People.**

Show 10 buyers and 11 memberships on the record: one exact-amount authorization failed,
the failed membership remains visible, and one compatible replacement restores exactly
24 units. The per-buyer chips say which rows Pool decided for and which it asked. Do not
say the failed buyer paid.

## 3:00–3:24 — Lock, order, pickup

Use only the existing drawer controls:

1. let Pool work the queue;
2. open the pickup window;
3. everyone collects their order.

These controls call participant and scheduler endpoints; they do not set lifecycle state
directly. Authorizations, simulated captures, the simulated supplier order, and one-time
handoff credentials remain distinct.

## 3:24–3:40 — Fulfilment completes

**Pool → Fulfilment.**

Show 10/10 handoffs. `Show my code` issues the signed-in member's own one-time
credential. Host compensation is earned and recorded in the simulated transaction; Pool
does not claim that a payout rail exists.

## 3:40–4:18 — Same-run technical proof

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

One optional sentence, if the take has room: the deterministic planner and the model
choose different tool paths through the same twelve tools, which is what makes the model
load-bearing rather than decorative.

## 4:18–4:45 — Both currencies, and the close

**Community.**

The page opens on the two things that matter and nothing else: **$1,127.76 → $861.44 →
$266.32 kept in the community**, and directly under it **what it cost anyone in
attention** — actions Pool took on its own, times it had to ask a person, commitments
made without asking.

Below that, the visible model:

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

- One workspace, one `Run Pool now` click, one live AgentCore invocation.
- The real wait is content, not dead air. Hold it rather than cutting it; if the take
  must be shortened, a cut may not replace the run or its result.
- Never say “deployed,” “paid,” “captured,” “final,” or “permission” more strongly than
  the screen supports.
- Never say a number not visible on screen. In particular, an estimate labelled
  *about* on screen is an estimate out loud.
- If the live call fails, keep the honest failure visible and stop the rehearsal. Do not
  spend a second invocation trying to manufacture a clean take.
- Do not record until the rehearsal confirms the exact run id, pool id and
  `created_by_run` relationship survive the entire journey.

## Backup

`make demo` produces a deterministic lifecycle transcript from the same domain and tool
code. It is a truthful fallback for explaining the lifecycle, but it is not a substitute
for the single live discovery proof required by the primary recording.

The thirteen-stage reader (`Pool → Activity → How this pool happened`, or Showcase → The
run) is the same transcript with a reader on it. It is excellent and it is too long for
the recording; at most two stages belong in the video, and on the deployed stack it runs
the deterministic planner rather than Bedrock, which the run record says on every row.
