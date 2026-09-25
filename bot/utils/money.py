"""Money helpers. All amounts are integers in cents (bani, kopecks...)."""

from __future__ import annotations

import re

MAX_AMOUNT_CENTS = 100_000_000  # 1 000 000.00

_AMOUNT_RE = re.compile(
    r"^\s*(?P<units>\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](?P<cents>\d{1,2}))?"
    r"\s*[^\d\s]{0,8}\.?\s*$"
)


def parse_amount(value: str) -> int | None:
    """'45', '45.5', '45,50', '1 200', '120 лей' -> cents; None if invalid or not positive."""
    match = _AMOUNT_RE.match(value)
    if not match:
        return None
    units = int(re.sub(r"\D", "", match.group("units")))
    cents = int((match.group("cents") or "0").ljust(2, "0"))
    total = units * 100 + cents
    if total <= 0 or total > MAX_AMOUNT_CENTS:
        return None
    return total


def format_money(cents: int, currency: str) -> str:
    """12345 -> '123.45 MDL', 4000 -> '40 MDL', -4000 -> '−40 MDL'."""
    sign = "−" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    number = f"{units:,}".replace(",", " ")
    if rest:
        number += f".{rest:02d}"
    return f"{sign}{number} {currency}".strip()
