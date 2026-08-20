---
name: Pool
description: A field ledger for an agent that only coordinates a purchase when the numbers actually work.
colors:
  paper: "#f7f4ef"
  paper-raised: "#fffdfa"
  paper-sunken: "#efeae1"
  paper-deep: "#e7e1d5"
  ink: "#17150f"
  ink-muted: "#575145"
  ink-faint: "#6f6759"
  rule: "#ded7c9"
  rule-strong: "#c6bdab"
  moss: "#3d6b4c"
  moss-bright: "#4f875f"
  moss-soft: "#e4ede4"
  moss-line: "#b2cbb7"
  graphite: "#384b5e"
  graphite-soft: "#e5ebf1"
  graphite-line: "#b6c4d2"
  clay: "#a0512a"
  clay-soft: "#f6e9df"
  clay-line: "#e0bda1"
  stop: "#8c3020"
  stop-soft: "#f6e2dd"
typography:
  hero:
    fontFamily: "Instrument Serif, Iowan Old Style, Georgia, serif"
    fontSize: "clamp(40px, 6.2vw, 76px)"
    fontWeight: 400
    lineHeight: 0.98
    letterSpacing: "-0.03em"
  display:
    fontFamily: "Instrument Serif, Iowan Old Style, Georgia, serif"
    fontSize: "clamp(28px, 3.4vw, 40px)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "-0.018em"
  figure:
    fontFamily: "Instrument Serif, Iowan Old Style, Georgia, serif"
    fontSize: "34px"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "-0.02em"
    fontFeature: "tabular-nums"
  title:
    fontFamily: "Instrument Serif, Iowan Old Style, Georgia, serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  value:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    fontFeature: "tabular-nums"
  label:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    letterSpacing: "0.05em"
  caption:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 550
  mono:
    fontFamily: "ui-monospace, SF Mono, JetBrains Mono, Menlo, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
rounded:
  xs: "2px"
  focus: "3px"
  sm: "4px"
  control-sm: "7px"
  md: "8px"
  control-lg: "10px"
  lg: "14px"
  pill: "999px"
spacing:
  hairline: "1px"
  xs: "6px"
  sm: "14px"
  grid: "22px"
  gutter: "32px"
  section: "34px"
  page-top: "34px"
  page-bottom: "96px"
  max-width: "1160px"
components:
  button:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "9px 15px"
  button-hover:
    backgroundColor: "{colors.paper-sunken}"
    textColor: "{colors.ink}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "9px 15px"
  button-primary-disabled:
    backgroundColor: "color-mix(in srgb, #17150f 62%, #f7f4ef)"
    textColor: "{colors.paper-raised}"
  button-accept:
    backgroundColor: "{colors.clay}"
    textColor: "{colors.paper-raised}"
    rounded: "{rounded.md}"
    padding: "9px 15px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "9px 15px"
  button-sm:
    rounded: "{rounded.control-sm}"
    padding: "6px 11px"
    height: "32px"
  button-lg:
    rounded: "{rounded.control-lg}"
    padding: "13px 22px"
  panel:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
  chip:
    backgroundColor: "{colors.paper-sunken}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  input:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "9px 11px"
    height: "38px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.control-sm}"
    padding: "6px 11px"
    height: "30px"
  nav-item-current:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    padding: "9px 13px"
    height: "38px"
  tab-current:
    textColor: "{colors.ink}"
  meter-track:
    backgroundColor: "{colors.paper-deep}"
    rounded: "{rounded.pill}"
    height: "6px"
  meter-fill:
    backgroundColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "6px"
  meter-fill-short:
    backgroundColor: "{colors.ink-muted}"
---

# Design System: Pool

## Overview

**Creative North Star: "The Field Ledger"**

Pool looks like a ledger somebody keeps by hand and can hand to an auditor. Warm paper
(`#f7f4ef`), dark ink, hairline rules doing the structural work, figures set in tabular
numerals so columns of money line up, and a serif display face for the numbers and names
that matter. A ledger's authority does not come from decoration; it comes from being
inspectable line by line. That is exactly the claim this product makes about an autonomous
agent, so the interface makes the claim in its own material rather than asserting it in
copy.

The density is low and the surfaces are quiet. Colour is scarce and strictly semantic:
three hues that mean *who was responsible* — moss for the agent, graphite for
deterministic code, clay for a person — and one red that means something broke. Nothing
else gets to be coloured. Success, ownership, progress and magnitude are all neutral, and
when a screen has no attribution to make, it is paper, ink, and rule. The reward for that
restraint is that the moment colour appears, it means something, and a viewer learns the
grammar in one screen without a legend.

The system is deliberately unlike four neighbours. It is not an operations console, not AI
product chrome, not a consumer savings app, and not an enterprise procurement tool. The
first is a lived failure rather than a taste: an earlier build put the same information on
screen three times in dense counter grids, and a correct system read as an admin dashboard.

**Key Characteristics:**

- Warm paper and ink; four paper tones carry depth instead of shadow.
- Instrument Serif for names, headlines and figures; system sans for everything read in
  sentences; monospace only for identifiers.
- Colour is attribution, never emphasis. Three semantic hues, one failure red, and no
  fourth accent. Success, ownership and magnitude are neutral.
- Tabular numerals wherever a number could be compared to another number.
- Hairline rules (1px) as the primary structural device.
- Full dark mode, token-for-token, at the same semantic meanings.
- Attribution is redundantly encoded as shape — diamond, square, circle — so it survives
  greyscale, colour-blindness and video re-encoding.

## Colors

A warm paper-and-ink neutral field, punctuated by exactly three attribution hues and one
failure red. Values are in the frontmatter; this section says what each one is *for*.

**The three hues are the actor triad, and they attribute an action or a fact to one party.
They are not available for any other job.** Anything that is not an attribution — success,
completion, ownership, progress, magnitude, emphasis, chrome — is neutral. This document
defines **no exception** to that, deliberately: a single carve-out is how a semantic palette
becomes a decorative one.

### Primary

- **Ink** — the near-black text colour, and the fill of the primary action. Pool's primary
  button is ink on paper, not a brand colour, precisely because the brand's own hues are
  spoken for by attribution. Its hover stays inside the neutral family: the ink deepens and
  the shadow lifts. Ink is also what carries any neutral emphasis an actor hue is not
  allowed to carry — a filled meter, the reader's own units, a completed step.
- **Moss** — *the agent decided this.* The green of the Strands loop's own choices: a tool
  the coordinator selected, an opportunity it chose to investigate, an escalation it decided
  to raise. Nothing else. Moss is not a success colour.
- **Graphite** — *deterministic code computed this, and it could not have been otherwise.*
  A figure a tool returned, a viability verdict, a threshold that mathematically passed.
  Graphite is **not** used for generic chrome or for the focus ring; generic focus is ink.
- **Clay** — *a person is responsible for this.* A question waiting on a human, an answer a
  human gave, an action only a human can take. Clay carries the **needs you** consumer state
  and the affirmative control a person presses to accept something. The centre of the
  wordmark is clay because the thing at the middle of a pool is a person's order, not
  automation.

### Neutral

- **Paper** (base), **Paper Raised** (panels and controls, the lightest tone),
  **Paper Sunken** (recessed wells, chips, hover), **Paper Deep** (meter tracks, the
  deepest recess). Four tones, and depth is built from them.
- **Ink Muted** — secondary prose and inactive controls.
- **Ink Faint** — small text: labels, table headers, captions, state words. Set at ≥4.5:1
  against paper deliberately, rather than at whatever looked quiet.
- **Rule** — hairline dividers and panel borders. **Rule Strong** — control borders and
  anything that must read as an edge at video scale.

### Failure

- **Stop** with **Stop Soft** — something broke: a declined card, a malformed or refused
  import row, a form error, a run that did not complete. Stop is not a fourth actor hue; it
  attributes nothing, and it says only that a thing failed.

  **Stop is never used for Pool declining to coordinate.** That is a correct, computed
  outcome — the product working — and it stays in the neutral field with its reason
  attached. A declined *card* is stop; a declined *pool* is not.

### Named Rules

**The Attribution Rule.** The three hues mean who was responsible and nothing else. Moss is
the agent, graphite is deterministic code, clay is a human. They are never spent on
hierarchy, emphasis, decoration, mood, success, ownership or magnitude, and no fourth accent
may be introduced. A new colour may only be a tone inside an existing role. Colour is the
cheapest proof the interface has of the product's central claim; spending it on emphasis
destroys the proof.

**The Neutral-Unless-Attributed Rule.** If a mark does not name which party acted, it is
neutral. Progress, totals, completion, ownership and chrome are ink, ink-muted, ink-faint or
a paper tone, distinguished by tone, weight and type rather than hue. When such a mark does
need attribution, add the attribution tag beside it — never tint the mark itself.

**The Stop Means Broken Rule.** `stop` says a thing failed: a card declined, a row rejected,
a run that did not complete. It never says no. Pool declining to coordinate is a computed
result and renders in the neutral field with its reason attached.

**The Colour Is Never Alone Rule.** Every state distinguished by colour is also
distinguished by a word, and attribution is also distinguished by shape. A state must be
readable in greyscale, because the demo is watched as re-encoded video.

### Known deviations in the implementation

The rules above are normative. `apps/web/src/styles.css` does not yet obey all of them, and
the gap is recorded here rather than described as doctrine, so no later pass mistakes the
current CSS for the standard. Moss has drifted furthest: it is spent across roughly thirty
selectors as a general affirmative, which is exactly the drift The Attribution Rule exists
to stop.

| Where | Today | Should be |
| --- | --- | --- |
| `.btn-primary:hover` | ink mixed 12% toward moss | ink deepened within the neutral family |
| `.btn-accept` | moss fill | clay fill — a person is affirming (5.58:1 with paper-raised) |
| `.status-chip.is-coordinating`, `.is-ready-to-collect`, `.is-done` | moss word | ink; clay stays on `.is-needs-you`, ink-faint on watching |
| `:focus-visible` (global) | 2px graphite | 2px ink, as `.control:focus-visible` already does |
| `.meter-fill` / `.meter-fill.short` | moss / clay | ink / ink-muted — a meter is magnitude, not attribution |
| `.casefit-unit.is-mine` | moss | ink — ownership is not an action |
| `.chip-live` | clay | ink with the pulsing dot; a live runtime is not a person |
| `.chip-ok`, `.wait-step.done`, `.onboard-*.is-done`, `.hop.done`, `.prov-verdict .ok`, `.product-sourceable`, `.scope-mine`, `.figure-accent`, `.ledger-line.gain`, `.hero h1 em`, `.ruler button.seen`, `.map-*`, `.legend-swatch.*`, `.env-dot` | moss as success / present / mine / emphasis / chrome | ink or a paper tone; moss only where the agent is the actor |
| `.banner`, `.wait-head`, `.wait-step.pending`, `.path` | graphite as chrome | ink-muted, except `.path` where the engine genuinely is the subject |
| `.chip-warn`, `.banner-warn`, `.hop.active` | clay as caution | ink-muted, unless a person is the one being waited on |

Graphite for computed magnitude — a meter, a threshold bar — was considered and rejected in
favour of neutral, so that a future pass does not reopen it: a data display is not an
attribution, and one exception would license the rest.

## Typography

**Display Font:** Instrument Serif (with Iowan Old Style, Georgia, serif)
**Body Font:** system sans stack (`ui-sans-serif`, `system-ui`, `-apple-system`, …)
**Mono Font:** system mono stack (`ui-monospace`, SF Mono, JetBrains Mono, Menlo)

**Character:** A single high-contrast serif at 400 weight against a plain system sans. The
serif is used for the things a ledger would write large — a name, a headline, a total — and
never for prose. Because it is the only typeface with personality in the system, anything
set in it reads as consequential; that scarcity is the hierarchy.

### Hierarchy

- **Hero** (Instrument Serif 400, `clamp(40px, 6.2vw, 76px)`, line-height 0.98,
  letter-spacing −0.03em): the product's opening claim, once per surface, balanced with
  `text-wrap: balance`.
- **Display** (Instrument Serif 400, `clamp(28px, 3.4vw, 40px)`, 1.08, −0.018em): page and
  section titles.
- **Figure** (Instrument Serif 400, 34px, 1.05, −0.02em, tabular): a single headline number
  — a total, a saving, a percentage. Ledger totals are set at 27px.
- **Title** (Instrument Serif 400, 19px, 1.2): the name of a thing in a list — the item on
  a watch row, a product, a person.
- **Body** (system sans 400, 15px, 1.55): all prose. Drops to 15px base at ≤560px with the
  gutter, never below.
- **Value** (system sans 600, 14px, tabular): a fact's value beside its label.
- **Label** (system sans 600, 11.5px, letter-spacing 0.05em, uppercase): state words,
  actor tags, and eyebrows. Actor tags sit at 0.04em.
- **Caption** (system sans 550, 12px, ink-faint): figure labels and secondary notes.
- **Mono** (system mono, 12.5px): identifiers only — run ids, pool ids, digests, ARNs.
  Never used for emphasis or for prose.

### Named Rules

**The Serif Means Consequence Rule.** Instrument Serif is reserved for names, headlines and
figures. It never sets prose, never sets a label, and never sets a control. If it appears,
the thing it sets is one a reader is meant to remember.

**The Tabular Rule.** Any number a reader could compare to another number is
`font-variant-numeric: tabular-nums`. Money, units, counts, percentages, elapsed time.
Non-negotiable: a ledger whose columns do not align is not a ledger.

**The Mono Is For Machines Rule.** Monospace marks a value a human is meant to copy or
verify, not a value a human is meant to understand. Identifiers, digests, hashes. A price
is never mono.

## Layout

A single centred column: `max-width: 1160px` with a `32px` gutter, dropping to `18px` at
≤560px. Page content sits in a vertical stack with a `34px` rhythm between sections, `14px`
inside a group, and `6px` between a label and its value. Multi-column groups use a `22px`
grid gap. The page breathes `34px` above the content and `96px` below it, so the last
section never touches the footer.

Spacing is a hand-tuned continuous scale rather than a strict 4/8 grid, and there is no
spacing token scale in `:root` beyond the gutter and the max width — component padding is
set per component (`9px 15px` on a button, `9px 11px` on an input, `2px 8px` on a chip).
Treat the frontmatter's named steps as the real scale and leave the per-component values
alone unless a component is being rebuilt.

Breakpoints, in the order they fire: **940px** (wide two-column groups collapse), **760px**
(min-width, where a few enhancements switch on), **700px**, **640px**, and **560px** — the
real phone breakpoint, where the gutter narrows, base type settles at 15px, section rhythm
tightens to 26px, and horizontal rails begin to scroll.

**Density target for demo-critical screens.** Cause, current state, and result belong in one
frame. Home's ordinary case fits within roughly one viewport height at 1280×720 and does not
grow when a run completes; primary purpose, state and action stay above the fold. Long proof
destinations — Behind Pool, Showcase — may legitimately scroll, because they exist to be
read rather than acted on.

### Named Rules

**The One Frame Rule.** On a demo-critical screen, the thing that changed and the reason it
changed are visible together without scrolling. A scroll that falls between a number and the
sentence explaining it is a defect.

**The Never Zoom Out Rule.** Density is solved by removing repetition, never by shrinking
type or asking the viewer to zoom. Everything is designed at 100% zoom at 1280×720,
1440×900 and 390×844.

## Elevation & Depth

**Depth is tonal, not cast.** Four paper tones and a 1px rule do nearly all the work: a
panel is `paper-raised` on `paper` with a `rule` border, a well is `paper-sunken`, a meter
track is `paper-deep`. Panels carry only `shadow-sm` at rest — enough to separate a card
from the page at video scale, not enough to float.

Shadow is reserved for two jobs: things that genuinely sit above the page (drawers,
overlays, the primary action) and response to state (`shadow-md` on primary hover). The
dark theme re-tunes every shadow to pure black at higher alpha rather than reusing the warm
ink shadows, because a warm shadow on a near-black paper reads as a smudge.

### Shadow Vocabulary

- **shadow-sm** (`0 1px 2px rgba(23, 21, 15, 0.05)`): a panel at rest. The default, and
  usually the only one on screen.
- **shadow-md** (`0 4px 14px -6px rgba(23, 21, 15, 0.18), 0 1px 3px rgba(23, 21, 15, 0.05)`):
  hover on the primary action, and small floating surfaces.
- **shadow-lg** (`0 18px 46px -22px rgba(23, 21, 15, 0.4), 0 2px 6px rgba(23, 21, 15, 0.06)`):
  drawers and overlays only.

### Named Rules

**The Shadow Earns Its Place Rule.** A shadow means *this is above the page* or *this
responded to you*. It never means *this is important*. Importance is tone, rule and type.

## Shapes

A calm rectilinear language on a small radius scale: `8px` on controls and buttons, `14px`
on panels, `7px` on small controls and nav items, `10px` on large buttons, and `999px` on
chips and meters only. Corners are noticeably tighter than the current app-design default,
which is what keeps the surface reading as a ruled sheet rather than a card deck.

Borders are the signature. Almost every surface is defined by a 1px line — `rule` for
dividers and panels, `rule-strong` for anything that must hold an edge at recording scale.

**Dashed means "not yet, or not this".** A dashed border is load-bearing semantics, not
decoration: in the case-fit diagram a solid box is a whole case Pool actually bought and a
dashed box is the remainder it did not, because a solid box around a partial case would
imply a purchase that never happened.

The three attribution glyphs are the system's geometric signature: **diamond** (agent),
**square** (engine), **circle** (human), at 9–10px, filled with `currentColor`.

### Named Rules

**The Dashed Outline Rule.** Dashed edges mean unbought, unfilled, or still standing. Never
use a dashed border for style.

## Components

### Buttons

- **Shape:** small radius (8px; 7px small, 10px large), 1px `rule-strong` border, 8px gap
  between icon and label, weight 550 at 14px.
- **Default:** `paper-raised` on a 1px strong rule — a quiet, real control.
- **Primary:** ink fill, paper label, `shadow-sm`. Hover deepens the ink within the neutral
  family and lifts to `shadow-md` — no actor hue enters the primary action.
- **Accept:** clay fill with a paper-raised label (5.58:1) — the affirmative control a
  *person* presses, which is why it is clay and not moss. In dark mode the label goes
  near-black against the lighter clay, matching the existing inversion pattern.
- **Ghost:** no border, no fill; for tertiary and destructive-adjacent actions.
- **Hover / Active:** background and border shift over 0.13s; active presses down 1px over
  0.08s.
- **Disabled is a state, not a dimmed copy.** A flat unlit surface with a legible label. A
  45%-opacity ghost of the label failed at both legibility and meaning, worst of all on a
  recorded screen. The primary action keeps its exact shape while running and loses only its
  charge, because that is the button a demo is watching.

### Cards / Containers

- **Corner:** 14px. **Background:** `paper-raised`. **Border:** 1px `rule`.
- **Shadow:** `shadow-sm` at rest, and nothing more (see Elevation).
- `overflow: hidden`, so a full-bleed child clips to the corner instead of squaring it.

### Inputs / Fields

- 1px `rule-strong` on `paper-raised`, 8px radius, `9px 11px` padding, 14px text.
- **`min-height: 38px` is a functional floor, not a taste.** iOS zooms the page when a
  focused control's text is under 16px, which reads as the layout breaking; the height and
  size are tuned together to prevent it.
- **Focus:** 2px ink outline, offset 1px, with the border going ink at the same time.

**The focus ring is ink, everywhere.** Focus is generic interface state, not an attribution,
so it takes no actor hue — the input's treatment above is the system-wide model. Ink gives
16.64:1 against paper, comfortably past AA, and it costs the palette nothing.

### Chips

- Pill (999px), `paper-sunken`, 1px `rule-strong`, 11.5px/600 in `ink-muted`, `2px 8px`.
- A live chip carries a 6px dot pulsing on a 2s ease-in-out cycle — the one continuous
  animation in the system, and it marks a genuinely live connection. It stays **ink**: a
  live runtime is not a person and not a decision, so it gets no actor hue. The pulse and
  the label carry the meaning.

### Navigation

- Text buttons at 13.5px/500 in `ink-muted`, 7px radius, 30px tall, colour and background
  crossfading over 0.13s.
- **Current page is an ink pill with paper text** — a solid mark, not an underline, so it
  survives a scrolling rail. On a phone the nav becomes a horizontally scrolling row with
  the trailing edge faded, the cheapest honest signal that there is more to the right.
- Focus rings inside scrolling rails are drawn *inside* the control (`outline-offset: -2px`)
  because an offset ring gets clipped by the scroll container.

### Tabs

- 13.5px/550, 38px tall, a 2px bottom border that is transparent until selected, pulled down
  1px to sit on the container's rule.
- Roving tabindex: one tab stop for the strip, arrows between tabs, Home/End to the ends, and
  the selected tab scrolls itself into view.

### Attribution Tag (signature)

The system's defining component. A 9px glyph plus an uppercase 11.5px label at 0.04em, in
the actor's hue: **diamond + moss** for "Agent decided", **square + graphite** for
"Computed", **circle + clay** for "Person asked". The legend appears once per surface that
uses the grammar and never twice. This is how the product's entire AI-versus-deterministic
argument is made without prose.

### Case-Fit Diagram (signature)

Whole cases drawn as bordered boxes of 9×15px units on `paper-sunken`; the reader's own units
filled **ink**; other buyers' units in `rule-strong`; still-standing units as dashed outlines;
the remainder in a dashed, transparent box outside the cases. Ownership is emphasis, not
attribution, so it is carried by tone rather than by an actor hue. It replaces three sentences
of case-fitting arithmetic, and it makes the no-speculative-surplus invariant visible at a
glance.

### Meter (signature)

A 6px pill track in `paper-deep` with an **ink** fill (14.02:1), dropping to `ink-muted`
when short of a threshold. A meter reports magnitude, not who acted, so it takes no actor
hue; the figure beside it names the shortfall. **Animated with `transform: scaleX()`, never
width** — a width transition is a layout animation, and these sit inside lists that are
still settling. At 6px tall the end cap's distortion under scaleX is not perceivable. 0.6s
on the expo-out curve.

### Consumer State Chip (signature)

A right-aligned two-line stack: an uppercase 11.5px/0.05em state word over a 12.5px reason in
`ink-muted`. The word is one of exactly five — *needs you, coordinating, ready to collect,
watching, done*.

Only one of the five names an actor. **Needs you** is clay, because a person is the one who
has to act. The other four are neutral — `ink` for the three active states, `ink-faint` for
watching — because "the system is working" is not one party: coordinating spans the agent's
choices, the engine's arithmetic and a host's acceptance, and tinting it moss would claim the
agent did work the engine and a human did. Where a specific state genuinely needs
attribution, put the attribution tag on the row rather than colouring the word.

Below 560px it stops being a column at the end of the row and becomes a line under the name,
because two stacked columns in 300px is neither.

## Do's and Don'ts

### Do:

- **Do** encode attribution with both hue and shape, and let the legend appear once.
- **Do** keep the focus ring ink, and keep generic chrome neutral. An actor hue on a focus
  ring, a banner or a heading attributes an action that nothing performed.
- **Do** reach for ink, ink-muted or a paper tone for success, completion, ownership and
  progress, and add an attribution tag when the actor genuinely matters.
- **Do** set every comparable number in tabular numerals.
- **Do** reach for a paper tone and a 1px rule before reaching for a shadow.
- **Do** keep Instrument Serif for names, headlines and figures only.
- **Do** animate `transform` and `opacity`. The one easing is
  `cubic-bezier(0.16, 1, 0.3, 1)`; state changes are 0.13s, entrances 0.28–0.42s, and the
  meter is 0.6s.
- **Do** let motion report a change that actually happened. On consumer surfaces an element
  may animate only when its own state changed — nothing on first paint, nothing on scroll.
  Showcase is a narrative reader, so sequenced reveal of already-computed facts is legitimate
  there.
- **Do** honour `prefers-reduced-motion`, and make sure the information survives with motion
  off. Motion explains a change; it is never the only thing carrying it.
- **Do** draw the arithmetic when a diagram replaces a paragraph — cases, thresholds,
  distances, recoveries.
- **Do** give a refusal the same typographic dignity as a success.
- **Do** keep contrast at WCAG 2.2 AA, and keep small text at `ink-faint` or darker.

### Don't:

- **Don't** spend moss, graphite or clay on emphasis, hierarchy, mood, success, ownership or
  magnitude, and don't add a fourth accent. Colour is attribution.
- **Don't** use moss as a success or done colour. Moss means the agent decided something; a
  green tick on a step nobody chose is a false claim about who acted.
- **Don't** use graphite for the focus ring or for generic chrome. Generic focus is ink.
- **Don't** use `stop` red for Pool declining to coordinate. That is a correct answer, not an
  error. Stop is for a thing that broke.
- **Don't** animate anything that implies work in progress the system is not doing — no
  fabricated thinking, no fake tool progress, no spinner on a step the browser cannot
  observe. A pulsing dot means a live connection; nothing else may borrow it.
- **Don't** dim a disabled control to a 45% ghost. Flatten it and keep the label legible.
- **Don't** animate `width`, `height`, `top` or `left`.
- **Don't** solve density by shrinking type or expecting a zoom-out.
- **Don't** put a dashed border on anything that is not literally unbought or unfilled.
- **Don't** set a price, a total or a name in monospace. Mono is for identifiers.
- **Don't** let this become an operations console: no dense counter grids, no metric walls,
  no sidebar-and-table chrome, and never the same fact in three sections of one screen.
- **Don't** let this become AI product chrome: no purple-blue gradients, no sparkle or wand
  iconography, no glowing thinking state, no typewriter text.
- **Don't** let this become a consumer savings app: no confetti on a saving, no trophy
  percentage, no cartoon illustration, no mint-and-white rounded card deck.
- **Don't** let this become an enterprise procurement tool: no grey-on-grey field walls, no
  tabbed record view standing in for hierarchy.
- **Don't** use emoji. Icons are one stroke weight on one grid, inline SVG.
