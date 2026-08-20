---
name: Pool
description: A synoptic analysis of latent demand — chart stock, graphite ink, one petrol scale for accumulating demand.
colors:
  stock: "#eaefee"
  stock-raised: "#f4f7f6"
  stock-sunken: "#dde5e3"
  stock-deep: "#cbd6d3"
  ink: "#101a1c"
  ink-muted: "rgba(16, 26, 28, 0.74)"
  ink-faint: "rgba(16, 26, 28, 0.68)"
  rule: "rgba(16, 26, 28, 0.2)"
  rule-strong: "rgba(16, 26, 28, 0.34)"
  field-1: "#c6d6d3"
  field-2: "#6c9e99"
  field-3: "#387b78"
  field-4: "#0e4c50"
  petrol: "#0e4c50"
  petrol-soft: "#cbdad8"
  signal: "#c87a0a"
  signal-deep: "#7a4705"
  signal-soft: "#f0e0c6"
  on-signal: "#101a1c"
typography:
  display:
    fontFamily: "Archivo Variable, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(27px, 3.3vw, 39px)"
    fontWeight: 700
    lineHeight: 1.03
    letterSpacing: "-0.024em"
  headline:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "clamp(26px, 2.7vw, 34px)"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "-0.024em"
  figure:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "clamp(23px, 2.4vw, 31px)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.024em"
  title:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.017em"
  lede:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  body:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
    fontVariant: "tabular-nums"
  small:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.55
  tiny:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "{typography.display.fontFamily}"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.14em"
  notation:
    fontFamily: "ui-monospace, SF Mono, JetBrains Mono, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "0"
rounded:
  none: "0"
spacing:
  hairline: "1px"
  xs: "6px"
  sm: "14px"
  md: "22px"
  lg: "34px"
  gutter: "34px"
  gutter-narrow: "20px"
components:
  button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "10px 17px"
    height: "40px"
  button-hover:
    backgroundColor: "{colors.stock-deep}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.stock}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "10px 17px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.petrol}"
    textColor: "{colors.stock}"
  button-accept:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "10px 17px"
    height: "40px"
  button-accept-hover:
    backgroundColor: "{colors.signal-deep}"
    textColor: "{colors.stock}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "10px 17px"
    height: "40px"
  button-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.ink-faint}"
  button-sm:
    typography: "{typography.label}"
    padding: "6px 11px"
    height: "32px"
  button-lg:
    padding: "14px 22px"
    height: "48px"
  control:
    backgroundColor: "{colors.stock-raised}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "9px 11px"
    height: "38px"
    width: "100%"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "3px 8px"
  chip-ok:
    textColor: "{colors.ink}"
  token:
    backgroundColor: "{colors.stock-sunken}"
    textColor: "{colors.ink}"
    typography: "{typography.notation}"
    rounded: "{rounded.none}"
    padding: "2px 6px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "5px 12px"
    height: "30px"
  nav-item-current:
    textColor: "{colors.ink}"
  panel:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px 0 22px"
  panel-advisory:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px 0 22px"
  banner:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "13px 15px"
  banner-warn:
    backgroundColor: "{colors.signal-soft}"
    textColor: "{colors.ink}"
  banner-stop:
    backgroundColor: "{colors.stock-sunken}"
    textColor: "{colors.ink}"
  status-word-needs-you:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.on-signal}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "3px 9px"
  drawer:
    backgroundColor: "{colors.stock}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px 24px 26px"
    width: "min(420px, 100vw)"
---

# Design System: Pool

## Overview

**Creative North Star: "Synoptic Hour"**

Many people observe independently at the same hour, nobody coordinates them, and the
coherent picture exists only because someone drew an analysis over their separate marks.
That is a synoptic chart, and it is also the product's one sentence: nobody organised the
group, Pool noticed. Every surface is therefore drawn, not decorated — an analysis sheet
with a masthead naming its source and the hour it was drawn, station rows beneath it, and
notation demoted to an enclosure at the foot.

The material is cold chart stock, never warm paper. Ink is graphite, and graphite carries
every analysis line and every refusal, because a refusal here is a result and gets set in
the same voice as a finding. Colour is rationed to two jobs and no others: a five-step
petrol field scale for accumulating demand, and amber as an advisory in effect. There is
no red anywhere on any surface.

The density is high and the dividing is done by rules and rails. No card, no shadow, no
glow, and every corner is square. Quantity is drawn as a **section** —
a fixed unit axis with the supplier's threshold as a tick on it — never as a contour and
never as a progress bar. Contours survive in exactly two places, the mark and the map's
isodistance rings, where the geometry is genuinely geographic. The system explicitly
refuses both the agent-dashboard card grid and its cream-editorial opposite.

**Key Characteristics:**
- Cold chart stock (`#dbe3e1` light / `#0f1719` dark) with graphite ink, both schemes first-class
- Zero radius, zero shadow; hairline and 2px rules divide everything
- One self-hosted variable font (Archivo Variable, weight axis, latin subset, 34.1 kB, SIL OFL)
- Petrol means accumulating demand; amber means an advisory waiting on a person; nothing else is coloured
- Responsibility encoded three times over: rule style, glyph shape, and the word
- Measured 0 contrast failures at 1280×720 and 375×812 in both schemes

## Colors

A cold analytical palette: one cool grey-green stock, one graphite ink, one petrol ramp
for quantity, one amber for advisories.

### Primary
- **Petrol** (`#0e4c50` light / `#9ac7c0` dark): accumulating demand and nothing else. The deep end of the field ramp, the mark's centre, the meteogram trace, the live/environment dots, the closed-case border, the reader's own units inside a purchased case. In dark it inverts to the light end so "more demand" still reads as further along the ramp.
- **The field scale** (`--field-1` … `--field-4`): the four-step ramp a section is drawn in, and every step carries a surface. Step 1 is the unfilled axis ground, step 2 the portion under the threshold, step 4 the portion over it; step 3 fills case-unit cells, the meter track and map pooled markers. A fifth step was declared during the build and consumed by nothing, so it was removed rather than documented — a value used zero times is not a system rule.

### Secondary
- **Signal Amber** (`#c87a0a` light / `#e2a13c` dark): an advisory in effect — something actually waiting on a person. Only ever a **fill**: the advisory panel's left rule and head wash, the `needs-you` status word, the accept control, the human actor's rule. Never amber text on stock.
- **Signal Deep** (`#7a4705` light / `#f0c078` dark): the human actor glyph and form-error text, where amber must sit on stock as ink rather than as a fill.
- **Signal Soft** (`#f0e0c6` light / `#2a2013` dark): the advisory wash behind a head or banner.
- **On-Signal** (`#101a1c`, constant in both schemes): the ink that sits on amber. It does not invert with the scheme, because `--ink` does, and light ink on amber measures about 1.9:1 in the dark counterpart.

### Neutral
- **Chart Stock** (`#dbe3e1` / dark `#0f1719`): the page. Cold and deliberately not paper.
- **Stock Raised** (`#e4eae9` / `#162023`): row hover, input field ground, map ground, active combobox option.
- **Stock Sunken** (`#d0dad8` / `#0a1113`): the muted panel, the stop banner, mono token chips.
- **Stock Deep** (`#c3d0cd` / `#060c0d`): the button hover ground and empty photograph frames.
- **Ink** (`#101a1c` / `#e6eeec`): body text, every analysis line, every refusal, the 2px masthead and footer rules, the focus outline.
- **Ink Muted** (74% ink, both schemes) and **Ink Faint** (68% light / 66% dark): secondary prose and station labels. Both are set above 4.5:1 on stock by measurement, because both are used for small text somewhere.
- **Rule** (20%/22% ink) and **Rule Strong** (34%/36% ink): the hairline between rows and the heavier hairline that opens a region.

### Named Rules
**The One Meaning Rule.** A hue carries exactly one meaning system-wide. Petrol is accumulating demand. Amber is an advisory in effect. A colour never doubles as decoration, category, sentiment, or emphasis.

**The Amber-Is-A-Fill Rule.** Amber is only ever a fill, and what sits on it is always `--on-signal` (measured 5.26:1 light, 7.92:1 dark). Amber as text on stock is prohibited: it does not reach AA at any size worth setting. `--signal-deep` is the only amber permitted as ink.

**The No Red Rule.** There is no red anywhere in this system. A refusal — "there is enough demand and it still would not be cheaper" — is the product's best behaviour, and it is set in ink on stock like every other finding. Refused rows are marked by a rule and the word "refused", never by colour.

**The Inverting-Ramp Rule.** In the dark scheme the field scale inverts so accumulating demand still reads as further along the ramp, and amber brightens so it can keep carrying dark ink. Any new colour must be declared in both `:root` blocks.

## Typography

**Display Font:** Archivo Variable (`--display` aliases `--sans`; falls back to ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif)
**Body Font:** the same family — one face, one weight axis, latin subset, self-hosted from `@fontsource-variable/archivo`
**Label/Mono Font:** system monospace stack (`--mono`: ui-monospace, SF Mono, JetBrains Mono, Menlo, Consolas) for notation, receipts, step indices and paths

The font is the only web font in the project: Archivo Variable, weight axis only, latin
subset, 34.1 kB, self-hosted from `@fontsource-variable/archivo` under SIL OFL 1.1, with
`font-display: swap` and an explicit `unicode-range`. No external font host, no CDN. The
shipped stylesheet is 34.8 kB (7.8 kB gzip).

**Character:** An instrument label, not a display face. The type stays out of the way so the drawing can be the display element; condensation is carried by tracking and weight rather than by a width axis (which exists in this family and costs 54 kB more).

### Hierarchy
- **Display / section titles** (800, `clamp(34px, 4.6vw, 60px)`, 1.0, −0.03em): the primary heading of a surface.
- **Headline** (800, `clamp(28px, 3.6vw, 48px)`, 1.0, balanced): the watched-item name in a station row — the item at display scale, which is the first viewport's anchor.
- **Figure** (900, `clamp(38px, 5vw, 76px)`, 0.98, −0.04em): a single standing quantity set as the figure it is. `.figure-value.sm` steps down to `clamp(24px, 2.4vw, 32px)`; the "yours" value runs to 84px and the bulletin lede to 52px. A hedge rides inside the figure as `.figure-approx` (0.33em, uppercase, superior) so "about" can never detach from the number it qualifies.
- **Title** (700, 17px, 1.12, −0.017em): judge step titles and panel headings; `h1`–`h4` all inherit 700/1.12/−0.017em with balanced wrapping.
- **Lede** (17px, 1.55, ink-muted, max 62ch): the sentence under a masthead.
- **Body** (16px, 1.55, tabular numerals globally): station prose. `.prose` caps at 68ch.
- **Small** (13.5px) / **Tiny** (12px, 1.5): metadata, captions, notes.
- **Stencil label** (700, 11px, 0.13em, uppercase, 1.35): states, attributions, act names and figure labels only. Chart marks sit at 11–12px.
- **Heading label** (700, 13px, no tracking, sentence case): section titles, chips, legends, captions and rail metadata.
- **Notation** (mono, 11–12.5px, no tracking): receipts, hashes, paths, step indices, judge step numbers, meteogram axis marks.

### Named Rules
**The Two-Register Rule.** There are exactly two label registers, and which one applies is decided by what the text does.

*Stencil* — 11px, 700, 0.13em, uppercase — is reserved for what a chart actually stencils onto a drawing: a **state** (`.status-word`), an **attribution** (`.actor`), an **act name** (`.entry-act`), and a **figure's own label** (`.fact-label`, `.prov-label`, `.figure-label`).

*Heading* — 13px, 700, no tracking, sentence case — carries everything that merely *heads* a region: `.section-title`, `.label`, `.chip`, `.outlook-tag`, `.legend-item`, `.arch-tier`, `.hop-name`, `.tl-meta`, `.spine-caption`.

This replaced a single register applied to all of the above, which was the most-used style in the system and made every surface read like an institutional form. Tracked caps everywhere is not a chart; it is paperwork. A third register is the bug this rule exists to refuse.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set on **data, not on prose**: figures, values, tables, ledgers, chart marks, elapsed clocks and mono. Numbers read in columns must not shift. It used to be set on `body`, which meant every sentence rendered in fixed-width digits — "7 people near you buy this" then reads as a meter rather than as a sentence, and that was a large part of what made the interface feel mechanical. Because tabular numerals do not shrink, long values wrap (`overflow-wrap: anywhere`) rather than overflow.

**The Drawing-Is-The-Display-Face Rule.** No decorative type. If a surface needs presence, it gets a section, a meteogram, or the figure register — not a larger, looser typeface.

The corollary, which the first build of this system missed: **if the drawing is the display face, it has to be drawn at display scale.** A 26px section is a hairline pretending to be a chart, and a system whose type is deliberately reticent then has no peak anywhere. `--sect-h` is 68px on a primary row (`--sect-h-sm`, 34px, in compact contexts), and the figure register runs to 76px at weight 900. Reticent type and a large drawing is the intended balance; reticent type and a small drawing is just quiet.

## Layout

A single centred measure: `--max: 1180px` with `--gutter: 34px`, dropping to 20px below
620px. The shell is a column with a sticky masthead, a `flex: 1` main padded `30px 0 72px`,
and a footer opened by a 2px ink rule.

Vertical rhythm runs on a 6 / 14 / 22 / 34px stack (`.stack-xs`, `.stack-sm`, `.grid`,
`.stack`), with `.stack` compressing to 26px below 620px. Grids are explicit and few:
2-up, 3-up, a 1.65fr/1fr side split, and a 0.6fr/1fr lede split. Every multi-column grid
collapses to one column at 1000px; the showcase runsheet's 150px act rail becomes a
horizontally scrolling row at the same breakpoint.

Breakpoints: 1000px (columns collapse, sticky rails unstick) and 620px (gutter narrows,
nav becomes a nowrap scroll strip, small buttons grow to 38px, facts reflow to 104px
minimum tracks). The reference viewports are 1280×720 and 375×812.

**The First-Viewport Rule.** At 1280×720 the masthead (source, analysis time, synthetic status), one full station row (state word, headline, item at display scale, demand sentence, section, reason) and the primary call to action are all above the fold. Nothing decorative may be inserted above the first station row.

**The Rails-Scroll Rule.** Navigation rails scroll rather than wrap: `.nav button`, `.acts a` and `.spine-meta` are `white-space: nowrap` with the scrollbar hidden. A nav item broken across three lines is not a narrower nav, it is a broken one.

## Elevation & Depth

There are no shadows in this system. No card, no shadow, no glow. Depth is entirely
tonal and linear: four stock tones (deep, sunken, base, raised) layer surfaces, and two
rule weights plus two rule strengths do all the dividing. A hairline (`1px var(--rule)`)
separates peers; a heavier hairline (`1px var(--rule-strong)`) opens a region; a `2px
solid var(--ink)` rule marks a boundary that matters — the masthead, the footer, the
lead panel, the first watch row, the drawer edge, the enclosure.

The only `box-shadow` declarations in the entire stylesheet are non-decorative: an inset
1px ring that thickens a focused input's border, an inset 3px left bar on the keyboard-
active combobox option, an inset 1px hairline separating the reader's own units inside a
case, and the inset rule that animates once when a state changes. None of them read as
elevation. The drawer's scrim (`rgba(16,26,28,0.42)`) is the one true overlay.

**The Flat-Sheet Rule.** Nothing floats. If a surface needs to read as separate, change its stock tone or rule it — never lift it.

## Shapes

**The Touch-Or-Drawn Rule.** Radius is decided by what kind of object something is.

*Things you can touch* take a radius: `--r-control` (7px) on buttons, inputs, chips,
thumbnails, result rows and result cards; `--r-region` (12px) on banners, the inverted
band, the drawer, the map frame and choice rows; a full pill on chips, step dots and
judge numbers.

*Things that are drawn* stay square, at zero: the section bar, its threshold tick, its
end caps and extent line, case cells, track cells, the meteogram and the map's own
geometry. A chart mark with a rounded corner is a lie about what kind of object it is.

This replaced a blanket zero. Ninety-degree corners on every control, plus 2px borders,
read as machined rather than technical — the interface felt like switch plates around the
instrument. Softening the chrome while the instrument stays hard-edged is the whole
distinction the rule exists to hold. The focus ring follows `--r-control`. Form language is orthogonal: rectangles, hairlines, ticks, caps and
brackets — the vocabulary of a drawing instrument.

The exceptions are geometric, not stylistic. Circles appear as the human actor glyph, the
member swatch, the map member dot, and the mark's rings. The mark is a closed contour
around a single centre (three rings above 20px, two below, stroke weight increasing
inward like a contour interval, petrol centre). Rings also appear as the map's isodistance
contours. The actor's engine glyph is a square with a 1.2-unit corner at a 10-unit viewBox
— a drafted glyph, not a rounded surface.

**The Contour Confinement Rule.** Contours are permitted in exactly two places: the mark (an emblem) and the map's isodistance rings (genuinely geographic). Everywhere else, quantity is a section.

## Components

### Buttons
An instrument control: square, ruled, its label set like a switch legend.
- **Shape:** `--r-control` radius, `1px solid` border on a `--stock-raised` surface, 40px minimum height, `10px 18px`
- **Default:** transparent ground, ink border and label; hover fills `--stock-deep`; active nudges down 1px
- **Primary:** ink ground, stock label; hover swaps ground and border to petrol
- **Accept (advisory):** amber ground, ink border, `--on-signal` label; hover deepens to `--signal-deep` with stock label
- **Ghost:** `--rule-strong` border, muted label; hover promotes both to ink
- **Disabled:** fills are cleared back to transparent with a faint label and `--rule-strong` border — faint ink on an ink fill would be dark-on-dark
- **Sizes:** `sm` 32px / 10px label / 1.5px border (grows to 38px below 620px); `lg` 48px / 12px label
- **Focus:** the global `2px solid var(--ink)` outline at 2px offset

### Chips
- **Style:** 11px station label, `3px 8px`, `1px solid var(--rule-strong)`, muted ink, square
- **States:** `ok` promotes border and text to ink; `live` prefixes a 6px petrol square. A mono `token` chip drops the tracking and sits on `--stock-sunken`.

### Panels (there are no cards)
- **Corner Style:** square
- **Background:** transparent by default; `--stock-sunken` for the muted variant (which bleeds to the gutter edge)
- **Border:** a `1px var(--rule-strong)` hairline on top, or `2px solid var(--ink)` for a lead panel
- **Internal Padding:** `20px 0 22px` — vertical only, so content stays on the page measure
- **Shadow Strategy:** none. See Elevation & Depth.

### Inputs / Fields
- **Style:** `--stock-raised` ground, `1.5px solid var(--rule-strong)`, square, 38px minimum, `9px 11px`, tabular numerals
- **Focus:** border goes to ink plus an inset 1px ink ring; the native outline is suppressed because the ring replaces it
- **Error:** `--signal-deep` at 13px/700 — amber as ink, never amber as text on a fill
- **Label:** 11px station label in `--ink-faint`; search controls use 16px to prevent iOS zoom

### Navigation
The masthead is the analysis's masthead: what it is, where it came from, when it was
drawn. Sticky, stock ground, `2px solid var(--ink)` bottom rule, 58px minimum. Items are
11px station labels in muted ink with a transparent 2px bottom border; hover promotes to
ink, and `aria-current="page"` promotes both label and bottom border to ink. Below 620px
the nav drops to its own full-width row and scrolls horizontally without wrapping.

### The Section Strip (signature)
`DemandSection` draws quantity on every non-map surface. This is the system's core
component and its rules are normative.

- **Axis:** a fixed unit axis whose extent is `max(demand, minimum)`. There is never padded headroom.
- **With a threshold:** a 26px stepped measure on `--field-1`; the portion under the minimum in `--field-2`, the portion over it in `--field-4`; the minimum as the one major tick (3px ink, overhanging 6px top and bottom) at its true position; case boundaries as 1.5px stock minor ticks; a bracket under the segment the verdict is about, labelled "N short" or "Cleared by N".
- **Without a threshold:** a dimension line — a 2px ink rule with 3px end caps over a 34%-opacity `--field-3` band, and the label "No supplier minimum on file". **No fill.**
- **Case boundaries:** drawn only when the case size is actually known from the supplier sheet in force. Otherwise omitted.
- **Priors:** each prior analysis is a 12px dashed-outline bar on the same axis, its own dated minimum ticked in ink at 70% opacity, labelled with its date and minimum.
- **Axis labels:** `0` on the left, "N units standing" on the right, 10px station register.
- **Geometry in percentages**, so positions are true at any width and labels stay in the real type system.
- **Accessibility:** the whole strip is `role="img"` with a sentence-form `aria-label` stating the extent, the threshold and its verdict, the case interval, and the presence of priors.

**The Section Rule.** Quantity on any non-map surface is a section: fixed unit axis, extent = max(standing demand, supplier minimum), threshold as a tick on the same axis. Never padded headroom, never a contour, never a progress bar.

**The Dimension-Line Rule.** A section with no threshold is a dimension line with end caps, never a fill. A filled bar with nothing to measure against reads as work completed, and this product does not imply work it did not do.

**The Known-Case Rule.** Case boundaries are drawn only when the case size is known from the supplier sheet in force. A guessed interval is not drawn.

**The Standing-Record Rule.** Prior analyses stay, dated, on the same axis in the dashed register. The present is never rewritten to agree with itself.

### The Meteogram (signature)
One quantity traced through the recorded stages of a run, on the Showcase surface.
- 1000×150 viewBox, `preserveAspectRatio="none"`, stroked with `vectorEffect="non-scaling-stroke"` so weights stay true at any width
- The trace is a 3.4px petrol step path; case boundaries are horizontal ink rules at 45% opacity, so a dip means something because it crosses one
- The shortfall span is a 45°-hatched rect with a 1px ink outline, spanning the stages the quantity sat below a whole case
- A 34px mono gutter carries the axis marks; the lowest mark is bottom-anchored inside its own box so it cannot overhang
- The dip is restated in words below the plot ("N units short of a whole case, for two stages")
- The secondary plot is a labelled expanded scale ("Expanded · target−4 to target units") at 60px, **not** an unlabelled zoom

**The Honest-Scale Rule.** A secondary plot states its own range in the label. Exaggerating a dip by cropping the axis silently is prohibited.

### The Actor Grammar (signature)
Responsibility is encoded three times over, so it survives greyscale, colour blindness
and video re-encoding.

| Actor | Rule style | Glyph | The word |
|---|---|---|---|
| agent | `3px dashed` ink left rule (`.bar-agent`) | hollow diamond | "The agent chose to do this" / "Agent decided" |
| deterministic code | `3px solid` ink left rule (`.bar-engine`) | square | "Deterministic code computed it" / "Computed" |
| human | `3px solid` amber left rule (`.bar-human`) | circle in `--signal-deep` | "A person was asked" / "Person asked" |

The glyph is a 9px SVG at a 10-unit viewBox filled with `currentColor`. The legend
(`ActorKey`) appears once per surface that uses the grammar, never twice.

**The Triple-Encoding Rule.** Never carry responsibility on colour alone. Rule style, glyph shape and the word must all agree, and any one of the three must be sufficient.

**The Reserved-Accent Rule.** The left accent rule is reserved for responsibility and for the advisory. It is deliberately not used for selection, refused rows, or ordinary banners.

**Known deviation, recorded deliberately.** A mechanical detector flags the left accent rule as a "side-tab" pattern in 4 remaining instances (`.bar-agent`, `.bar-engine`, `.bar-human`, `.panel-advisory`). Those 4 are the system, not a defect: the left rule is the visual carrier of responsibility and of the one advisory state, and it is confined to exactly those two jobs. The warning is accepted, not fixed. If the count rises above 4, the new instance is the bug.

### Banners and states
- **Banner (default):** `1.5px solid var(--rule-strong)`, transparent — a plain result
- **Banner stop:** ink border, `--stock-sunken` ground, no colour. A refusal is set like every other finding.
- **Banner warn / advisory panel:** ink border with a `4px solid var(--signal)` left rule and a `--signal-soft` wash. The advisory panel's head carries the wash and bleeds 15px either side.
- **Status word:** 11px station label at 0.16em in ink. The single `needs-you` state — the one thing waiting on a person — gets the amber fill with `--on-signal` at `3px 9px`.
- **Refused trace step:** the summary is promoted from muted to full ink. The word "refused" already sits in the summary; no colour is added.

### The Bulletin and Enclosure (judge surfaces)
Judge-facing surfaces open the way a forecast office opens a written analysis: an issuing
line in the station register, one sentence of what is claimed set at
`clamp(21px, 2.3vw, 28px)`, then numbered sections (`§1`…`§8`) with mono section numbers.
The chart is an **enclosure** at the foot, opened by a `2px solid var(--ink)` rule and
labelled "Enclosure A" — a judge needs the hierarchy of the proof before the notation.
Collapsible record sections are 44px-minimum summaries with a rotating caret at a fixed
left inset.

### Motion
The whole budget, in three items: one 0.9s beat under a status word when the state
actually changes (`.status-chip.just-changed`, an inset petrol rule fading out), the
drawer's 0.16s slide-in, and a 0.9s spinner during a real wait. All three are cancelled
under `prefers-reduced-motion: reduce`, which also disables smooth scrolling and freezes
the spinner to a static ring.

**The No-Implied-Progress Rule.** Nothing animates to suggest work in flight. The meter never animates and never fills to imply completion; the wait screen shows real elapsed time in mono, because the clock is the only thing that is true.

## Do's and Don'ts

### Do:
- **Do** draw any non-map quantity as a section: fixed unit axis, extent `max(demand, minimum)`, threshold as a tick on the same axis.
- **Do** draw a threshold-less section as a dimension line with 3px end caps and no fill.
- **Do** keep prior analyses on the same axis, dated, in the dashed register.
- **Do** declare every new colour in both `:root` and the `prefers-color-scheme: dark` block, and keep the field ramp inverting so more demand reads as further along it.
- **Do** put `--on-signal` on every amber fill — it is a constant in both schemes for a measured reason (5.26:1 light, 7.92:1 dark).
- **Do** encode responsibility three times: rule style, glyph shape, and the word.
- **Do** divide with rules and stock tones: `1px var(--rule)` between peers, `1px var(--rule-strong)` to open a region, `2px solid var(--ink)` for a boundary that matters.
- **Do** set anything that names rather than states in the station-label register (11px / 700 / 0.14em / uppercase).
- **Do** keep tabular numerals on every value and let long values wrap rather than overflow.
- **Do** hold the floor: 0 contrast failures at 1280×720 and 375×812 in both schemes, no touch target under 24px, no horizontal overflow at 375 or 1280.
- **Do** state a secondary plot's range in its label.
- **Do** open judge surfaces as a bulletin — written record and numbered sections first, notation as an enclosure at the foot.
- **Do** keep the font self-hosted: one family, weight axis only, latin subset, no external host and no CDN.

### Don't:
- **Don't** use red. A refusal is set in ink on stock, with a rule and the word, because it is the product's best behaviour.
- **Don't** set amber as text on stock. Amber is a fill; `--signal-deep` is the only amber permitted as ink.
- **Don't** spend petrol on anything except accumulating demand — not on progress, success, links, or emphasis.
- **Don't** add a card, a shadow, a glow, or a corner radius. There is no radius token to reach for, and reintroducing one is the change this line exists to refuse.
- **Don't** pad a section's axis for headroom, or draw case boundaries the supplier sheet in force does not establish.
- **Don't** rewrite a prior analysis to agree with the present.
- **Don't** use the left accent rule for selection, refused rows, or ordinary banners — it is reserved for responsibility and advisory.
- **Don't** draw a contour anywhere except the mark and the map's isodistance rings.
- **Don't** animate anything that implies work in flight, and don't ship motion that has no `prefers-reduced-motion` escape.
- **Don't** let a nav or act rail wrap; rails scroll.
- **Don't** add a second label register, a decorative typeface, or a second font request.
- **Don't** crop a chart's axis to make a movement look larger than it is.

### The inverted band

One region per screen may invert, and only when it is genuinely the news: an order that
actually formed. `.panel-inverted` swaps the ink/stock/rule/field tokens locally, so every
child keeps its meaning without knowing where it sits — a section drawn inside it is still
"demand in petrol against the ground", it is just that the ground is now ink and petrol is
the light end of the ramp.

- Ground `#0d1517`, type `#eaefee`, field ramp inverted so more demand still reads deeper.
- Inset within the measure, **not** full-bleed. It carried a negative margin briefly; the
  gutter container is not its parent, so the band escaped the measure and made the
  document wider than the viewport at 375px.
- Depth is contrast. There is still no shadow anywhere in this system.
- Measured: 0 contrast failures inside the band at either reference viewport.

**The One-Inversion Rule.** A second inverted region on the same screen makes both of them
ordinary. If something else needs emphasis, it gets scale or the figure register.

### Motion

Two durations and one easing: `--dur-fast` 120ms, `--dur` 180ms, `--ease`
`cubic-bezier(0.2, 0, 0, 1)`.

**The Feedback-Not-Progress Rule.** Motion in this system answers *the reader's own
input* and never narrates Pool's work. Controls, rows, result cards, inputs and nav items
transition their colour and border on hover, focus and press. Values do **not** tween: a
quantity moving from 24 to 22 snaps, because a recomputation is not a journey and an
eased number implies elapsed effort that did not happen.

The one authored moment is `.status-chip.just-changed`, a single 0.9s beat under a state
word that has actually changed. Plus the drawer slide and a spinner during a genuinely
real wait.

Before this, nothing in the interface transitioned at all — every interaction was an
instant hard swap, which is correct for data and wrong for a control, and was a large
part of why the surface read as robotic rather than precise.

Under `prefers-reduced-motion: reduce` every duration collapses to 0.01ms, so state still
changes but nothing travels.
