"""The consumer product catalogue, and the search that turns typing into a product id.

This is the layer that was missing. Everything downstream of a ``product_id`` — matching,
substitution, timing, case fitting, economics — was already deterministic and tested; what
did not exist was any way for a person to *arrive* at a ``product_id`` except by picking
from a six-row dropdown of invented brands.

Three properties are non-negotiable here, and they are why this is a bundled file rather
than an API client:

**No network, ever.** The catalogue is a JSON snapshot committed to the repository and the
images are committed assets. Open Food Facts documents ten search requests per minute and
warns against using search for autocomplete; while building this, its search endpoint
returned 503 at well under that rate. A demo whose first interaction depends on that is a
demo that breaks in front of judges (AGENTS.md §8, docs/CATALOG_RESEARCH.md §5.1).

**Deterministic.** Same query, same ranking, every run — so a test can pin what
``"vanilla whey"`` resolves to, and so the demo behaves the same on the tenth rehearsal as
on the first. Ranking is a pure function of the query and the snapshot. No model is
called, here or anywhere on this path.

**Identity only.** A catalogue entry describes what a person is buying. It carries no
price, no case size, no MOQ and no supplier, and its ``display_size`` is a string for
humans that nothing multiplies. Supplier economics live in ``Offer`` and are curated or
operator-verified. Keeping those apart is what stops a real brand name from lending
credibility to an invented quote (§41, §48).
"""

from __future__ import annotations

import functools
import json
import os
import re
from dataclasses import dataclass

from ..domain.models import Product, ProductSource

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.json")

#: Deliberately small. These are recognition aids on a card, not a browse experience —
#: a member is confirming the thing they already buy, and a list they have to read is a
#: list that has stopped helping.
DEFAULT_LIMIT = 6
MAX_LIMIT = 12
#: Below this, a query is still being typed rather than asked.
MIN_QUERY_CHARS = 2

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").casefold())


@dataclass(frozen=True)
class CatalogEntry:
    """One consumer product identity, exactly as the snapshot recorded it."""

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
    synonyms: tuple[str, ...]
    source: str
    source_ref: str

    @property
    def label(self) -> str:
        return " ".join(p for p in (self.brand, self.name, self.variant) if p)

    def to_product(self) -> Product:
        """Materialise this identity as a Pool product.

        ``substitute_group`` is carried across as the snapshot recorded it — which the
        build script sets from a curated category table and from nothing else. An entry
        whose category was never reviewed arrives with an empty group, and
        ``domain.substitution`` then treats it as compatible with nothing but itself.
        Failing closed is the whole point: an unreviewed category must not be able to
        quietly make two people's purchases interchangeable.
        """
        return Product(
            id=self.product_id,
            name=self.name,
            category=self.category,
            unit=self.unit,
            substitute_group=self.substitute_group,
            brand=self.brand,
            variant=self.variant,
            # Not sourced from the snapshot. Host capacity is computed from it, and
            # public package weights are not reliable enough to carry that (§48). A
            # curated product supplies its own; a catalogue product declares none.
            unit_weight_grams=0,
            gtin=self.gtin,
            image_ref=self.image_ref,
            image_attribution=attribution().image_credit,
            display_size=self.display_size,
            synonyms=list(self.synonyms),
            source=ProductSource(self.source),
            source_ref=self.source_ref,
        )

    def view(self) -> dict:
        """The shape the client renders a product card from.

        ``product_id`` is present because the client has to send it back, and is never
        displayed — a member should not learn that Pool has internal identifiers.
        """
        return {
            "product_id": self.product_id,
            "name": self.name,
            "brand": self.brand,
            "variant": self.variant,
            "display_size": self.display_size,
            "unit": self.unit,
            "category": self.category,
            "image_ref": self.image_ref,
        }


@dataclass(frozen=True)
class Attribution:
    """Licence obligations that travel with the snapshot, so the UI can honour them."""

    source: str
    source_url: str
    data_license: str
    image_license: str
    credit: str
    snapshot: str

    @property
    def image_credit(self) -> str:
        return f"{self.source} ({self.image_license})"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "data_license": self.data_license,
            "image_license": self.image_license,
            "credit": self.credit,
            "snapshot": self.snapshot,
        }


# --------------------------------------------------------------------------- loading


@functools.lru_cache(maxsize=1)
def _payload() -> dict:
    if not os.path.isfile(CATALOG_PATH):
        # A missing snapshot must not take the API down: the seeded products still work
        # and search simply finds nothing. Silence would be worse than an empty result,
        # so the shape stays valid and the emptiness is visible.
        return {"products": [], "snapshot": "", "attribution": ""}
    with open(CATALOG_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@functools.lru_cache(maxsize=1)
def entries() -> tuple[CatalogEntry, ...]:
    """Every catalogue entry, in a stable order. Parsed once per process."""
    out: list[CatalogEntry] = []
    for row in _payload().get("products", []):
        try:
            out.append(
                CatalogEntry(
                    product_id=row["product_id"],
                    name=row["name"],
                    brand=row.get("brand", ""),
                    variant=row.get("variant", ""),
                    category=row.get("category", ""),
                    substitute_group=row.get("substitute_group", ""),
                    unit=row.get("unit", "unit"),
                    gtin=row.get("gtin", ""),
                    display_size=row.get("display_size", ""),
                    image_ref=row.get("image_ref", ""),
                    synonyms=tuple(row.get("synonyms", ())),
                    source=row.get("source", "curated"),
                    source_ref=row.get("source_ref", ""),
                )
            )
        except KeyError:
            # One malformed row should cost one row, not the catalogue.
            continue
    return tuple(sorted(out, key=lambda e: e.product_id))


@functools.lru_cache(maxsize=1)
def attribution() -> Attribution:
    p = _payload()
    return Attribution(
        source=p.get("source", ""),
        source_url=p.get("source_url", ""),
        data_license=p.get("data_license", ""),
        image_license=p.get("image_license", ""),
        credit=p.get("attribution", ""),
        snapshot=p.get("snapshot", ""),
    )


@functools.lru_cache(maxsize=1)
def _by_id() -> dict[str, CatalogEntry]:
    return {e.product_id: e for e in entries()}


def get(product_id: str) -> CatalogEntry | None:
    return _by_id().get(product_id)


# --------------------------------------------------------------------------- search


@functools.lru_cache(maxsize=1)
def _index() -> tuple[tuple[CatalogEntry, frozenset[str], str], ...]:
    """Precomputed haystacks: (entry, searchable tokens, lowercase label).

    Built once. The catalogue is a few hundred rows, so scoring all of them per keystroke
    costs well under a millisecond — which is the entire reason this needs no search
    service, no index server, and no vector store (AGENTS.md §3.7).
    """
    out = []
    for e in entries():
        words = set()
        for field in (e.name, e.brand, e.variant, e.category, *e.synonyms):
            words.update(_tokens(field))
        out.append((e, frozenset(words), e.label.casefold()))
    return tuple(out)


def _score(query: str, tokens: frozenset[str], label: str, entry: CatalogEntry) -> int:
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0

    matched = 0
    total = 0
    for qt in q_tokens:
        best = 0
        if qt in tokens:
            best = 40
            if qt in _tokens(entry.brand):
                best += 12          # a brand word is a stronger signal than a noun
            if qt in _tokens(entry.variant):
                best += 8           # so is a flavour, which is how people disambiguate
        else:
            # Prefix match, so "choc" finds "chocolate" while the member is still typing.
            for word in tokens:
                if len(qt) >= 3 and word.startswith(qt):
                    best = max(best, 22)
        if best:
            matched += 1
            total += best

    if not matched:
        return 0
    # Every word the member typed should mean something. Partial matches still rank, but
    # far below complete ones, so "vanilla whey" cannot be beaten by an unrelated whey.
    if matched == len(q_tokens):
        total += 60
    else:
        total = total // 2

    phrase = " ".join(q_tokens)
    if phrase in label:
        total += 90                 # they typed the name; stop making them scroll
    if label.startswith(phrase):
        total += 25
    return total


def search(query: str, limit: int = DEFAULT_LIMIT) -> list[CatalogEntry]:
    """Rank catalogue entries against free text. Pure, offline, and stable.

    Ties break on ``(brand, name, product_id)`` rather than on iteration order, so the
    ranking is reproducible across processes and across rebuilds of the snapshot — which
    is what lets a test assert that a given query resolves to a given product.
    """
    query = (query or "").strip()
    if len(query) < MIN_QUERY_CHARS:
        return []
    limit = max(1, min(limit, MAX_LIMIT))

    scored = [
        (s, e)
        for e, tokens, label in _index()
        if (s := _score(query, tokens, label, e)) > 0
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1].brand, pair[1].name, pair[1].product_id))
    return [e for _, e in scored[:limit]]


def reset_cache() -> None:
    """Drop every memoised view of the snapshot.

    Only tests need this, but they need *all* of it: the parsed entries, the id map, the
    attribution, and the search index are four separate caches over one file, and
    clearing three of them leaves the fourth quietly serving the old snapshot.
    """
    for cached in (_payload, entries, attribution, _by_id, _index):
        cached.cache_clear()
