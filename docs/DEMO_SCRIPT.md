# Demo rehearsal script

Two flows. The first is the submission recording; the second is the version for somebody
who has ninety seconds and no interest in AWS.

Both are navigation-and-timing rehearsals, not word-for-word voiceovers.

The line everything hangs off:

> **Nobody organised the group. Pool noticed.**

And the line this version cashes, which is the harder half:

> **Pool kept watching, the world changed, and the answer changed with it.**

## What changed, and why

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

# A. The submission recording — about 4:00

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

> 22 bags were already due, and 2 more were bought early under permission those members had
> already given. · Together that reached the supplier's 16-unit minimum. · It fills 3
> complete cases with nothing left over. · Pool compared 2 supplier prices and took the one
> at $6.25 a unit, ahead of $9.75.

That last line matters: both sheets are still on file, and the evaluator picked the better
one. Nothing was deleted to make this work.

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
