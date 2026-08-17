# Demo script — five minutes

One journey. The implementation is sophisticated; the story must not be.

**The line everything hangs off:**

> **Nobody organised the group. Pool noticed.**

Do not spend the video explaining every state, every adapter, every host formula, or
every future legal question. Show one purchase happening.

The rubric is five equally weighted criteria, and the video is graded on **Presentation**
while also being most judges' only exposure to **Design** and **Potential Impact**. So
the video's job is not to enumerate features. It is to make one purchase legible, prove
the agent is real, and prove the money is honest.

---

## Before recording

```bash
make qa          # everything green before you film anything
make dev         # API :8000, web :5173
```

Record against the **deployed URL**, not localhost, so the live AgentCore action is
available and the address bar is itself evidence. Open it, use **Demo University → Reset
Demo University**, and leave the browser on Home.

Say what is synthetic once, early — the drawer's *What is real here* block has the exact
wording. Everything after it is easier to trust.

Have a second terminal with `make demo` typed but not run — it produces the same
lifecycle as a text transcript from the same code path, and it is a legitimate fallback.

---

## 0:00–0:20 — The problem

**Show:** Pool's home screen, signed in as Rosa.

> Every campus already does this. Someone posts: *"I can buy 50 tubs of protein powder
> way cheaper than the store — message me if you want one."*
>
> It works, badly. That person guesses the demand, fronts their own money, answers thirty
> messages, chases payment, and eats whatever is left. They are not paid for any of it.
> So it happens once and stops.

## 0:20–0:50 — What a member actually has

**Point at:** *What you buy anyway*.

> This is Pool. Rosa told it two things she buys regularly and then forgot about it. No
> group, no chat, no sign-up sheet — and twenty-four people in this community have each
> done the same thing, thirty-three standing needs between them.

**Point at:** the figure beside *Pool is watching*.

> Each line is one person's restock date. Eight fall due in the same week — eighteen
> units, and the supplier will not sell fewer than twenty-four. Two more would not have
> bought for weeks, and Pool may bring them forward *only* because those two authorised
> an early purchase. Their six units close the gap exactly.

## 0:50–1:20 — Pool notices

**Click:** *Find opportunities.*

> Nobody creates a group. Pool's coordinator looks across the standing needs and decides
> whether an order is worth forming at all.

**Show:** the opportunity that appears.

> Ten people. Twenty-four units. A pool exists that none of them asked for.

**Click:** *Open the pool.*

## 1:20–2:00 — The record, and the money

**Show:** the pool's Overview, then Economics.

> This is a real record, not a summary. Who is carrying it, where it is collected, and
> thirteen checks that all have to pass before anything is bought.
>
> And the part I would want as a buyer. Seven hundred and fifty-six dollars of
> merchandise. Forty-four sixty-eight to the host — funded by the buyers, not by us.
> Twenty-eight of card processing. Thirty-two seventy to Pool.
>
> All-in eight sixty-one forty-four, against eleven twenty-seven if these ten people had
> each walked to the campus store. Twenty-three point six percent, *after* everything.
> Pool's fee is a share of the saving, so no saving means no fee.

## 2:00–2:40 — The other nine people

**Open:** *Demo University → Demo controls.*

> Pool is a three-sided product and I am one person, so this is where I act for everyone
> else. Every one of these calls the same endpoint that participant would — the host
> answering an offer, the buyers answering theirs.

**Click:** *accepts the fulfilment job*, then *Let Pool work the queue*.

> The host accepts, so the price can be exact. Pool prices it, and eight of these buyers
> had already told it their rules — minimum saving, maximum spend, maximum walk. Those
> pass, so Pool commits for them. Two did not, so they get one question each.

## 2:40–3:20 — Failure, and repair

**Show:** the pool's Buyers, and the record's count.

> And one card is declined. This is where a group buy normally dies in a chat.
>
> Ten people were matched. One payment failed, one replacement was recruited — so ten
> people still buy, and the record carries eleven memberships. The declined one stays
> here. A record that edits out its failures is not a record.

**Click:** *Buyers answer*, then *Let Pool work the queue*, then *Open the pickup
window*, then *Everyone collects their order*.

> Funded, locked, ordered — clearly labelled simulated — and handed over against a
> one-time code that works exactly once.

## 3:20–4:10 — The agent is real

**Go to:** the pool's *Activity* tab → **Agent execution**. Press **Run the deployed
agent**.

> The pool at the start of this was found by the coordinator deployed on Amazon Bedrock
> AgentCore Runtime — a real model, in a session generated per invocation, working on
> this visitor's own DynamoDB workspace. Not a copy of it. The row you have been reading
> all the way through carries that run's id.
>
> Everything after that ran on the server — the same Strands event loop, the same tools,
> the same domain arithmetic, with a deterministic planner in the model's place. That is
> deliberate: a product that needs a paid model call to render every page is a product
> that breaks in front of someone.
>
> This button runs the deployed one again, from the auditor's side. Ten to twenty seconds.

**While it runs, point at:** the tool catalogue.

> These are the only twelve things the model can reach. No shell, no query language, no
> generic mutation. Seven read, four commit something, one ends the run — and every
> committing tool is idempotent by an explicit key, because agent systems retry.

**When it returns:** point at the marked tools, the three durations, then the block
below them.

> There is what it chose, in order. Time inside the agent, time inside AWS, and the
> browser's own round trip — three separately measured numbers. If this call had failed,
> the screen would say so. There is no code path in this repository that fabricates a
> run.
>
> And this last part is not the agent's report — it is what the database held afterwards,
> read back by the server from the same table it serves every other page from. That is
> the difference between an agent that says it did something and one that did it.

## 4:10–4:40 — The architecture, in one sentence

**Show:** the *What is running where* block at the foot of Agent execution, or the
diagram.

> Browser to a Lambda Function URL, which signs an invocation of AgentCore Runtime bound
> to this visitor's workspace. Inside it, a bounded Strands loop and Amazon Bedrock. State
> in one DynamoDB table, isolated per visitor — and the runtime writes that same table, so
> the agent on AWS is the one that formed the pool. It can read and write there; it cannot
> delete.
>
> And the rule underneath all of it: **the model decides what to do; deterministic code
> decides what is true.** Every price on every screen came from a tool, not from a
> sentence a model wrote.

## 4:40–5:00 — Who it is for, and the close

**Show:** Community.

> A community is a trust-and-density boundary — a campus, an apartment block, a
> workplace, a school. Bulk pricing normally favours whoever can afford a bigger purchase
> up front and has somewhere to put it. This is a way to reach that price without each
> person carrying the capital, the quantity, the storage and the coordination alone.
>
> The buyer saves. The host earns for work they actually did. The supplier gets a clean
> bulk order.
>
> Nobody organised the group. Pool noticed.

---

## Rules for the recording

- **Say what is simulated, once, early.** It buys credibility for everything after it.
- **Never say "deployed"** unless it is, at that moment, deployed and on screen.
- **Never say a number the screen is not showing.**
- Do not narrate the state machine. Do not narrate the adapters. Do not explain the
  merchant-of-record question. All of it is in the docs for anyone who wants it.
- Arrow keys step the lifecycle reader, so both hands stay off the mouse there.
- If the demo breaks on camera: **Demo University → Reset Demo University** and re-run.
  It is deterministic and will produce the same numbers.
- The thirteen-stage reader lives on the pool's *Activity* tab as **How this pool
  happened**. Use it if you want the failure and the repair spelled out with figures —
  but the product already showed both, so it is optional.

## Backup

If the UI misbehaves, `make demo` prints the same lifecycle as a transcript from the same
code path. It is a legitimate fallback, not a different demo.

If the live AgentCore action fails on camera, **say so and move on** — the screen already
says it, and a recorded failure is worth more than a re-shoot that hides it.
