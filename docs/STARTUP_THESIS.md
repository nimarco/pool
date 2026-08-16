# Startup thesis

The argument for Pool as a business, with its assumptions stated rather than implied.

---

## The behaviour already exists

Nobody has to be convinced that group buying works. It already happens, informally, on
every dense campus:

> "I can buy 50 tubs of protein powder in bulk for way cheaper than the store. DM me if
> you want one."

What does not exist is a way to do it that is not miserable. The informal version puts
the whole burden on one person:

```
guess demand → front personal money → buy speculative stock → advertise afterwards
→ answer DMs → track quantities → chase payment → arrange meetups → risk leftovers
→ handle no-shows
```

That person is not being paid, the risk is entirely theirs, and it stops the moment they
get bored. This is why bulk buying stays a favour between friends instead of becoming
infrastructure.

## The inversion

Pool aggregates demand **before** the purchase instead of after it.

```
declare recurring needs → discover compatible demand → evaluate a real bulk offer
→ form a candidate pool → recruit paid fulfilment → compute exact landed economics
→ collect authorisations → lock → buy once → distribute in one window
```

Three consequences follow immediately, and they are the whole business:

1. **Nobody speculates on inventory.** The goods are sold before they are bought.
2. **Nobody is the unpaid organiser.** The coordination is the software's job, and the
   physical work is a paid one.
3. **Nobody has to notice the opportunity.** The system finds it, which is the only way
   a long tail of small recurring purchases ever becomes worth pooling.

## Why an agent, not a marketplace

A marketplace waits for someone to start something. That is exactly the step that does
not happen. The interesting work is *searching a space nobody asked about*: five students
separately buy protein powder monthly; discovering that a viable group could exist means
evaluating combinations of demand, supplier minimums, case structures, timing windows,
fulfilment capacity and landed cost — and doing it repeatedly, quietly, for opportunities
that mostly turn out not to be worth it.

Concluding "nothing worthwhile this week" and telling nobody is a success state. A
marketplace cannot have that behaviour; an agent can.

---

## Initial wedge: college campuses

Campuses are the first Community type because of what they physically are:

- high residential density inside a walkable radius
- heavily overlapping recurring needs across a narrow demographic
- dorm and apartment clusters that make pickup trivially local
- public common spaces usable as pickup nodes
- predictable weekly schedules, so a concentrated Pool Day works
- a population already willing to take an occasional paid side gig

Likely early categories are sealed, shelf-stable, repeat purchases: protein powder,
energy drinks, coffee, detergent, paper products, toiletries, snacks, pet supplies.
Nothing perishable, nothing that has to be opened or divided.

**Community, not campus, is the domain concept.** The same model covers apartment
complexes, dense neighbourhoods, workplaces, and community organisations. A university is
one `CommunityKind`. Building it campus-shaped would have been the mistake.

---

## The three sides

```
BUYERS              fragmented, recurring, individually too small for bulk pricing
SUPPLIERS           want volume and predictability; minimums exist for a reason
FULFILMENT LABOUR   local, occasional, motivated by a fair per-job rate
```

Pool's job is to make a transaction exist that works for all three, plus itself.

### Buyers

Bulk pricing quietly favours whoever can afford a larger upfront purchase, has somewhere
to put it, and personally consumes enough to justify the quantity. That is a real
asymmetry and it is the honest impact claim: **Pool lets several people reach economies of
scale without each of them carrying the full capital, quantity, storage, logistics, and
coordination burden alone.**

Not a charitable claim, and not one that needs inflating.

### Suppliers

A minimum order quantity is a supplier saying "this price is available at this volume".
Aggregated demand is exactly the thing that clears it. The long-term version is more
interesting than a discount: Pool can eventually tell a distributor

> "we expect 84 financially eligible buyers for 84 units next month"

which is a fundamentally better object than a coupon. Committed, pre-verified demand is
worth quoting against directly. That is the deeper supply thesis, and it is documented
rather than built.

### Fulfilment

Someone has to physically collect and hand out the goods. Making that a paid role, priced
by the work actually done, is what turns a favour into something repeatable. Compensation
scales with orders, distance, and load; the run is earned once the goods are collected and
held, so a buyer no-show cannot erase it.

Crucially the host does **not** front the purchase. Buyers' captured funds cover the
order. A model that asks a student to underwrite four hundred dollars of stock and hope
everyone shows up has just reinvented the problem.

### Pool

The platform fee is a transparent share of the savings the group actually achieved.
Aligned by construction: no savings, no fee. It appears as a line item on every offer.

If any of the four does not work, the correct outcome is that no pool forms. A system
that manufactures viability by hiding a cost, ignoring someone's stated limits, or
silently subsidising a participant is not a business — it is a subsidy with a funnel.

---

## Capital and timing

**Capital:** buyers fund merchandise, fulfilment, processing, and the platform fee. Pool
does not float inventory. Hosts do not front money. Nobody carries risk they were not
paid to carry.

**Timing:** recurring needs plus Community-configured Pool Days plus per-member
early-purchase windows. Pool does not buy the instant a minimum is touched — there are
explicit deadlines for formation, host acceptance, final offer, authorisation, lock, and
distribution. Demand can be pulled forward only inside the window a member authorised.

---

## Cold start

A three-sided marketplace with no liquidity is the classic way to fail. The plan is to
not need one:

| Side | First pilot |
| --- | --- |
| Community | One dense Community with explicit membership rules. Not a city. |
| Buyers | The part actually being validated. Everything else is scaffolding. |
| Supply | An operator phones wholesalers and records verified offers by hand. |
| Fulfilment | Founder as the fallback fulfiller when nobody volunteers. |

Then open the sides that were faked, in order: host marketplace first (it is the easier
one to recruit for), then supplier self-service, then negotiated direct offers.

**Supply evolution:** manual verified offers → supplier portal → direct negotiated quotes
against committed demand.

**Fulfilment evolution:** single fulfiller → partner business hubs → supplier delivery to
a hub, or multi-pool runs batched into one trip.

**Geographic evolution:** campuses → apartment complexes → dense neighbourhoods →
workplaces and community organisations. Each is a new `CommunityKind`, not a new product.

---

## Assumptions, stated plainly

These are the things that would sink it, listed so they can be tested rather than
discovered:

1. **Enough overlapping recurring demand exists inside one Community** to clear real
   supplier minimums on a weekly cadence. Untested.
2. **The saving survives honest costs.** After host pay, processing, and the platform fee
   there must still be a margin people care about. The demo produces ~23% net on a
   realistic-looking basket, but with invented prices.
3. **People will fill in recurring needs once and then leave the app alone.** If it needs
   attention every week, the coordination burden has just moved.
4. **Someone will take the fulfilment job at a fair rate.** Plausible on a campus;
   unproven.
5. **Suppliers will quote to a coordinator.** Very likely at wholesale, unknown for
   direct manufacturer relationships.
6. **The merchant-of-record structure is workable.** This is the largest unresolved
   question — see `PILOT_READINESS.md`.

## What would falsify it

- Demand within a Community is too thin or too fragmented to clear minimums.
- Landed savings after fulfilment are small enough that people would rather just buy one.
- Nobody wants the host job at a rate buyers will fund.
- The legal structure forces a shape that erases the margin.

None of these are answered by building more software. They are answered by one small
controlled pilot — which is why the architecture is designed so that pilot needs no
rewrite.
