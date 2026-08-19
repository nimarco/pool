"""Build Pool's bundled consumer product catalogue from Open Food Facts.

Run occasionally, by hand, on a laptop. **Never at request time and never in a test.**
The whole point of this script is that its *output* is committed, so the running system
— and the demo a judge watches — makes no third-party call at all.

That is not a stylistic preference. Open Food Facts documents 10 search requests per
minute per IP and explicitly warns against using search for autocomplete; in practice
this script sees HTTP 503 from it at well under that rate, which is exactly the kind of
dependency a live demo must not have (docs/CATALOG_RESEARCH.md §5.1).

What is imported, and what is deliberately not
----------------------------------------------
Imported: consumer **identity** — name, brand, GTIN, category, front image. A member
recognises these, so an error is visible to the person best placed to catch it.

Not imported: anything Pool computes with. Package size is the sharp example. Sampling
US protein powders returns ``"43.2 oz ("``, ``""``, ``"80 x 31g"``, ``"I tablesp"`` and
``"30.5 g"`` (a serving, not a package) — seven formats in eight records. So ``quantity``
becomes ``display_size``, a string shown on a card, and nothing multiplies it. The sealed
unit, case structure, and MOQ stay curated or operator-verified (AGENTS.md §8, §48).

``substitute_group`` is assigned here, from the curated table below, and only from it.
A product whose category is not in the table gets **no** group, which
``domain.substitution`` treats as "matches nothing but itself" — the safe direction. An
unreviewed category must never quietly make two people's purchases interchangeable.

Usage
-----
    services/agent/.venv/bin/python scripts/build_catalog.py [--refresh]

Raw API responses are cached under ``.catalog-cache/`` so re-runs are free and the
output is reproducible without hammering a volunteer-run service. ``--refresh`` ignores
the cache.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE = os.path.join(ROOT, ".catalog-cache")
CATALOG_OUT = os.path.join(ROOT, "services/agent/pool/data/catalog.json")
IMAGE_OUT = os.path.join(ROOT, "apps/web/src/assets/products")

#: Identifies this project to a volunteer-run service, as their terms ask.
UA = "PoolCatalogBuild/1.0 (+https://github.com/nimarco/pool)"

#: Stamped into every record so a stale catalogue is visible rather than assumed fresh.
SNAPSHOT = "2026-08-19"


# --------------------------------------------------------------------------- categories


@dataclass(frozen=True)
class CategorySpec:
    """One slice of the catalogue.

    ``group`` is the Pool substitute group. Two products may only ever be combined into
    one purchase if they share it, so it is set here by a human and never inferred.
    ``unit`` is the sealed consumer unit an offer would be priced against.
    """

    host: str
    tag: str
    category: str          # Pool's coarse category
    group: str             # Pool substitute_group — curated, load-bearing
    unit: str
    cap: int = 22
    synonyms: tuple[str, ...] = ()


FOOD = "world.openfoodfacts.org"
BEAUTY = "world.openbeautyfacts.org"
PRODUCTS = "world.openproductsfacts.org"

CATEGORIES: list[CategorySpec] = [
    CategorySpec(FOOD, "en:protein-powders", "nutrition", "whey_protein", "tub", 28,
                 ("protein", "whey", "protein powder", "shake")),
    CategorySpec(FOOD, "en:protein-bars", "nutrition", "protein_bar", "box", 16,
                 ("protein bar", "bar")),
    CategorySpec(FOOD, "en:energy-drinks", "beverage", "energy_drink", "pack", 24,
                 ("energy drink", "energy")),
    CategorySpec(FOOD, "en:coffees", "beverage", "coffee", "bag", 26,
                 ("coffee", "beans", "ground coffee")),
    CategorySpec(FOOD, "en:teas", "beverage", "tea", "box", 14, ("tea", "teabags")),
    CategorySpec(FOOD, "en:sparkling-waters", "beverage", "sparkling_water", "pack", 16,
                 ("sparkling water", "seltzer", "soda water")),
    CategorySpec(FOOD, "en:sodas", "beverage", "soda", "pack", 16, ("soda", "pop", "cola")),
    CategorySpec(FOOD, "en:breakfast-cereals", "pantry", "cereal", "box", 18,
                 ("cereal", "breakfast")),
    CategorySpec(FOOD, "en:granola-bars", "pantry", "granola_bar", "box", 16,
                 ("granola bar", "snack bar")),
    CategorySpec(FOOD, "en:peanut-butters", "pantry", "nut_butter", "jar", 16,
                 ("peanut butter", "nut butter")),
    CategorySpec(FOOD, "en:chips", "pantry", "chips", "bag", 16, ("chips", "crisps")),
    CategorySpec(FOOD, "en:pastas", "pantry", "pasta", "box", 14, ("pasta", "noodles")),
    CategorySpec(FOOD, "en:rices", "pantry", "rice", "bag", 12, ("rice",)),
    CategorySpec(BEAUTY, "en:shampoos", "toiletries", "shampoo", "bottle", 16,
                 ("shampoo", "hair")),
    CategorySpec(BEAUTY, "en:toothpastes", "toiletries", "toothpaste", "tube", 14,
                 ("toothpaste", "tooth paste")),
    CategorySpec(BEAUTY, "en:deodorants", "toiletries", "deodorant", "stick", 14,
                 ("deodorant", "antiperspirant")),
    CategorySpec(BEAUTY, "en:soaps", "toiletries", "soap", "bar", 12,
                 ("soap", "body wash", "hand soap")),
    CategorySpec(PRODUCTS, "en:laundry-detergents", "household", "detergent", "tub", 14,
                 ("detergent", "laundry", "washing")),
    CategorySpec(PRODUCTS, "en:toilet-papers", "household", "toilet_paper", "pack", 10,
                 ("toilet paper", "loo roll", "tp", "bathroom tissue")),
    CategorySpec(PRODUCTS, "en:paper-towels", "household", "paper_towels", "pack", 10,
                 ("paper towel", "kitchen roll", "kitchen towel")),
]


# --------------------------------------------------------------------------- canonical pins
#
# The demo scenario's economics are keyed on these product ids — the offers, MOQ, case
# sizes and every asserted figure hang off them. So the ids are *pinned*: the catalogue
# supplies a recognisable identity for a row that already exists rather than adding a new
# one. That is what lets an invented "Northfield vanilla whey" become something a person
# actually recognises without touching a number in the scenario.
#
# These entries deliberately carry **no GTIN and no package size**, and that is the most
# important decision in this file.
#
# Pool holds a synthetic supplier offer for each of them: a 5 lb tub, twelve to a case,
# minimum twenty-four. Those terms were invented for the scenario. The Open Food Facts
# record whose photograph makes the product recognisable is a *specific retail SKU* — the
# vanilla one is a 24.05 oz tub — and its barcode identifies that SKU exactly. Printing
# that barcode beside a case structure invented for a different package would assert a
# correspondence that does not exist, and a barcode is precisely the field a careful
# judge would check.
#
# So the rule is: a product Pool quotes a synthetic price for is identified at the level
# that is true — brand, product line, flavour, photograph — and claims no SKU. Catalogue
# products Pool has *no* offer for carry their full identity, barcode included, because
# nothing there can contradict them.
#
#   pool product_id -> (GTIN to adopt the identity/image of, name, variant, extra synonyms)

CANONICAL_PINS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "prod_whey_vanilla": (
        "0748927069525", "100% Whey Protein", "Vanilla Ice Cream",
        ("whey", "vanilla whey", "vanilla protein", "on whey", "protein powder"),
    ),
    "prod_whey_chocolate": (
        "0748927059113", "Gold Standard 100% Whey", "Extreme Milk Chocolate",
        ("whey", "chocolate whey", "chocolate protein", "on whey", "protein powder"),
    ),
    "prod_energy_drink": (
        "0611269991000", "Energy Drink", "",
        ("energy drink", "energy", "red bull", "redbull"),
    ),
    "prod_coffee_beans": (
        "0762111184016", "Pike Place Medium Roast", "",
        ("coffee", "ground coffee", "beans", "medium roast"),
    ),
}

#: Categories the open catalogues simply do not cover. Probing Open Products Facts for US
#: rows returned 0 laundry detergents, 0 toilet papers and 1 paper towel, so household
#: consumables cannot come from there. They are curated instead, and deliberately carry
#: no brand: inventing one would put a fictional brand beside two hundred real ones, and
#: Pool genuinely does not know a brand here. They render with the category fallback tile,
#: which is also how that path gets exercised for real.
CURATED: list[dict] = [
    # Rice is the one entry here the open catalogues *do* cover — twelve US records, and
    # every one of them a specific retail SKU with its own barcode: 250 g microwave
    # pouches, 8 oz boxes, a 16 oz bag of wild rice. Pool's scenario product is a 5 lb
    # sack that a supplier later quotes by the case, and pinning a real barcode to it
    # would assert a correspondence between an invented case structure and a specific
    # package that does not exist — the same reason the canonical pins above emit no
    # GTIN, applied to a product whose sizes disagree even more sharply.
    #
    # So it is curated and brandless, like the household rows: Pool genuinely does not
    # know a brand here, and inventing one would put a fictional brand beside two
    # hundred real ones. It renders with the category tile.
    {
        "product_id": "prod_rice_jasmine", "name": "Jasmine rice, 5 lb",
        "brand": "", "variant": "", "category": "pantry",
        "substitute_group": "rice", "unit": "bag",
        "synonyms": ["rice", "jasmine rice", "white rice", "long grain rice"],
    },
    {
        "product_id": "prod_detergent_pods", "name": "Laundry detergent pods, 96 count",
        "brand": "", "variant": "", "category": "household",
        "substitute_group": "detergent", "unit": "tub",
        "synonyms": ["detergent", "laundry", "pods", "washing", "laundry detergent"],
    },
    {
        "product_id": "prod_paper_towels", "name": "Paper towels, 6 rolls",
        "brand": "", "variant": "", "category": "household",
        "substitute_group": "paper_towels", "unit": "pack",
        "synonyms": ["paper towels", "kitchen roll", "kitchen towel", "towels"],
    },
    {
        "product_id": "prod_toilet_paper", "name": "Toilet paper, 12 rolls",
        "brand": "", "variant": "", "category": "household",
        "substitute_group": "toilet_paper", "unit": "pack",
        "synonyms": ["toilet paper", "tp", "loo roll", "bathroom tissue"],
    },
    {
        "product_id": "prod_dish_soap", "name": "Dish soap, 30 fl oz",
        "brand": "", "variant": "", "category": "household",
        "substitute_group": "dish_soap", "unit": "bottle",
        "synonyms": ["dish soap", "washing up liquid", "dishwashing"],
    },
    {
        "product_id": "prod_trash_bags", "name": "Kitchen trash bags, 80 count",
        "brand": "", "variant": "", "category": "household",
        "substitute_group": "trash_bags", "unit": "box",
        "synonyms": ["trash bags", "bin bags", "garbage bags", "bin liners"],
    },
]


# --------------------------------------------------------------------------- fetching


class FetchError(RuntimeError):
    pass


def _get(url: str, *, attempts: int = 6, timeout: int = 45) -> bytes:
    """GET with exponential backoff.

    Open Food Facts is a volunteer-run service that returns 503 under load. Backing off
    politely is both the neighbourly thing to do and the only way this script finishes.
    """
    delay = 8.0
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                raise FetchError(f"{last} for {url}") from exc
        except Exception as exc:  # noqa: BLE001 - network is allowed to fail here
            last = str(exc)
        if attempt < attempts:
            print(f"    retry {attempt}/{attempts - 1} in {delay:.0f}s ({last})", flush=True)
            time.sleep(delay)
            delay = min(delay * 1.7, 90.0)
    raise FetchError(f"gave up after {attempts} attempts: {last}")


def fetch_category(spec: CategorySpec, *, refresh: bool) -> list[dict]:
    os.makedirs(CACHE, exist_ok=True)
    key = f"{spec.host.split('.')[1]}_{spec.tag.replace(':', '_')}.json"
    path = os.path.join(CACHE, key)
    if os.path.isfile(path) and not refresh:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("products", [])

    url = (
        f"https://{spec.host}/api/v2/search?categories_tags={spec.tag}"
        "&countries_tags=en:united-states"
        "&fields=code,product_name,product_name_en,brands,quantity,image_front_url,categories_tags"
        "&page_size=100&sort_by=popularity_key"
    )
    print(f"  fetching {spec.tag} from {spec.host}", flush=True)
    payload = json.loads(_get(url))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    time.sleep(9)  # documented: 10 search req/min/IP
    return payload.get("products", [])


# --------------------------------------------------------------------------- cleaning

#: Brands whose casing is a deliberate style rather than shouting.
BRAND_STYLE = {
    "gt's": "GT's", "bodyarmor": "BODYARMOR", "rxbar": "RXBAR", "kind": "KIND",
    "on": "Optimum Nutrition", "pop-tarts": "Pop-Tarts", "m&m's": "M&M's",
}

_WS = re.compile(r"\s+")
_JUNK = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value: str) -> str:
    return _WS.sub(" ", _JUNK.sub(" ", value or "")).strip(" ,;-–—·|")


def normalize_brand(raw: str) -> str:
    """First brand only, cased like a brand rather than like a database field.

    Open Food Facts returns "Optimum nutrition", "Optimum Nutrition" and
    "OPTIMUM NUTRITION" for one company, sometimes within a single response. Matching on
    brand is a deterministic rule downstream, so the variants have to collapse here.
    """
    first = clean_text((raw or "").split(",")[0])
    if not first:
        return ""
    styled = BRAND_STYLE.get(first.casefold())
    if styled:
        return styled
    if first.isupper() or first.islower():
        return " ".join(w[:1].upper() + w[1:] for w in first.split())
    return first


def clean_name(raw: str, brand: str) -> str:
    name = clean_text(raw)
    if not name:
        return ""
    if name.isupper() and len(name) > 4:
        name = " ".join(w[:1] + w[1:].lower() for w in name.split())
    # "Optimum Nutrition Gold Standard" -> "Gold Standard": the card prints the brand
    # separately, and repeating it costs the line's whole width.
    if brand and name.casefold().startswith(brand.casefold() + " "):
        name = name[len(brand) + 1 :].strip()
    return clean_text(name)


#: A package size is only shown when it looks like one. Everything else becomes "",
#: because a wrong size on a card is worse than no size — and it is *never* arithmetic.
_SIZE_OK = re.compile(
    r"^\d{1,4}(?:[.,]\d{1,2})?\s*(?:g|kg|mg|ml|l|oz|fl\.?\s?oz|lb|lbs|ct|count|pack|x\s*\d+\s*\w+)\b",
    re.IGNORECASE,
)


def clean_size(raw: str) -> str:
    text = clean_text(raw)
    if not text or len(text) > 24 or not _SIZE_OK.match(text):
        return ""
    return text


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


# --------------------------------------------------------------------------- build


@dataclass
class Entry:
    product_id: str
    name: str
    brand: str
    variant: str
    category: str
    substitute_group: str
    unit: str
    gtin: str
    display_size: str
    image_ref: str
    synonyms: list[str] = field(default_factory=list)
    source: str = "open_food_facts"
    source_ref: str = ""
    image_url: str = ""     # build-time only; stripped before writing


def build_entries(refresh: bool) -> list[Entry]:
    pinned_by_gtin = {gtin: pid for pid, (gtin, *_) in CANONICAL_PINS.items()}
    seen_gtin: set[str] = set()
    seen_key: set[str] = set()
    out: list[Entry] = []

    for spec in CATEGORIES:
        try:
            raw = fetch_category(spec, refresh=refresh)
        except FetchError as exc:
            print(f"  !! {spec.tag}: {exc}", file=sys.stderr, flush=True)
            continue

        kept = 0
        for row in raw:
            if kept >= spec.cap:
                break
            # The barcode the snapshot came from. Used for de-duplication and to look up
            # a pin, and separate from the barcode that gets *published*, which a pinned
            # product deliberately does not have.
            source_gtin = clean_text(str(row.get("code") or ""))
            brand = normalize_brand(row.get("brands", ""))
            name = clean_name(row.get("product_name_en") or row.get("product_name", ""), brand)
            image = row.get("image_front_url") or ""
            if not (source_gtin and brand and name and image):
                continue
            if len(name) < 3 or len(name) > 54 or source_gtin in seen_gtin:
                continue

            pid = pinned_by_gtin.get(source_gtin) or f"prod_{source_gtin}"
            gtin = source_gtin
            variant = ""
            size = clean_size(row.get("quantity", ""))
            extra: tuple[str, ...] = ()
            if pid in CANONICAL_PINS:
                # Curated identity wins, and the SKU-level fields are dropped on
                # purpose — see the note above CANONICAL_PINS.
                _, name, variant, extra = CANONICAL_PINS[pid]
                gtin, size = "", ""

            key = (slug(brand), slug(name), slug(variant))
            if key in seen_key:
                continue

            seen_gtin.add(source_gtin)
            seen_key.add(key)
            kept += 1
            out.append(
                Entry(
                    product_id=pid,
                    name=name,
                    brand=brand,
                    variant=variant,
                    category=spec.category,
                    substitute_group=spec.group,
                    unit=spec.unit,
                    gtin=gtin,
                    display_size=size,
                    image_ref=pid,
                    synonyms=sorted({*spec.synonyms, *extra}),
                    source_ref=f"openfoodfacts:{SNAPSHOT}",
                    image_url=image,
                )
            )
        print(f"  {spec.tag:<28} kept {kept}", flush=True)

    # Household consumables, which no open catalogue covers (see CURATED).
    for row in CURATED:
        out.append(
            Entry(
                product_id=row["product_id"],
                name=row["name"],
                brand=row["brand"],
                variant=row["variant"],
                category=row["category"],
                substitute_group=row["substitute_group"],
                unit=row["unit"],
                gtin="",
                display_size="",
                image_ref="",          # no photograph; the card falls back to a tile
                synonyms=sorted(set(row["synonyms"])),
                source="curated",
                source_ref="pool:curated",
                image_url="",
            )
        )
    print(f"  {'curated household':<28} kept {len(CURATED)}", flush=True)

    missing = set(CANONICAL_PINS) - {e.product_id for e in out}
    if missing:
        print(f"\n!! canonical pins not found in the fetched data: {sorted(missing)}",
              file=sys.stderr)
        print("   the scenario depends on these; fix the pin or the category before "
              "committing.", file=sys.stderr)
    return out


def download_images(entries: list[Entry]) -> int:
    """Fetch the 200px render of each front image and commit it as a local asset.

    200px is Open Food Facts' own pre-rendered size — about 6 KB — so nothing needs
    resizing and the whole catalogue costs roughly a megabyte. Local because the demo may
    not depend on an image host, and because the CSP is ``img-src 'self'``.
    """
    os.makedirs(IMAGE_OUT, exist_ok=True)
    ok = 0
    for i, e in enumerate(entries, 1):
        if not e.image_url:
            continue          # curated entries have no photograph by design
        dest = os.path.join(IMAGE_OUT, f"{e.product_id}.jpg")
        if os.path.isfile(dest) and os.path.getsize(dest) > 512:
            ok += 1
            continue
        # `.../front_en.51.400.jpg` -> `.../front_en.51.200.jpg`
        url = re.sub(r"\.(\d+)\.jpg$", r".200.jpg", e.image_url)
        try:
            data = _get(url, attempts=3, timeout=30)
        except FetchError as exc:
            print(f"    image missing for {e.product_id}: {exc}", file=sys.stderr)
            continue
        if len(data) < 512:
            continue
        with open(dest, "wb") as handle:
            handle.write(data)
        ok += 1
        if i % 25 == 0:
            print(f"    images {i}/{len(entries)}", flush=True)
        time.sleep(0.2)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore the local cache")
    ap.add_argument("--skip-images", action="store_true")
    args = ap.parse_args()

    print("→ Fetching categories")
    entries = build_entries(args.refresh)
    if not entries:
        print("no entries built", file=sys.stderr)
        return 1

    if not args.skip_images:
        print("\n→ Downloading images")
        got = download_images(entries)
        print(f"  {got}/{len(entries)} images on disk")
        # An entry that *expected* a photograph and did not get one would render a hole,
        # so it is dropped. Entries that never claimed one (the curated household rows)
        # are kept and fall back to a category tile.
        entries = [
            e for e in entries
            if not e.image_ref
            or os.path.isfile(os.path.join(IMAGE_OUT, f"{e.product_id}.jpg"))
        ]

    entries.sort(key=lambda e: (e.category, e.substitute_group, e.brand, e.name))
    payload = {
        "snapshot": SNAPSHOT,
        "source": "Open Food Facts, Open Beauty Facts, Open Products Facts",
        "source_url": "https://openfoodfacts.org",
        "data_license": "ODbL-1.0",
        "image_license": "CC-BY-SA-4.0",
        "attribution": "Product names, brands, barcodes and images from Open Food Facts "
                       "contributors, used under ODbL (data) and CC-BY-SA (images).",
        "note": "Consumer identity only. Package sizes are display text and are never "
                "used in Pool's economics; supplier offers, cases and MOQ are separate "
                "and are not sourced from here.",
        "products": [
            {k: v for k, v in vars(e).items() if k != "image_url"} for e in entries
        ],
    }
    os.makedirs(os.path.dirname(CATALOG_OUT), exist_ok=True)
    with open(CATALOG_OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    groups = len({e.substitute_group for e in entries})
    print(f"\n✓ {len(entries)} products across {groups} substitute groups")
    print(f"  catalogue: {os.path.relpath(CATALOG_OUT, ROOT)}")
    print(f"  images:    {os.path.relpath(IMAGE_OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
