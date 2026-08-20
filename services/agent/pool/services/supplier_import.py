"""Reading a supplier's quotes out of a file, for real.

The demo turns on one claim: Pool's answer changes when the *world* changes rather than
when the demand does. Something outside the system has to arrive for that to be
demonstrable, and how it arrives decides whether a judge believes it.

Two hardcoded ``Record quote`` buttons made the mechanism honest and the *presentation*
indistinguishable from a switch. So the same terms now arrive the way supplier terms
actually arrive: as a file somebody sends you. Two sheets under ``demo-data/`` are
committed, readable on GitHub, and parsed here — really parsed, by :mod:`csv`, with a
schema, with rows that can and do fail.

Two rather than one, because the order matters. The split-case sheet clears the supplier
minimum and fills whole cases and is *still* refused once a fulfiller's pay, processing
and Pool's fee are counted; the programme sheet is the one that works. A single file
containing both would land them together and skip the refusal, which is the half of the
sequence that makes it evidence rather than a switch.

The claim this supports is exactly: **real ingestion pipeline, synthetic dataset.** Not
"real supplier data". Riverbend Wholesale does not exist.

The conflict worth reading carefully
------------------------------------
This build deliberately refuses client-submitted economics. ``SupplierQuoteRequest`` sets
``extra="forbid"`` so a request that *tries* to send a price is rejected rather than
quietly stripped, because a stranger who can set a price can poison every figure the site
derives from it — and because a control that let somebody type prices until Pool said yes
would demonstrate nothing except that Pool does arithmetic.

An unrestricted upload endpoint hands that authority straight back. ``$0.01`` rice would
make Pool look brilliant and prove nothing.

The resolution is that these are two different questions:

* **Is the pipeline real?** Always. The bytes are read, the parser runs, the schema is
  checked, malformed rows are counted and named, and nothing is pre-decided. That is
  true of every upload on every deployment.
* **Whose numbers may become offer rows?** On a deployment strangers can reach, only
  bytes whose digest is in ``demo-data/MANIFEST.json``. A judge downloads the file from
  the repository, uploads it, and watches it parse; change one price and it is refused,
  with the reason named. Locally — where whoever is running the process already owns the
  database — any file is accepted, because there is nobody to protect the operator from.

So the parse result is honest either way, and only the *write* is gated. A refusal still
reports what the file contained, because "your file was rejected" and "your file was
unreadable" are different facts and the second one is not true.

What a valid row may say
------------------------
Terms, and only terms: which product, which supplier, the unit price, the case size, the
minimum, and the supplier's own reference. There is no column for a verdict, a saving, a
viability flag or an expected outcome, and there is nowhere to put one — the same
separation the catalogue keeps between what a product *is* and what a supplier *charges*.

Every row lands as :data:`~pool.domain.models.OfferSource.SYNTHETIC`, which is what it
is. ``MANUAL_VERIFIED`` would be the closer match for the act and the wrong label for
the fact: Operations renders that source as a chip meaning a human confirmed a real quote
with a real supplier.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..domain.models import MoqKind, Offer, OfferKind, OfferSource, iso, utcnow
from .context import PoolContext

#: Where the committed fixtures and their digests live, relative to the repository root.
_HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "..", "demo-data"))
MANIFEST_PATH = os.path.join(DEMO_DATA_DIR, "MANIFEST.json")

#: The columns a row must carry. Extra columns are ignored rather than refused — a
#: supplier's export having a column Pool does not read is not an error, and refusing
#: the file for it would be pretending to a strictness this format does not have.
REQUIRED_COLUMNS = (
    "product_id",
    "supplier_id",
    "unit_price_cents",
    "case_units",
    "min_units",
    "supplier_reference",
)

#: Bounds, so a typo cannot become a price. These are sanity limits rather than policy:
#: whether a priced order is *worth doing* is the evaluator's answer and is not decided
#: here or anywhere near here.
MAX_UNIT_PRICE_CENTS = 100_000
MAX_CASE_UNITS = 500
MAX_MIN_UNITS = 10_000
#: A whole file, capped. Large enough for any real quote sheet, small enough that a
#: hostile upload cannot cost anything.
MAX_BYTES = 64 * 1024
MAX_ROWS = 200


class SupplierImportError(ValueError):
    """The file itself could not be used. Distinct from a row that failed."""


@dataclass(frozen=True)
class QuoteRow:
    """One supplier quote, as the file stated it and the schema accepted it."""

    line: int
    product_id: str
    supplier_id: str
    unit_price_cents: int
    case_units: int
    min_units: int
    supplier_reference: str
    quoted_at: str = ""

    @property
    def offer_id(self) -> str:
        """Stable, so re-importing the same sheet refreshes rather than accumulating.

        Derived from the supplier's own reference where there is one: two imports of one
        quote must not leave Pool believing it has two tiers, which would double the
        supply the evaluator thinks exists.
        """
        ref = "".join(c for c in self.supplier_reference.lower() if c.isalnum() or c == "-")
        return f"off_import_{ref}" if ref else f"off_import_{self.product_id}_{self.min_units}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "product_id": self.product_id,
            "supplier_id": self.supplier_id,
            "unit_price_cents": self.unit_price_cents,
            "case_units": self.case_units,
            "min_units": self.min_units,
            "supplier_reference": self.supplier_reference,
            "quoted_at": self.quoted_at,
            "offer_id": self.offer_id,
            "synthetic": True,
        }


@dataclass(frozen=True)
class RejectedRow:
    """A row the schema refused, and why — named, so a file can be fixed."""

    line: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "reason": self.reason}


@dataclass
class ParseResult:
    """What was in the file. Says nothing about whether any of it was written."""

    filename: str
    sha256: str
    byte_count: int
    rows: list[QuoteRow] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.rows) + len(self.rejected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "bytes": self.byte_count,
            "rows_found": self.total,
            "valid": len(self.rows),
            "rejected": len(self.rejected),
            "records": [r.to_dict() for r in self.rows],
            "rejections": [r.to_dict() for r in self.rejected],
        }


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest() -> dict[str, dict[str, Any]]:
    """The allowlisted fixtures, by filename. Empty when the manifest is absent.

    Absent means *nothing is allowlisted*, which fails closed: on a public deployment a
    missing manifest refuses every upload rather than accepting every upload.
    """
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as handle:
            return dict(json.load(handle).get("files", {}))
    except (OSError, ValueError):
        return {}


def fixture_path(name: str) -> Path:
    """Where a committed sheet lives, for a name already checked against the manifest.

    Takes the basename only. The caller validates ``name`` against
    :func:`fixture_order`, and this refuses to build a path out of anything else, so
    neither a traversal nor a sibling file can be reached even if that check is ever
    weakened.
    """
    return Path(DEMO_DATA_DIR) / os.path.basename(name)


def fixture_order() -> list[str]:
    """The sheets in the order the demo uses them, or alphabetical if unstated.

    Which sheet arrives first is load-bearing: the split-case programme clears the
    supplier minimum and is *still* refused, and that refusal is what makes the sequence
    evidence rather than a switch. A demo that imported the better sheet first would
    demonstrate only that Pool can say yes.
    """
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []
    stated = [str(n) for n in payload.get("order", [])]
    files = sorted(payload.get("files", {}))
    return stated + [f for f in files if f not in stated]


def allowlisted(data: bytes) -> str:
    """The name of the committed fixture these bytes are, or ``""``.

    Compares digests rather than filenames, because a filename is something the uploader
    chooses and a digest is something the bytes are.
    """
    want = digest(data)
    for name, entry in manifest().items():
        if entry.get("sha256") == want:
            return name
    return ""


def _int(raw: str, label: str, *, maximum: int) -> int:
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"{label} is missing")
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"{label} is not a whole number: {text!r}") from None
    if value <= 0:
        raise ValueError(f"{label} must be greater than zero")
    if value > maximum:
        raise ValueError(f"{label} is above the accepted maximum of {maximum}")
    return value


def parse(data: bytes, filename: str = "") -> ParseResult:
    """Read supplier quotes out of CSV bytes. Pure: touches no repository.

    Comment lines (``#``) and blank lines are skipped, so a fixture can explain itself
    to whoever opens it — which is the whole point of committing one.

    A row that fails is *recorded*, not fatal. A quote sheet with one bad line is an
    ordinary thing to receive, and refusing the file would throw away the good rows and
    tell the operator nothing about which line to look at.
    """
    if len(data) > MAX_BYTES:
        raise SupplierImportError(
            f"that file is {len(data)} bytes; the limit is {MAX_BYTES}"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SupplierImportError("that file is not UTF-8 text") from None

    # Line numbers are the *file's*, so a rejection points at the line an operator can
    # open. csv's own row count would be off by every comment and blank line.
    numbered = list(enumerate(text.splitlines(), start=1))
    body = [(n, line) for n, line in numbered if line.strip() and not line.lstrip().startswith("#")]
    result = ParseResult(filename=filename, sha256=digest(data), byte_count=len(data))
    if not body:
        raise SupplierImportError("that file has no rows in it")

    reader = csv.DictReader(io.StringIO("\n".join(line for _, line in body)))
    if reader.fieldnames is None:
        raise SupplierImportError("that file has no header row")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise SupplierImportError(
            "the header is missing " + ", ".join(missing)
        )

    # The header consumed the first body line; data rows start at the second.
    data_lines = [n for n, _ in body][1:]
    for index, row in enumerate(reader):
        if index >= MAX_ROWS:
            raise SupplierImportError(f"that file has more than {MAX_ROWS} rows")
        line = data_lines[index] if index < len(data_lines) else 0
        try:
            product_id = (row.get("product_id") or "").strip()
            supplier_id = (row.get("supplier_id") or "").strip()
            reference = (row.get("supplier_reference") or "").strip()
            if not product_id:
                raise ValueError("product_id is missing")
            if not supplier_id:
                raise ValueError("supplier_id is missing")
            quote = QuoteRow(
                line=line,
                product_id=product_id,
                supplier_id=supplier_id,
                unit_price_cents=_int(
                    row.get("unit_price_cents", ""),
                    "unit_price_cents",
                    maximum=MAX_UNIT_PRICE_CENTS,
                ),
                case_units=_int(
                    row.get("case_units", ""), "case_units", maximum=MAX_CASE_UNITS
                ),
                min_units=_int(
                    row.get("min_units", ""), "min_units", maximum=MAX_MIN_UNITS
                ),
                supplier_reference=reference,
                quoted_at=(row.get("quoted_at") or "").strip(),
            )
        except ValueError as exc:
            result.rejected.append(RejectedRow(line=line, reason=str(exc)))
            continue
        result.rows.append(quote)
    return result


def resolvable(ctx: PoolContext, rows: list[QuoteRow]) -> tuple[list[QuoteRow], list[RejectedRow]]:
    """Split parsed rows by whether this workspace can actually hold them.

    A quote for a product Pool has never heard of is a real rejection with a real reason,
    not a silent drop and not a new product. Importing a *quote* must never bring a
    product into existence: identity and economics are separate on purpose, and a
    supplier sheet is not evidence that a product exists.
    """
    known = {p.id for p in ctx.repo.list_products(ctx.ws)}
    suppliers = {s.id for s in ctx.repo.list_suppliers(ctx.ws)}
    ok: list[QuoteRow] = []
    bad: list[RejectedRow] = []
    for row in rows:
        if row.product_id not in known:
            bad.append(
                RejectedRow(row.line, f"no product {row.product_id} in this community")
            )
        elif row.supplier_id not in suppliers:
            bad.append(
                RejectedRow(row.line, f"no supplier {row.supplier_id} in this community")
            )
        else:
            ok.append(row)
    return ok, bad


def record(ctx: PoolContext, rows: list[QuoteRow]) -> list[Offer]:
    """Write accepted quotes as ordinary bulk offers, and return them.

    The same kind of row the seeded catalogue holds, read by the same ``offers_for``
    every price in this system already comes from. No import mode, no scenario flag, and
    nothing for the evaluator to be taught about — which is why the verdict afterwards is
    not scripted anywhere.
    """
    written: list[Offer] = []
    for row in rows:
        offer = Offer(
            id=row.offer_id,
            supplier_id=row.supplier_id,
            product_id=row.product_id,
            kind=OfferKind.BULK,
            unit_price_cents=row.unit_price_cents,
            case_units=row.case_units,
            moq_kind=MoqKind.UNITS,
            moq_amount=row.min_units,
            # The moment the quote entered Pool's records, which is genuinely now.
            # `quoted_at` from the file is the supplier's claim about when they quoted
            # it, and is kept as a reference rather than used as freshness (§43).
            verified_at=iso(utcnow()),
            valid_until="",
            source=OfferSource.SYNTHETIC,
            supplier_reference=row.supplier_reference,
        )
        ctx.repo.put_offer(ctx.ws, offer)
        written.append(offer)
    return written
