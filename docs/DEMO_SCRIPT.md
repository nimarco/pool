# Demo video script — 5:00 maximum

**Not yet recorded.** This is the shooting script.

Presentation is 20% of the score and Design is another 20%, so the video has to carry the
idea, not just the features. The single most memorable thing Pool does is **repair itself
after a dropout** — that gets the most screen time.

---

## Before recording

```bash
make install
make api          # terminal 1
make web          # terminal 2
```

Then in the browser: click **Reset demo**, then **New workspace**. Confirm the dashboard
shows 25 households / 29 needs and no pools.

**Checklist**
- [ ] Browser at 1440×900, zoom 100%, light mode
- [ ] Browser chrome and bookmarks hidden
- [ ] No personal tabs, no notifications, do-not-disturb on
- [ ] `make demo` run once beforehand to warm everything
- [ ] Terminal font large enough to read at 1080p
- [ ] Nothing on screen contains a real name, address, or credential

---

## 0:00–0:30 — The problem

**Visual:** the landing page. Slow scroll through the three-step explainer.

> Buying in bulk is dramatically cheaper. Most households can't, because a hundred-and-fifty
> pound minimum order isn't something one family needs.
>
> Eight families together? That works. But somebody has to find those eight families,
> split the quantities, compare suppliers, work out whether the saving is even worth it,
> arrange a pickup, and chase everyone for a reply. Then someone drops out and they start
> over.
>
> That work is why neighbourhood buying clubs mostly don't exist. It's not a missing app.
> It's a missing organiser.

## 0:30–0:55 — The insight

**Visual:** cut to the Needs table. Scroll it.

> Pool removes the organiser.
>
> Households declare what they routinely buy — once — with their own limits. Fifteen pounds
> of rice every six weeks. At least twenty-five percent cheaper. Nothing over thirty
> dollars. Pickup within ten minutes.
>
> Then they close the app. Nobody here has asked to organise anything. Nobody has posted a
> listing. These are just twenty-nine standing declarations.

## 0:55–2:00 — Discovery, live

**Visual:** Neighbourhood view. Click **Run a background scan**. Let the run land.

> In production this runs on a schedule, unattended. I'm triggering the identical code
> path so you can watch it.

**Visual:** the run chip appears — point at the tool sequence.

> The agent called three tools. It asked what demand was going unserved, evaluated the
> most promising product, and formed a pool. It chose the product and the pickup site
> itself.

**Visual:** the rice pool card. Point at the numbers.

> Eight households in the same few blocks each wanted jasmine rice. None of them knew.
> Aggregated, their hundred and fifty-five pounds clears a wholesaler's minimum — which
> unlocks twenty-five pound bags at sixty-nine cents against a dollar thirty-five retail.
>
> Ninety-nine dollars saved across the group. Forty-two percent below buying alone.
>
> Every one of those numbers came from a pricing tool, not from the model. The agent
> decides what to investigate. Deterministic code decides what's true.

**Visual:** the map.

> And note what the map does *not* show. Approximate positions only — no addresses, no
> names. Pool is a neighbourhood product, so location privacy is a design constraint, not
> a setting.

## 2:00–2:45 — The autonomy boundary

**Visual:** the Decision Inbox.

> Seven of those households had already told Pool the terms they'd accept, so Pool
> committed them without asking. That's the point — they wanted rice, not a notification.
>
> Two are on *Ask Me*. They get one question each, with the numbers already worked out.
> Your share, nine dollars thirty-five. Four minutes away. Join, or skip.

**Visual:** point at the "Why you're being asked" line.

> And Pool says *why* it had to ask. That's not generated text — a policy engine evaluated
> six rules and this is the one that failed.

**Visual:** click **Join** on both.

> Now the threshold is met.

## 2:45–3:35 — The dropout, and the repair

**Visual:** open the pool → **Withdraw** the largest participant.

> Here's the failure that kills real buying clubs. The biggest participant pulls out.
> Thirty pounds gone. The pool drops to a hundred and twenty-five against a hundred and
> fifty minimum. The deal is dead, and in a normal group chat this is where seven people
> get a message asking them to fix it.

**Visual:** back to the neighbourhood → **Run a background scan**.

> Pool notices the pool is short and goes looking.

**Visual:** the activity feed updating. Let it land, then read the entry aloud.

> It widened the search beyond the original block, found a household with compatible
> demand whose own Smart Join rules permitted the join, added them, and restored the
> threshold.
>
> **Nobody else was contacted.** The other seven households never knew anything happened.
>
> That's the whole product in one event: the coordination work that used to fall on a
> volunteer, done by an agent, quietly.

## 3:35–4:15 — How it's built

**Visual:** the Agent activity tab, expand a trace.

> Under it: a single Strands agent on Amazon Bedrock, deployed to AgentCore Runtime.
>
> Every run is bounded — eight model iterations, twenty-five tool calls, duplicate-call
> detection, a wall clock. Those aren't instructions to the model, they're hooks in the
> event loop that cancel or terminate. During development one of them caught a genuine
> infinite loop in my own planner code.
>
> The trace shows tool names, counters and a termination reason — deliberately not model
> reasoning. Explainable, without exposing chain of thought.

**Visual:** architecture diagram, five seconds, no line-by-line reading.

> DynamoDB is the source of truth for money and membership. Amazon Location does routing.
> EventBridge drives the background scan — and ships disabled, because this runs on
> student credits and a forgotten schedule is how those disappear.

## 4:15–4:45 — Impact

**Visual:** the Impact tab.

> Computed from stored state, not asserted. Ninety-nine dollars saved across nine
> households. Seven commitments made without anyone being interrupted. Two questions
> asked. One pool repaired.
>
> This is synthetic demonstration data — invented households, invented suppliers. Not
> customers, not traction.

## 4:45–5:00 — Close

**Visual:** back to the neighbourhood map, slow zoom out.

> Eight people wanted the same thing. None of them knew. None of them organised anything.
>
> Pool noticed.

---

## Alternative closes

- "The best group buy is the one nobody had to run."
- "Pool doesn't help you organise a buying club. It means nobody has to."

## Cut first if over time

1. The map privacy aside (0:55–2:00) — 12 s
2. The architecture diagram beat — 8 s
3. The Needs table scroll, shorten to a glance — 10 s

**Never cut:** the dropout recovery. It is the demo.
