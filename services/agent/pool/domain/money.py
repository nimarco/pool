"""Exact money arithmetic.

Every monetary value in Pool is an integer number of cents. Floats never touch
money: a float cent is a rounding bug waiting to become a wrong number in a
message to a human (AGENTS.md §5).

Savings percentages are carried as integer basis points (1 bp = 0.01%) for the
same reason — policy thresholds are compared in bps, never in floats.
"""

from __future__ import annotations


class MoneyError(ValueError):
    """Raised when a monetary invariant is violated."""


def cents(dollars: float | int | str) -> int:
    """Convert a human-entered amount to integer cents.

    Accepts a string like "12.34" (exact) or a number (rounded half-up at the cent).
    Prefer the string form for anything originating from a human or a fixture.
    """
    if isinstance(dollars, str):
        text = dollars.strip().replace("$", "").replace(",", "")
        neg = text.startswith("-")
        if neg:
            text = text[1:]
        if "." in text:
            whole, _, frac = text.partition(".")
            if len(frac) > 2:
                raise MoneyError(f"more precision than cents: {dollars!r}")
            frac = (frac + "00")[:2]
        else:
            whole, frac = text, "00"
        if not whole.isdigit() or not frac.isdigit():
            raise MoneyError(f"not a monetary amount: {dollars!r}")
        value = int(whole) * 100 + int(frac)
        return -value if neg else value
    # Numeric input: round half-up on the absolute value so -0.005 and 0.005 agree.
    scaled = dollars * 100
    sign = -1 if scaled < 0 else 1
    return sign * int(abs(scaled) + 0.5)


def format_cents(amount: int) -> str:
    """Render cents as a display string. Never used as an input to further math."""
    sign = "-" if amount < 0 else ""
    a = abs(amount)
    return f"{sign}${a // 100}.{a % 100:02d}"


def allocate_cost(total_cents: int, weights: list[int]) -> list[int]:
    """Split ``total_cents`` across ``weights`` so the parts sum to exactly the total.

    Uses the largest-remainder method: every household pays its proportional share,
    and the leftover cents (which cannot be split further) go to the households with
    the largest fractional remainders. Deterministic and order-stable — ties break
    toward the earlier index, so the same inputs always produce the same split.
    """
    if total_cents < 0:
        raise MoneyError("cannot allocate a negative total")
    if any(w < 0 for w in weights):
        raise MoneyError("weights must be non-negative")
    total_weight = sum(weights)
    if total_weight == 0:
        if total_cents != 0:
            raise MoneyError("cannot allocate a non-zero total across zero weight")
        return [0] * len(weights)

    base: list[int] = []
    remainders: list[tuple[int, int]] = []  # (remainder numerator, index)
    for i, w in enumerate(weights):
        exact = total_cents * w
        share = exact // total_weight
        base.append(share)
        remainders.append((exact - share * total_weight, i))

    leftover = total_cents - sum(base)
    # Largest remainder first; earlier index wins a tie.
    remainders.sort(key=lambda pair: (-pair[0], pair[1]))
    for k in range(leftover):
        base[remainders[k][1]] += 1
    return base


def savings_bps(baseline_cents: int, actual_cents: int) -> int:
    """Savings as integer basis points of the baseline. 2500 bps == 25%.

    Returns 0 when the baseline is 0 (nothing to save against) and can go negative
    when the "deal" is worse than retail — callers must treat negative as a failure
    to beat baseline, not clamp it away.
    """
    if baseline_cents <= 0:
        return 0
    saved = baseline_cents - actual_cents
    # Round half-away-from-zero at the basis point.
    scaled = saved * 10_000
    sign = -1 if scaled < 0 else 1
    return sign * ((abs(scaled) * 2 + baseline_cents) // (2 * baseline_cents))


def bps_to_pct_str(bps: int) -> str:
    """Render basis points for display, e.g. 3780 -> '37.8%'."""
    sign = "-" if bps < 0 else ""
    a = abs(bps)
    return f"{sign}{a // 100}.{(a % 100) // 10}%"


def pct_to_bps(pct: int | float) -> int:
    """Convert a whole-percent policy threshold to basis points."""
    return int(round(pct * 100))
