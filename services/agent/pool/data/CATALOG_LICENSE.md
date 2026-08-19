# Licence for the bundled product catalogue

This directory contains **two differently-licensed things**, and the distinction matters.

`catalog.json`, and the product images in `apps/web/src/assets/products/`, are a curated
subset of open community databases. **They are not covered by this repository's MIT
licence.** Everything else in this repository — all of the code, including the script
that produced the subset — is MIT as stated in `/LICENSE`.

## Source

* [Open Food Facts](https://openfoodfacts.org) — food, drink and supplements
* [Open Beauty Facts](https://openbeautyfacts.org) — toiletries
* [Open Products Facts](https://openproductsfacts.org) — other consumer goods

Snapshot date is recorded in the `snapshot` field of `catalog.json`. Regenerate with:

```
services/agent/.venv/bin/python scripts/build_catalog.py --refresh
```

## Licences

| Asset | Licence |
| --- | --- |
| Database as a whole (`catalog.json`) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) |
| Individual contents | [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) |
| Product photographs (`*.jpg`) | [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

**Attribution required.** Credit is rendered in the application in two places: inline
beneath product search results, and durably under *Product data and credits* in the About
view. Both link to openfoodfacts.org, as the terms require.

**Share-alike.** `catalog.json` is a Derivative Database under ODbL §4.4 and is therefore
offered under ODbL, not MIT. It is kept in its own file — rather than merged into Pool's
other data — precisely so that boundary is unambiguous. Displaying this data in the
application is a *Produced Work* under ODbL §4.5, which requires the attribution above but
does not place Pool's own data under ODbL.

## What was deliberately not taken

Package sizes are carried only as the free-text `display_size` field, and nothing parses
or multiplies them. Sampling US protein powders returned `"43.2 oz ("`, `""`,
`"80 x 31g"`, `"I tablesp"` and `"30.5 g"` (a serving, not a package) — seven formats in
eight records. Pool's sealed-unit sizes, case structures and supplier minimums are curated
or operator-verified and never sourced from here.

## Caveat on the photographs

Open Food Facts notes that product images may carry rights beyond the CC-BY-SA grant on
the photograph itself — packaging design copyright and trademark belong to the
manufacturer. Naming a product is protected by nominative fair use; reproducing its
packaging is a separate question. For a labelled, non-commercial demonstration with
attribution the exposure is low, but **this needs a proper answer before any commercial
launch**, and the cheapest one is first-party photography. Recorded here rather than
discovered later.

No manufacturer named in this catalogue has any involvement in, or relationship with,
this project. Every supplier price, case size and minimum in the demo is invented.
