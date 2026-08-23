# Demo rehearsal script

**Core (~2:00)** is the tight version and the one to record first. **A (~3:30)** is the
same story with room to breathe, and is the submission recording. **A+ (~5:00)** extends it
with reversibility and the AWS boundary. **B** is the ninety-second explanation for somebody
with no interest in AWS. **C** is the older changing-world narrative, kept because it proves
a different claim and because the machinery behind it is still real.

All of them are navigation-and-timing rehearsals, not word-for-word voiceovers.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

And the line flow A cashes, which is the harder half:

> **The obvious option was the one that did not work, and Pool found that out by
> costing it.**

## What changed, and why it matters to the presenter

The recording used to require the presenter to *drive* Pool: load a fixture, record a
supplier quote, press "run agent", answer for other people. Every one of those is an
action whose only purpose is advancing a demo, and a judge watching one is being asked to
take the interesting part on trust.

Flow A now contains **one** causal action: a member saves something they buy. Everything
after it — the search, the refusal, the adaptation, the order — happens because of that
save and is readable afterwards from stored rows.

**The presenter is a user of Pool, not its puppeteer.** If you find yourself pressing
something a member would never press, the take is wrong.

---

# Core. The two-minute cut

One browser, mobile-sized (390 × 844). Fresh session. Everything here is on screen; nothing
is arranged in advance.

| | Beat | What you do | What you say |
| --- | --- | --- | --- |
| **0:00** | Hook | `/verify`, already open | *"Group buying sounds simple until everybody buys a slightly different thing and nobody wants to organise the group."* |
| **0:15** | The member | Start → name → search **Kestrel** → medium roast | *"I normally buy this coffee."* |
| **0:30** | Consent | Choose **Any brand that matches my preferences** | *"I would take another brand — if it is still the coffee I actually drink."* |
| **0:45** | The questions | Answer the two or three that appear; add **Dark** | *"Pool's bounded planner selected these questions from an approved product schema. It cannot invent a question, and it cannot decide what an answer means."* |
| **1:05** | Save | Three bags. Save. Once. | *"That is the only thing I do. There is no run button."* |
| **1:15** | Consequence | Home has changed on its own | *"Pool found fragmented recurring demand that nobody organised, and coordinated a provisional order around a dark roast — because I said dark was fine. Nothing has been bought and no card has been touched."* |
| **1:30** | Why | **Why this order?** — considered, refused, chosen, excluded, provisional | *"The option with the most demand behind it is the one that lost money. It only found that out by costing it, and then it tried the other one."* |
| **1:50** | Proof | Desktop. Expand **Technical proof for this run** | *"This repeatable public run uses the deterministic offline planner inside the real Strands loop, which is why it shows zero model tokens. The control plane chooses what to investigate and can adapt; deterministic code decides what is true — compatibility, cases, economics, and whether an action is allowed at all."* |

Stop there. Do not walk the lifecycle to completion; the claim is already made and the
order is honestly provisional.

---

# A. The submission recording (~3:30)

One browser, mobile-sized (390 × 844), for everything except the last beat.

## Before recording

- `bash scripts/run_public_demo_local.sh`, or the deployed URL if one has been verified.
- A **fresh** browser profile or cleared `localStorage`. The walkthrough is about a cold
  session; a warm one has your last take's declaration in it.
- Go to `/verify`. Nothing else is set up in advance, and nothing needs to be.

## 0:00–0:20 — Where you are, honestly

Open on the problem, not on the product:

> **"Group buying rarely fails because the demand is missing. It fails because everybody
> buys a slightly different version of the same thing — and nobody wants the unpaid
> coordination job."**

Then `/verify` says the rest before you do: a synthetic community that already has coffee
demand in it, real software, simulated payments, nobody real represented. Read the three
lines under *What is real here* rather than paraphrasing them — they are the claim being
made.

Say: **"A dozen households here already buy coffee. They disagree about which coffee.
Nothing has been arranged for me."**

## 0:20–0:50 — Becoming a member

Start → a name → what you buy → how much Pool may do. This is ordinary setup and is not
the story; move through it. From `/verify` the community step is skipped, because the page
has already said which synthetic community this is and that Pool did not ask the browser
where you are.

**Skip the test card.** It is optional and the screen says so: a provisional order forms
without any payment method, and nothing on the path this recording takes touches a card.
Adding one on camera invites the question the whole beat then has to answer.

## 0:50–1:40 — The one thing a member does

Search **Kestrel**. Pick the medium roast.

Then the beat this whole phase exists for. One question first, and it is a consent gate:

- **Only this exact coffee** — Pool will never buy you anything else.
- **Any brand that matches my preferences** — the brand opens up, and nothing else does.

Choose the second. *Now* the questions arrive, and they are about coffee:

- Roasts that work for you — with the standing demand behind each one.
- It has to be whole bean.
- It has to be caffeinated.

Say: **"I am not choosing a substitution policy. I am telling it what coffee is. Pool's
bounded planner selected these questions from an approved product schema — it cannot
invent a question, and it cannot decide what an answer means."**

> **Do not oversell this beat.** The coffee schema holds three approved questions and the
> canonical planner asks all three, so most of what is on screen here could be reproduced
> deterministically. It is a real capability and a genuinely better form, and it is *not*
> the why-an-agent claim. That comes two beats later, at the refusal.

Set **three bags a month**, leave whole bean and caffeinated ticked, and add **Dark**
alongside Medium.

> **On the roast.** Medium alone is the default, because Pool never widens a preference
> nobody widened. Beside each roast is the standing demand it would let you combine with —
> 22 units behind medium, 6 behind dark — so adding dark is a decision you make with the
> consequence in front of you. Say it that way: *"I would drink a dark roast, and it shows
> me what that opens up."* Do not say it is required for the demo.
>
> **On the quantity.** Any quantity works and the answer you get is the real one. Three is
> the amount this member buys; it also happens to land on this supplier's case boundary,
> which is why the form in the verification world starts there. Change it to two and Pool
> tells you, truthfully, *"it could assemble an order, but not one you would be in, so it
> did not form it"* — a good answer and a worse recording. The field is a field; nothing
> here forces a result.

Save. **That is the last thing you do to Pool.**

## 1:40–2:10 — What Home says now

Home has changed on its own. Read what is actually there:

- Harbourstone dark roast — *not* the bag that was picked.
- Your three bags, about **$43.96** instead of **$55.50** buying alone.
- With five others, collecting from the Student Union.
- **Not final yet** — a fulfiller's pay is part of the price.
- 18 units, past the supplier's 12-unit minimum.

Say: **"I asked for a medium roast. It formed the order around a dark one, because I said
dark was fine — and it never tells me that is a substitute, because it isn't. Nothing has
been bought: this is a provisional order, and nobody's card has been touched."**

## 2:10–3:00 — Why this order?

One tap from the order card. Take these in order and do not rush the middle one:

1. **What Pool considered** — two options, neither with a price. Kestrel had *more*
   demand (23 bags from 8 people) and more headroom over its minimum.
2. **What Pool worked out** — Kestrel: not worth doing. $367.19 all in against $360.00
   buying separately. Harbourstone: 18 bags, three full cases of six, nothing left over,
   $69.18 saved.
3. **Who could not join** — four people who asked for one specific product, two who buy
   decaf or ground. Aggregate only; no names anywhere.
4. **What has not happened** — no card charged, nobody has agreed to collect it, the exact
   price comes later, nothing ordered.

Say: **"The option that looked best on every fact it had is the one that lost money. It
only found that out by costing it — and it did not give up, it tried the other one."**

> **This is the why-an-agent beat.** Not the targeted questions. A cohort that looks
> strongest on coarse facts, an authoritative deterministic refusal that no amount of
> prompting can talk past, and a control plane that responds by investigating a different
> cohort — that is the thing a lookup table does not do. Give it the time.

## 3:00–3:30 — Technical proof for this run

Switch to desktop here, once. Expand *Technical proof for this run*.

The same event id, run id, evaluation ids and pool id as the page above it — because it is
the same rows. Point at three things and stop:

- the tool sequence: list, evaluate, evaluate, create;
- **2 of 3** options costed, **1 of 1** order formed, and the planner-iteration count
  against its bound;
- *What Pool decided to ask, before any of this* — the approved question set beside the
  ones actually asked, and its own separate run;
- **the provider line**, and the paragraph under it, and the line saying the community is
  synthetic and payments simulated.

Read the numbers off the screen rather than from this page. They are deterministic for the
canonical fixture and they are still the run's, not the script's.

Say the provider sentence, and do not skip it: **"This repeatable public run uses the
deterministic offline planner inside the real Strands loop, which is why it shows zero
model tokens. The Lambda serving this page has no permission to call a model at all."**

Then: **"The control plane chose what to investigate and adapted when it was refused. It
never computed a price, decided who was compatible, or supplied a member, a quantity or a
supplier term. The tool that forms an order takes two identifiers and nothing else."**

Then the live path, separately and as its own claim: **"That agent is also deployed to
Amazon Bedrock AgentCore Runtime, where the same Strands loop and the same bounded tools
run against Amazon Nova Lite on the same DynamoDB state. That was verified live on
2026-08-22, and it is a different button — see the AWS beat."**

Then reload the page. The explanation is still there, unchanged, and there is still one
run. Nothing was held in the browser.

---

# A+. The five-minute cut

Flow A, plus two beats and a closing frame. Only record this version if A is comfortably
inside time — a rushed five minutes is worse than a calm three and a half.

**Insert after *Why this order?* (about 3:00): changing your mind.**

Go to **What you buy → Change**. Switch to **Only this exact coffee** and save.

The order disappears from Home, and the banner says why: *Pool took you out of an order
your new rules no longer allow. Nobody was charged, and the other members' order is
unaffected.* Home now says it is watching, and names what is missing.

Say: **"Watch what happens if I change my mind. It does not argue, and it does not keep
me in an order I have just said I do not want."**

That is the whole beat — about twenty seconds. **Do not** demonstrate switching back
unless the take is short and calm: the restoration is real, it is verifiable, and it is
one more thing to explain. It stays available to any judge who tries it.

**Insert before the close (about 4:15): what is real.**

Read the three lines off `/verify` rather than paraphrasing:

- **Synthetic** — the community, the households, the coffee brands, the supplier quotes.
- **Simulated** — payments and purchasing. No card is charged, no supplier is contacted.
- **Real** — the compatibility engine, the case fitting, the landed economics, the agent
  loop and its bounds, and every record you just read.

Then the AWS frame, and **only what has been verified**. Check `README.md` §AWS before
recording, and do not put an old URL on screen.

**There is one AWS truth and it has two halves. Say both, and say which is which.**

> **"Everything you have just watched ran on AWS — a Lambda function URL and a DynamoDB
> table — using the real Strands agent loop with a deterministic offline planner in place
> of a model. That is deliberate: it makes this run repeatable, and it costs a judge
> nothing to reproduce. The function serving it has no permission to call a model."**
>
> **"The same Strands agent is also deployed to Amazon Bedrock AgentCore Runtime, where it
> runs against Amazon Nova Lite over the same DynamoDB state and the same bounded tools.
> That was verified live on 2026-08-22."**

If the live verification is mentioned in any more detail than that, it must be described
as it actually went (`BUILD_HISTORY` #0061): the run was genuinely live, the provider was
`bedrock` / `us.amazon.nova-lite-v1:0`, and it correctly recorded **no action**, because
the member's only declaration had already been served by the in-process run their save had
caused. It proves the deployment, the tool surface and the bounds on real infrastructure.
It does **not** show Nova adapting from Kestrel to Harbourstone, and saying it does would
be describing the offline planner's trace as the model's.

**Never say or imply that the public `/verify` trace was produced by Nova Lite.** It was
not, the proof panel says so, and a judge who checks will find the contradiction.

**Close on the thesis, not on a feature list:**

> **Nobody organised the group. Pool noticed.**

---

# B. The two-minute product explanation

No AWS, no proof surface, no operator console framing. If Pool cannot be made
understandable in two minutes, that is a fact about the product and not about the edit.

**0:00–0:25 — set up.** Type a name. Join the one community found near you. Type `rice`,
pick the family, keep the defaults, add it. Choose *ask me first*, add the simulated card,
finish. Four screens, no group created, nobody invited.

**0:25–0:50 — the pitch is the screen.** Home, one row:

> Rice · WATCHING · No verified supplier yet
> 7 people near you buy this — 24 bags standing, 2 of them yours

Seven people already buy this. Nobody organised anything, and what is missing is a supplier
rather than people.

**0:50–1:10 — the world changes.** Import the split-case sheet. Same row:

> Supplier found — not cheaper

There is a supplier now, and it is still not worth doing once collection and fees are
counted. Pool bothered nobody.

**1:10–1:25 — and again.** Import the case-programme sheet. Same row:

> Worth doing

**1:25–1:50 — the order.** *Check again now.* Your 2 bags, about $17.53 instead of $22.98,
with six others, collect from Central Quad pavilion. Three complete cases, nothing left over.

**1:50–2:00 — the line.** Nobody organised the group. Pool noticed.

---

## What to show, and what to leave out

**Must show.** Setup as yourself · the family declaration · the demand that pre-existed ·
one refusal · the file import · the intermediate refusal · the second run forming the order ·
the one approval question · `created_by_run` proof.

**Optional if time.** The paper-towels second refusal · the map's walking rings · the case
drawing on an excluded declaration · the money ledger in Behind Pool.

**Do not show in the primary video.** The Showcase's fourteen stages — it is a regression
proof, and walking it costs ninety seconds to restate a claim the live sequence already made.
The community aggregates. The viability checklist's eleven checks. The Orders list when it
holds one row. Every one of those is real, and each one asks the viewer to hold a second
subject.

## Continuity rules

- One workspace, one continuous journey, **two** live AgentCore invocations and no more.
- The real wait is content, not dead air. Hold the first one; the second may be tightened,
  but a cut may not replace a run or its result.
- Never pre-record a supplier quote. The starting state has none, and the sequence is the
  demonstration.
- Import the sheets in order. The split-case one first, always.
- Never say "deployed," "paid," "captured," "final," or "permission" more strongly than the
  screen supports.
- Never say a number not visible on screen. An estimate labelled *about* on screen is an
  estimate out loud.
- Never say Pool "considered" something the report does not list. The report shows only what
  that run actually evaluated, and that is the claim being made.
- Never describe the supplier sheets as anything but synthetic and operator-imported.
  Riverbend Wholesale does not exist.
- Never call a family declaration a substitution. The member said "rice"; Pool choosing
  jasmine is fulfilment, not a swap.
- If a live call fails, keep the honest failure visible and stop the rehearsal. Do not spend
  another invocation trying to manufacture a clean take.

## If the take runs long

Cut in this order:

1. **The paper-towels declaration** (‑20s). The rice thread carries the whole argument alone;
   towels only adds "and it answered the other one too", which the outcome-matrix table can
   cover if a judge asks.
2. **The map aside in Behind Pool** (‑10s).
3. **The host-acceptance step** (‑15s), going straight to the approval question.

Do **not** cut the split-case quote. A single quote that turns a no into a yes is the version
of this sequence that looks like an answer key; the refusal in the middle is what makes the
whole thing evidence rather than a switch.

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
| a specific coffee Pool cannot source | stays exactly what you picked, and truthfully no-ops |
| `Pike Place`, on a fresh account | an order forms **without** your units, and the case boundary is drawn |
| something invented entirely | declarable, and openly unsourceable |

`tests/test_outcome_matrix.py` runs these through the real endpoints, so the table cannot
drift from the product without a test failing.

## The Showcase, if it is asked for

Fourteen recorded stages on **one page**, in **its own copy of Demo University**, which
means it **does not touch the account you set up** in the recording — a separate partition,
reseeded every time it runs. It is no longer a paginated reader: a sticky unit track draws
the quantity through the whole story (24 funded, two lost to a declined card, two restored
by a replacement, closing into two whole cases), the twelve acts are labelled destinations,
and every stage is on screen at once with its figures one click away. It is the one place the whole lifecycle appears, including the parts the live
sequence cannot reach in four minutes: an authorisation that fails, the quantity falling to
22, a compatible replacement restoring exactly 24, purchase, ten pickups, and
reconciliation.

Canonical, and not to be paraphrased: 11 memberships, 10 funded buyers, 1 authorisation
failure, 1 replacement, 24 units, 2 cases, 0 surplus, $861.44 all-in against $1,127.76
retail, $266.32 kept, 23.61%, North Hall lobby.

---

# C. The changing-world narrative (kept, and still real)

The older recording, preserved because it proves a *different* claim: that Pool keeps
watching, that an outside event can change the answer, and that no agent runs when nothing
happened. It uses the rice fixture and the supplier-quote import, and every mechanism in it
still works.

It is **not** the submission recording any more, for the reason at the top of this file:
it required the presenter to drive the system. Use it for the changing-world claim, for
regression rehearsal, and when somebody asks specifically how supplier facts arrive.

## What that flow changed, and why

Three things about the *product* changed since the last rehearsal, and each one removes a
sentence the presenter used to have to say out loud.

**A member can now say what they buy.** Typing `rice` offers **Rice** — the family — with
the thirteen individual bags one click behind it. That is not a cosmetic search change: the
engine has always pooled a curated substitute group, and nothing in the interface could ask
for one. Twelve people buying coffee across three brands used to produce no order at all,
against a minimum they cleared twice over.

**Home is one row per thing you buy, and the row changes.** It used to list each
declaration three times — a verdict, then demand and a blocker, then a cadence — and the
changing-world beat was carried by a minimum-quantity number at the tail of a sentence,
which goes *up* when the better quote lands. The three answers now appear as three states
of the same row, in one frame, with what the last run found kept underneath and dated.

**The supplier terms arrive as a file.** Two sheets in `demo-data/`, committed and
readable in the repository, really parsed. The claim is *real ingestion pipeline, synthetic
dataset* — not real supplier data. Riverbend Wholesale does not exist.

The spine is unchanged: one declaration answered three times, from three world states,
with the demand never moving.

| World state | Pool's answer |
| --- | --- |
| no supplier quote | nothing to evaluate — the blocker is supply, not people |
| a split-case sheet arrives | the supplier will sell, and it is still not worth doing |
| a case-programme sheet arrives | viable — and the same seven people get the order |

Nobody is recruited between those rows. No declaration is edited, no quantity moves, no
household joins. One supplier offer row lands, twice, and the deterministic layer
recomputes.

**The canonical whey lifecycle is not walked live.** It is the Showcase, in its own copy of
Demo University, and it stays a backup and a regression proof rather than the recording's
subject.

## Before recording

1. Run `make qa` and the release checks.
2. Use the deployed URL and open a fresh disposable workspace.
3. Confirm the drawer says: discovery uses AgentCore / Bedrock; the lifecycle uses the
   deterministic planner; payments and supplier ordering are simulated.
4. A fresh workspace opens on **setup**, not on somebody's home screen. Pool knows nothing
   about you: no name, no card, no declarations. That is the opening.
5. Decide the name you will type. Any name works and none is special.
6. Keep the form's default quantities. They are what a visitor would leave alone, and the
   case arithmetic is real — the two-bag default is what lands the order on a whole case
   boundary, and a different number is a true outcome and a weaker beat.
7. Keep one continuous browser journey. Switching to a different run or workspace is never
   permitted.
8. Have both CSV sheets on the desktop, and **import them in order**. The split-case sheet
   first.
9. Do **not** pre-record the supplier quotes. The starting state has none, and the demo
   depends on the judge watching them arrive.

---

## The changing-world walkthrough — about 4:00

## 0:00–0:10 — Who is using this

**A brand-new workspace.** Pool opens on *What should Pool call you?*

Type a name. Say it out loud: this is your account, not a seeded persona you have been cast
as.

## 0:10–0:20 — Where you are, honestly

**Continue.** *Pool works street by street.*

One community is found, and you join it. Say the two things this screen exists for: Pool is
local, because the people it finds have to be close enough to share a pickup — and this
community is invented, so Pool has not asked the browser for a position and has not guessed
one. Whoever is watching, in whatever city, is exploring Demo University from the inside.

Ten seconds, because it is the one place a demo like this normally lies.

## 0:20–0:45 — Two things you buy

**Join Demo University.** **Type a category** — `rice` — not a memorised product name.

The first result is the family: **Rice**, *any of 13 — Pool buys whichever works out
cheapest*. Underneath, one click away, are the thirteen individual bags, and any of them is
equally declarable.

This is worth ten seconds of narration, because it is the difference between a product that
finds overlap and one that fragments it: six neighbours who each named a different bag of
rice are six people Pool cannot help. Somebody who genuinely means one exact product still
picks it, and Pool then says plainly when it cannot source that row.

Pick **Rice**, keep the defaults, **Add this**. Then type `towels` and add **Paper towels**,
also on defaults.

Two things, and neither of them is something Pool can currently buy. That is deliberate:
this recording is about what Pool does when the answer is no.

Say once, over the results: these are real products from a public catalogue; the supplier
prices later in the demo are invented, and the app says so on its About page.

## 0:45–0:55 — How much Pool may do

**Continue.** Choose **Ask me first**, add the test card, finish.

Both parts in one breath: the card is simulated and no real money exists, and *ask me first*
is why Pool will stop and put a question in front of you rather than spending on your behalf.

Setup is over. Four screens, no group created, nobody invited.

## 0:55–1:15 — The question, before the answer

**Home.** Do not click yet. One card, two rows, and the rice row is the whole thesis:

> **Rice** — WATCHING · No verified supplier yet
>
> **7 people near you** buy this — 24 bags standing, 2 of them yours
>
> No supplier Pool has verified sells this in bulk yet, so there is nothing to price a group
> order against.

Read them in that order and say why the order matters. Seven people already buy this. You
did not find them, you cannot see them, and none of you organised anything. What is missing
is not demand — it is a supplier. Those are completely different problems, and most software
would have shown you an empty screen.

The status word is the whole state, and the sentence under it is the reason. That is all
either row ever says.

## 1:15–1:35 — The first live run

**Click `Ask Pool to check now` exactly once.**

Say the honest version, because the screen already does: in the real product Pool watches
these declarations on the community's pool day; nothing is scheduled in the demo account, so
the coordinator starts when you press it.

Hold the wait. It names Amazon Bedrock AgentCore, names the region, runs a real elapsed
clock, resolves the one thing the browser actually observed — that it sent the request — and
says on screen that nothing in between is being animated.

The answer is two refusals, for two different reasons:

> **Jasmine rice, 5 lb** — No supplier Pool has verified sells this in bulk yet.

> **Paper towels, 6 rolls** — 6 compatible packs were declared near you, and the supplier
> will not sell fewer than 48.

Pool answered both things you told it, and both answers are no. Read the tail out loud,
because it is the promise the rest of the recording keeps:

> Your declaration stays standing, and Pool keeps watching.

Note in passing that the run names *Jasmine rice, 5 lb* while your row says *Rice*. That is
the point of a family declaration: you said what you buy, and Pool picked the exact product
it would actually buy for you.

## 1:35–2:15 — The world changes, and no agent runs

**Footer → Behind Pool → Operations console → Import a supplier quote sheet.**

Frame the actor before touching anything: this is an **operator** screen, not yours. A member
cannot conjure a wholesale quote. What a member does is say what they buy; what changes
whether that can be acted on is the world.

The panel names the two committed sheets and their digests. **Import
`riverbend-split-case.csv`.** What comes back is the file, as read:

> riverbend-split-case.csv · 1144 bytes · sha256 8e0f4e6e049d14b1…
>
> 1 record found · 1 valid · 0 rejected

The line number in the table is line 18, because that is where the row actually is in a file
that explains itself in comments first. This is a real CSV parser on real bytes — a
malformed row fails and says which line it was on — and the sheet is committed, so a judge
can read it before uploading it. Say the boundary out loud: **real ingestion pipeline,
synthetic dataset.** Riverbend Wholesale does not exist.

Say what just happened and what did not: one supplier offer row was written. No declaration,
no household, no pool, no past run record was touched — and **no agent ran**.

**Back to Home.** The row has moved on its own:

> **Rice** — WATCHING · **Supplier found — not cheaper**
>
> 7 people near you buy this — 24 bags standing, 2 of them yours
>
> There is enough demand, but buying it together would not actually be cheaper once
> collection and fees are counted.
>
> Last checked *hh:mm*: No supplier Pool has verified sells this in bulk yet.

This is the beat to slow down on, and it is now one frame. The first blocker is gone: there
is a supplier, the minimum clears, the units fill whole cases. And Pool still says no,
because once a fulfiller's pay, card processing and Pool's own fee are counted the group pays
more than its members would pay alone. **Removing an obstacle did not buy a yes.**

The demand line is identical to the one before the import. And the dated line underneath is
the run's own finding, unchanged — history and present, side by side, with Pool not editing
the first to agree with the second.

**Back to Operations. Import `riverbend-case-programme.csv`.** Then **Home**:

> **Rice** — WATCHING · **Worth doing — Pool has not run yet**

Same demand. Same dated history. Third answer.

## 2:15–2:40 — The second run, on the changed world

**Click `Check again now`.**

Same declaration. Same six neighbours. Same quantities, same dates, same rules. The only
thing that changed is a supplier fact somebody imported ninety seconds ago.

> Your 2 bags · about $17.53 instead of $22.98 buying alone.
> With 6 others · collect from Central Quad pavilion.

Open **Why this worked** and read three lines, not all six:

> Together that reached the supplier's 16-unit minimum. · It fills 3 complete cases with
> nothing left over. · Pool compared 2 supplier prices and took the one at $6.25 a unit,
> ahead of $9.75. · Collect from Central Quad pavilion — the best of 4 pickup points for
> this group.

That third line matters: both sheets are still on file, and the evaluator picked the better
one. Nothing was deleted to make this work.

**Read the timing line off the screen rather than from here.** It is the one figure in this
block that moves with the calendar — how much of the demand was already due against how
much was pulled forward under permission members had already given depends on today's date
relative to their cadences. Both readings are true; quoting a fixed one would eventually
have the presenter saying a number the page does not show.

And point at paper towels, still standing, still refused on the supplier minimum. The world
changed for one product, not for the demo.

## 2:40–3:05 — Host first, then the one question

**Demo University drawer → the host accepts the fulfilment job → Let Pool work the queue.**
Back to Home.

The button names the host Pool actually ranked and offered the work to. Offering to host did
not claim the job: Pool ranked candidates and offered it to the best eligible one. Only after
acceptance can host pay enter the exact buyer price — which is why the number above was
labelled an estimate, and why it moves slightly when the exact one arrives.

You are now asked to approve the exact amount, with the policy engine's own reason under it:
*member is on Ask Me — commitment requires explicit approval*. Answer it.

## 3:05–3:40 — Same-run technical proof

**Footer → Behind Pool.** Everything a judge can inspect is on one page, each with a sentence
saying what it proves. Take **Technical proof**.

Show, without invoking anything:

- Amazon Bedrock AgentCore Runtime live, region, model provider and model;
- the exact run id and resulting pool id;
- `Pool created_by_run`, equal to that run id;
- the stored tool sequence, outcome and termination;
- authoritative run + pool readback from the same workspace;
- browser → Lambda → AgentCore → Strands / Bedrock → typed tools → deterministic services →
  DynamoDB → browser.

Two runs are stored, not one, and they disagree. That is the proof this version adds: the
same member's same declaration, evaluated twice against two different world states, with both
verdicts kept.

While you are here, the map is worth five seconds: the ring around each pickup point is the
distance the matcher actually allows, so overlapping rings are where one order can serve two
neighbourhoods.

Close on the collective outcome rather than a feature list:

> The buyers get viable bulk economics without organising the group. The host earns recorded
> compensation. The supplier receives one clean bulk order. Nobody organised the group. Pool
> noticed — and kept noticing.

---
