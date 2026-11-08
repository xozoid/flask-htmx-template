"""Parse common primitive values from strings."""

from __future__ import annotations

import datetime
import re
from decimal import Decimal

_REGEX_REAL_CLEAN = re.compile(r"[^0-9\.]")
_REGEX_REAL_GROUPED = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?\Z")
_REGEX_REAL_OPERATORS = re.compile(r"[()+\-*/]")


def real(s: str | None, precision: int | None = 2) -> Decimal | None:
    """Parse a real number from a string.

    Args:
        s: String to parse
        precision: Number of decimal places to round to, or None not to round

    Returns:
        Parsed value, or None if the string holds no number

    """
    if s is None:
        return None
    # NOTE: Validate each arithmetic operand separately so an expression with
    # multiple grouped amounts does not merge their digits before checking.
    for operand in _REGEX_REAL_OPERATORS.split(s):
        numeric = re.sub(r"[^0-9,.]", "", operand)
        if "," in numeric and _REGEX_REAL_GROUPED.fullmatch(numeric) is None:
            return None
    clean = _REGEX_REAL_CLEAN.sub("", s)
    if not clean:
        return None
    # NOTE: The sign is inferred from the original string because the
    # cleaning regex intentionally strips minus signs and parentheses.
    value = -Decimal(clean) if "-" in s or "(" in s else Decimal(clean)
    return value if precision is None else round(value, precision)


def int_(s: str | None) -> int | None:
    """Parse an integer from a string.

    Args:
        s: String to parse

    Returns:
        Parsed value, or None if the string holds no number

    """
    value = real(s)
    return None if value is None else int(value)


def bool_(s: str | None) -> bool | None:
    """Parse a boolean from a string.

    Args:
        s: String to parse

    Returns:
        Parsed value, or None if the string is empty

    """
    if s is None or not s:
        return None
    return s.lower() in {"true", "t", "1"}


def date(s: str | None) -> datetime.date | None:
    """Parse an ISO date from a string.

    Args:
        s: String to parse

    Returns:
        Parsed value, or None if the string is empty

    """
    if s is None or not s:
        return None
    return datetime.date.fromisoformat(s)
