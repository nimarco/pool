# Demo rehearsal script — about 3:10

This is a navigation and timing rehearsal, not a final word-for-word voiceover. The
presentation pass happens later.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

The defining technical rule is equally simple:

> **One live AgentCore invocation.** The `Run Pool now` run is the same stored run shown
> later under `Technical proof for this run`. Never invoke the runtime again in the
> recording.

## What changed, and why this script is shorter

The previous version opened by naming one exact product for the presenter to type, and it
was right to: before search knew which products Pool could actually source, anything else
was a dead end. Typing `coffee` returned eight real coffees, none of them the one Pool holds a bulk
quote for, and the honest consequence was that no pool could form.

That is fixed, so the instruction goes. **Type a category** — `whey`, `coffee`, `energy`,
`laundry`, `towels` — and the option Pool can genuinely source leads the list, labelled
*Pool can source this*. Every one of those five reaches a different, truthful outcome,
which is the point: the product is not built around one memorised phrase.

The old script also spent 4:53 walking the entire lifecycle. Most of that is now the
**Showcase**, which replays the canonical order end to end in its own copy of the
community — so the recording can be about the thing that is hard to believe (an agent
answering *your* declaration) rather than about a lifecycle a reader can step through
themselves.

## Before recording

1. Run `make qa` and the release checks.
2. Use the deployed URL, open a fresh disposable workspace, and reset Demo University.
3. Confirm the drawer says: discovery uses AgentCore / Bedrock; the lifecycle uses the
   deterministic planner; payments and supplier ordering are simulated.
4. A fresh reset opens on **setup**, not on somebody's home screen. Pool knows nothing
   about you: no name, no card, no declarations. That is the opening.
5. Decide the name you will type. Any name works and none is special.
6. Keep the form's default quantities. They are what a visitor would leave alone, and the
   case arithmetic is real — three tubs instead of two genuinely lands outside the case
   boundary, which is a true outcome and a weaker beat.
7. Keep one continuous browser journey. Switching to a different run or workspace is
   never permitted.

## 0:00–0:10 — Who is using this

**A brand-new workspace.** Pool opens on *What should Pool call you?*

Type a name. Say it out loud: this is your account, not a seeded persona you have been
cast as.

## 0:10–0:20 — Where you are, honestly

**Continue.** *Where are you?*

Pool is local — the people it finds have to be close enough to share a pickup. And this
community is invented, so Pool has not asked the browser for a position and has not
guessed one. Whoever is watching, in whatever city, is exploring Demo University from the
inside.

Ten seconds, because it is the one place a demo like this normally lies.

## 0:20–0:45 — Two things you buy

**Continue.** Type `whey`.

Read what happens: the first result is marked **Pool can source this**. The rest of the
catalogue is right underneath it and equally declarable — Pool is not hiding anything, it
is saying which one it currently holds a supplier quote for. Pick it, keep the defaults,
**Add this**.

Then type `towels` and add that one too, also on defaults.

Two declarations is the whole reason for this beat. One product proves Pool can find an
overlap; two prove it will tell you the truth about **both**, including the one that does
not work.

Say once, over the results: these are real products from a public catalogue; the supplier
prices later in the demo are invented, and the app says so on its About page.

## 0:45–0:55 — How much Pool may do

**Continue.** Choose **Ask me first**, add the test card, finish.

Both parts in one breath: the card is simulated and no real money exists, and *ask me
first* is why Pool will stop and put a question in front of you rather than spending on
your behalf.

Setup is over. Four screens, no group created, nobody invited.

## 0:55–1:12 — The question, before the answer

**Home.** Do not click yet. This screen is the pitch.

Two rows, each one thing you declared and what has already accumulated around it, on its
own:

> 12 other members have independently declared something this could be bought for — 29
> tubs. With yours, 31. The supplier's best price starts at 24.

> 2 other members … 4 packs. With yours, 6. The supplier's best price starts at 48.

Then read the line underneath, because it is what makes the first two honest:

> Whether an order actually works still depends on things Pool has not checked yet:
> whether those people can reach one pickup point, whether their restock dates overlap
> with yours, whether the units fill whole cases, and whether the all-in price beats
> buying alone.

Nobody organised anything. Nobody can see anybody else's list. The overlap is a fact
about twenty-four people's habits, and whether it is *worth* anything is exactly what
has not been decided yet.

## 1:12–1:32 — One live run

**Click `Run Pool now` exactly once.**

Say the honest version, because the screen already does: in the real product Pool watches
these declarations on the community's pool day; nothing is scheduled in the demo account,
so the coordinator starts when you press it.

Hold the wait. It names Amazon Bedrock AgentCore, names the region, runs a real elapsed
clock, resolves the one thing the browser actually observed — that it sent the request —
and says on screen that nothing in between is being animated.

Do not open Showcase's live page and do not press `Run again` later.

## 1:32–2:00 — Both answers

**Stay on Home.**

The order card is scoped to you: two tubs, about **$71.92** against **$93.98** buying
alone, with nine others, collecting from North Hall lobby. The tail says **Not final yet
— a fulfiller's pay is part of the price**, which is an invariant rather than a missing
number.

Open **Why this worked** and read three of the lines, not all six:

> 16 tubs were already due, and 8 more were bought early under permission those members
> had already given. · Together that reached the supplier's 24-unit minimum. · It fills 2
> complete cases with nothing left over. · Pool compared 2 supplier prices and took the
> one at $31.50 a unit, ahead of $39.80.

Every one of those is a value the run computed and stored while it ran. None of it is
recomputed for the screen, and none of it was written by a model.

Then point at the other row — **paper towels**:

> 6 compatible packs were declared near you, and the supplier will not sell fewer than
> 48. Your declaration stays standing, and Pool keeps watching.

Say the sentence the whole demo is for: Pool answered **both** things you told it, and
one of the answers is no.

## 2:00–2:25 — Host first, then the one question

**Demo University drawer → the host accepts the fulfilment job → Let Pool work the
queue.** Back to Home.

Offering to host did not claim the job: Pool ranked candidates and offered it to the best
eligible one. Only after acceptance can host pay enter the exact buyer price — which is
why the number above was labelled an estimate.

You are now asked to approve the exact amount, with the policy engine's own reason under
it: *member is on Ask Me — commitment requires explicit approval*. Answer it.

Then the strip below: **things Pool did on its own** against **times it had to ask a
person**. Most of the buyers were never asked at all.

## 2:25–2:40 — Both currencies

**Community.**

The two things that matter: **$1,127.76 → $861.44 → $266.32 kept in the community**, and
directly under it what it cost anyone in attention.

> **Community enables → Pool coordinates → Members choose and collect.**

Demo verification and pickup permissions are synthetic and imply no institutional
partnership.

## 2:40–3:10 — Same-run technical proof

**Home → `Technical proof for this run`.**

Show, without invoking anything:

- Amazon Bedrock AgentCore Runtime live, region, model provider and model;
- the exact run id and resulting pool id;
- `Pool created_by_run`, equal to that run id;
- the stored tool sequence, outcome and termination;
- authoritative run + pool readback from the same workspace;
- browser → Lambda → AgentCore → Strands / Bedrock → typed tools → deterministic
  services → DynamoDB → browser.

`Run again` is collapsed and secondary. Do not open it.

Close on the collective outcome rather than a feature list:

> The buyers get viable bulk economics without organising the group. The host earns
> recorded compensation. The supplier receives one clean bulk order. Nobody organised the
> group. Pool noticed.

## Continuity rules

- One workspace, one `Run Pool now` click, one live AgentCore invocation.
- The real wait is content, not dead air. Hold it rather than cutting it; if the take must
  be shortened, a cut may not replace the run or its result.
- Never say "deployed," "paid," "captured," "final," or "permission" more strongly than
  the screen supports.
- Never say a number not visible on screen. An estimate labelled *about* on screen is an
  estimate out loud.
- Never say Pool "considered" something the report does not list. The report shows only
  what that run actually evaluated, and that is the claim being made.
- If the live call fails, keep the honest failure visible and stop the rehearsal. Do not
  spend a second invocation trying to manufacture a clean take.

## If you have thirty seconds spare

Type a third category during setup — `laundry` — and let the same run answer it too. The
sentence names both figures; read whichever ones are on screen:

> There is enough demand, but buying it together would cost $398.92 against $367.84
> buying it alone.

Three declarations, three genuinely different deterministic verdicts — formed, below the
supplier minimum, and *worse than retail* — from one button press and seven model turns
against a bound of eight. It is the strongest thirty seconds available and the first thing
to cut if the take runs long.

Three is also the cap: a run takes on the three declarations you need soonest, and says so
about any it did not reach rather than inventing a reason for them.

## Other truthful inputs, if a judge asks

Every one of these is reachable through the same flow, and each ends somewhere different:

| Typed | What happens |
| --- | --- |
| `whey` | forms, and you are in it |
| `coffee` | forms — a different product, different members, its own economics |
| `energy` | forms, on a third independent set of members |
| `laundry` | refused on **economics**: enough demand, and pooling it saves nothing |
| `towels` | refused on the **supplier minimum**: 6 packs against 48 |
| a coffee Pool cannot source | stays exactly what you picked, and truthfully no-ops |
| something invented entirely | declarable, and openly unsourceable |

`tests/test_outcome_matrix.py` runs all of these through the real endpoints, so the table
is checked rather than asserted.

## Backup

The **Showcase** replays the canonical order end to end — thirteen recorded stages
through discovery, host recruitment, a declined card, recovery, lock, purchase and ten
handoffs — with the reconciliation the write-ups quote: 11 memberships, 10 buyers, 24
units, 2 cases, $861.44 against $1,127.76.

It runs in **its own copy of Demo University**, reseeded from scratch each time, so
replaying it does not touch the account you set up in the recording. That is what makes
"this starts the community over" literally true, and it is why the showcase is now a
backup and a regression proof rather than something to walk through live.

`make demo` produces the same transcript on a terminal. Both use the deterministic planner
rather than Bedrock, which the run record says on every row.
