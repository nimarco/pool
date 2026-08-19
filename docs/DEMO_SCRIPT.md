# Demo rehearsal script — about 3:55

This is a navigation and timing rehearsal, not a final word-for-word voiceover. The
presentation pass happens later.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

And the line this version adds, which is the harder half of the claim:

> **Pool kept watching, the world changed, and the answer changed with it.**

## What changed, and why

The previous script ended its best beat on a promise. Pool refused an order truthfully —
*your declaration stays standing, and Pool keeps watching* — and a judge's next thought is
**watching for what?** Nothing in the recording ever cashed it. The demo could show that
Pool says no; it could not show that no is a *current* answer rather than a permanent one.

So the spine is now one declaration answered three times, from three different world
states, with the demand never changing:

| World state | Pool's answer |
| --- | --- |
| no supplier quote | nothing to evaluate — the blocker is supply, not people |
| a split-case quote arrives | the supplier will sell, and it is still not worth doing |
| a case-programme quote arrives | viable — and the same seven people get the order |

Nobody is recruited between those rows. No declaration is edited, no quantity moves, no
household joins. One supplier offer row lands, twice, and the deterministic layer
recomputes. That is the whole mechanism, and it is why the sequence is worth the minute it
costs.

**The canonical whey lifecycle is no longer walked live.** It is the Showcase — thirteen
recorded stages in its own copy of the community — and it stays a backup and a regression
proof rather than the recording's subject.

### The one decision this script does not make for you

The old rule was **one live AgentCore invocation, ever**. This structure needs **two**:
the run that refuses and the run that acts on the changed world. Two is inside the
deployed per-session cap of three, and the technical-proof section is stronger for it —
two stored runs, two different verdicts, the same declarations, and one recorded supplier
fact between them.

But it is a real change to a rule that existed for good reasons, and it should be a
deliberate decision rather than a side effect of this script. Settle it before recording.

## Before recording

1. Run `make qa` and the release checks.
2. Use the deployed URL, open a fresh disposable workspace, and reset Demo University.
3. Confirm the drawer says: discovery uses AgentCore / Bedrock; the lifecycle uses the
   deterministic planner; payments and supplier ordering are simulated.
4. A fresh reset opens on **setup**, not on somebody's home screen. Pool knows nothing
   about you: no name, no card, no declarations. That is the opening.
5. Decide the name you will type. Any name works and none is special.
6. Keep the form's default quantities. They are what a visitor would leave alone, and the
   case arithmetic is real — the two-bag default is what lands the order on a whole case
   boundary, and a different number is a true outcome and a weaker beat.
7. Keep one continuous browser journey. Switching to a different run or workspace is
   never permitted.
8. Do **not** pre-record the supplier quotes. The starting state has none, and the demo
   depends on the judge watching them arrive.

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

**Continue.** **Type a category** — `rice` — not a memorised product name.

The first result is **Jasmine rice, 5 lb**. Notice what it is *not* labelled: there is no
*Pool can source this* mark on it, and the real branded rices underneath are equally
declarable. Pick it, keep the defaults, **Add this**.

Then type `towels` and add that one too, also on defaults.

Two declarations, and neither of them is a thing Pool can currently buy. That is
deliberate: this recording is about what Pool does when the answer is no.

Say once, over the results: these are real products from a public catalogue; the supplier
prices later in the demo are invented, and the app says so on its About page.

## 0:45–0:55 — How much Pool may do

**Continue.** Choose **Ask me first**, add the test card, finish.

Both parts in one breath: the card is simulated and no real money exists, and *ask me
first* is why Pool will stop and put a question in front of you rather than spending on
your behalf.

Setup is over. Four screens, no group created, nobody invited.

## 0:55–1:15 — The question, before the answer

**Home.** Do not click yet. This screen is the pitch, and the rice row is the whole thesis
in two sentences:

> 6 other members have independently declared something this could be bought for — 22
> bags. With yours, 24.

> Pool has no verified bulk supplier for this yet, so there is nothing to price a group
> order against. Your declaration stays standing.

Read them in that order and say why the order matters. Six people already buy this. You
did not find them, you cannot see them, and none of you organised anything. What is
missing is not demand — it is a supplier. Those are completely different problems, and
most software would have shown you an empty screen.

Then the line underneath, because it is what keeps the first two honest:

> Whether an order actually works still depends on things Pool has not checked yet:
> whether those people can reach one pickup point, whether their restock dates overlap
> with yours, whether the units fill whole cases, and whether the all-in price beats
> buying alone.

## 1:15–1:35 — The first live run

**Click `Run Pool now` exactly once.**

Say the honest version, because the screen already does: in the real product Pool watches
these declarations on the community's pool day; nothing is scheduled in the demo account,
so the coordinator starts when you press it.

Hold the wait. It names Amazon Bedrock AgentCore, names the region, runs a real elapsed
clock, resolves the one thing the browser actually observed — that it sent the request —
and says on screen that nothing in between is being animated.

The answer is two refusals, for two different reasons:

> **Jasmine rice, 5 lb** — No supplier Pool has verified sells this in bulk yet.

> **Paper towels, 6 rolls** — 6 compatible packs were declared near you,
> and the supplier will not sell fewer than 48.

Pool answered both things you told it, and both answers are no. Read the tail out loud,
because it is the promise the rest of the recording keeps:

> Your declaration stays standing, and Pool keeps watching.

## 1:35–2:15 — The world changes, and no agent runs

**Demo University drawer → Operations console → Supplier updates.**

Frame the actor before touching anything: this is an **operator** screen, not yours. A
member cannot conjure a wholesale quote. What a member does is say what they buy; what
changes whether that can be acted on is the world.

The panel leads with the demand, not with a button: *7 members already declared this
independently — 24 bags standing*, and a **no bulk quote** chip. Both quotes are labelled
**synthetic**, and the footer says nobody negotiated them and no wholesaler relationship
exists.

**Record the split-case quote.** $9.75 a bag, 4 to a case, minimum 12 bags.

Say what just happened and what did not: one supplier offer row was written. No
declaration, no household, no pool, no past run record was touched — and **no agent ran**.

**Back to Home, then Needs.** The current outlook has moved on its own:

> **As things stand** — There is enough demand, but buying it together would not actually
> be cheaper once collection and fees are counted.

This is the beat to slow down on. The first blocker is gone: there is a supplier now, the
minimum clears, the units fill whole cases. And Pool still says no, because once a
fulfiller's pay, card processing and Pool's own fee are counted the group pays more than
its members would pay alone. **Removing an obstacle did not buy a yes.**

**Back to Operations. Record the case-programme quote.** $6.25 a bag, 8 to a case,
minimum 16 bags.

**Home.** Now hold both panels in one frame, because this is the most important screenful
in the recording:

- the run report still says **No supplier Pool has verified sells this in bulk yet.**
  That is what was true when that run happened.
- the standing card now says **The supplier's best price starts at 16.** That is what is
  true now.

One is history and one is the present, and Pool does not edit the first to agree with the
second. Nothing has run.

## 2:15–2:40 — The second run, on the changed world

**Click `Run Pool again`.**

Same declaration. Same six neighbours. Same quantities, same dates, same rules. The only
thing that changed is a supplier fact somebody recorded ninety seconds ago.

> Your 2 bags · about $17.53 instead of $22.98 buying alone.
> With 6 others · collect from Central Quad pavilion.

Open **Why this worked** and read three lines, not all six:

> 22 bags were already due, and 2 more were bought early under permission those members
> had already given. · Together that reached the supplier's 16-unit minimum. · It fills 3
> complete cases with nothing left over. · Pool compared 2 supplier prices and took the
> one at $6.25 a unit, ahead of $9.75.

That last line matters: both quotes are still on file, and the evaluator picked the better
one. Nothing was deleted to make this work.

And point at paper towels, still standing, still refused on the supplier minimum. The
world changed for one product, not for the demo.

## 2:40–3:05 — Host first, then the one question

**Demo University drawer → the host accepts the fulfilment job → Let Pool work the
queue.** Back to Home.

Offering to host did not claim the job: Pool ranked candidates and offered it to the best
eligible one. Only after acceptance can host pay enter the exact buyer price — which is
why the number above was labelled an estimate.

You are now asked to approve the exact amount, with the policy engine's own reason under
it: *member is on Ask Me — commitment requires explicit approval*. Answer it.

Then the strip below: **things Pool did on its own** against **times it had to ask a
person**. Most of the buyers were never asked at all.

## 3:05–3:20 — Both currencies

**Community.**

What it saved, and directly under it what it cost anyone in attention.

> **Community enables → Pool coordinates → Members choose and collect.**

Demo verification and pickup permissions are synthetic and imply no institutional
partnership.

## 3:20–3:55 — Same-run technical proof

**Home → `Technical proof for this run`.**

Show, without invoking anything:

- Amazon Bedrock AgentCore Runtime live, region, model provider and model;
- the exact run id and resulting pool id;
- `Pool created_by_run`, equal to that run id;
- the stored tool sequence, outcome and termination;
- authoritative run + pool readback from the same workspace;
- browser → Lambda → AgentCore → Strands / Bedrock → typed tools → deterministic
  services → DynamoDB → browser.

Two runs are stored, not one, and they disagree. That is the proof this version adds: the
same member's same declaration, evaluated twice against two different world states, with
both verdicts kept.

Close on the collective outcome rather than a feature list:

> The buyers get viable bulk economics without organising the group. The host earns
> recorded compensation. The supplier receives one clean bulk order. Nobody organised the
> group. Pool noticed — and kept noticing.

## Continuity rules

- One workspace, one continuous journey, **two** live AgentCore invocations and no more.
- The real wait is content, not dead air. Hold the first one; the second may be tightened,
  but a cut may not replace a run or its result.
- Never pre-record a supplier quote. The starting state has none, and the sequence is the
  demonstration.
- Never say "deployed," "paid," "captured," "final," or "permission" more strongly than
  the screen supports.
- Never say a number not visible on screen. An estimate labelled *about* on screen is an
  estimate out loud.
- Never say Pool "considered" something the report does not list. The report shows only
  what that run actually evaluated, and that is the claim being made.
- Never describe the supplier quotes as anything but synthetic and operator-recorded.
  Riverbend Wholesale does not exist.
- If a live call fails, keep the honest failure visible and stop the rehearsal. Do not
  spend another invocation trying to manufacture a clean take.

## If the take runs long

Cut in this order:

1. **The paper-towels declaration** (‑20s). The rice thread carries the whole argument
   alone; towels only adds "and it answered the other one too", which the outcome-matrix
   table can cover if a judge asks.
2. **The Community screen** (‑15s). The savings figure is already on the order card.
3. **The host-acceptance step** (‑15s), going straight to the approval question.

Do **not** cut the split-case quote. A single quote that turns a no into a yes is the
version of this sequence that looks like an answer key; the refusal in the middle is what
makes the whole thing evidence rather than a switch.

## Other truthful inputs, if a judge asks

Every one of these is reachable through the same flow, and each ends somewhere different:

| Typed | What happens |
| --- | --- |
| `whey` | forms, and you are in it |
| `coffee` | forms — a different product, different members, its own economics |
| `energy` | forms, on a third independent set of members |
| `laundry` | refused on **economics**: enough demand, and pooling it saves nothing |
| `towels` | refused on the **supplier minimum**: 6 packs against 48 |
| `rice` | refused for **no supplier at all**, with the demand behind it still shown |
| a coffee Pool cannot source | stays exactly what you picked, and truthfully no-ops |
| something invented entirely | declarable, and openly unsourceable |

`tests/test_outcome_matrix.py` runs all of these through the real endpoints, so the table
is checked rather than asserted. `tests/test_supplier_updates.py` does the same for the
three-state rice sequence, including that recording a quote changes the offer table and
nothing else.

## Backup

The **Showcase** replays the canonical order end to end — thirteen recorded stages
through discovery, host recruitment, a declined card, recovery, lock, purchase and ten
handoffs — with the reconciliation the write-ups quote: 11 memberships, 10 buyers, 24
units, 2 cases, $861.44 against $1,127.76.

It runs in **its own copy of Demo University**, reseeded from scratch each time, so
replaying it does not touch the account you set up in the recording. That is what makes
"this starts the community over" literally true, and it is why the showcase is a backup
and a regression proof rather than something to walk through live.

`make demo` produces the same transcript on a terminal. Both use the deterministic planner
rather than Bedrock, which the run record says on every row.
