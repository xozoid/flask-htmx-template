"""Miscellaneous functions and classes."""

from __future__ import annotations

import ast
import calendar
import contextlib
import datetime
import logging
import operator as op
import pathlib
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import (
    cast,
    NamedTuple,
    overload,
    TYPE_CHECKING,
)

from flask_htmx_template import exceptions as exc
from flask_htmx_template import parsing

if TYPE_CHECKING:
    import inspect
    from collections.abc import Callable


_PACKAGE_DIR = pathlib.Path(__file__).parent
_UTILS_PATH = pathlib.Path(__file__)


_REGEX_CC_SC_0 = re.compile(r"(.)([A-Z][a-z]+)")
_REGEX_CC_SC_1 = re.compile(r"([a-z0-9])([A-Z])")
_REGEX_REAL_STATEMENT_LITERAL = re.compile(r"(?:(?:[eE][+-])|[^()+\-*/])+")

REAL_OPERATORS: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: cast("Callable[[Decimal, Decimal], Decimal]", op.truediv),
}
REAL_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Decimal], Decimal]] = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}

MIN_PASS_LEN = 8

MIN_STR_LEN = 2
SEARCH_THRESHOLD = 60
DUPLICATE_THRESHOLD = 80

DAYS_IN_YEAR = Decimal("365.25")
DAYS_IN_WEEK = 7
DAYS_IN_QUARTER = int(DAYS_IN_YEAR // 4)
MONTHS_IN_YEAR = 12

MATCH_PERCENT = Decimal("0.05")
MATCH_ABSOLUTE = Decimal(10)

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def first_party_caller(stack: list[inspect.FrameInfo]) -> inspect.FrameInfo:
    """Return the first frame belonging to this package.

    Frames from the standard library and third-party libraries are skipped so
    diagnostics identify the application query that initiated an operation.

    Args:
        stack: Stack frames from ``inspect.stack()``

    Returns:
        First frame inside the package, or the first entry when none match

    """
    for frame in stack:
        try:
            frame_path = pathlib.Path(frame.filename)
            if frame_path != _UTILS_PATH and frame_path.is_relative_to(_PACKAGE_DIR):
                return frame
        except ValueError:  # pragma: no cover
            # Paths on different drives cannot be compared on Windows.
            continue
    return stack[0]


class Downsampled(NamedTuple):
    """downsample results."""

    labels: list[str]
    min: list[Decimal]
    avg: list[Decimal]
    max: list[Decimal]


class Tokens(NamedTuple):
    """tokenize_search_str results."""

    must: set[str]
    can: set[str]
    not_: set[str]


def camel_to_snake(s: str) -> str:
    """Transform CamelCase to snake_case.

    Args:
        s: CamelCase to transform

    Returns:
        snake_case

    """
    s = _REGEX_CC_SC_0.sub(r"\1_\2", s)  # _ at the start of Words
    return _REGEX_CC_SC_1.sub(r"\1_\2", s).lower()  # _ at then end of Words


def _is_real_literal_character(char: str) -> bool:
    """Check whether a character is valid numeric display formatting.

    Args:
        char: Character to check

    Returns:
        Whether the character may appear in a numeric literal

    """
    # NOTE: Unicode category Sc covers currency symbols without maintaining a
    # hard-coded list of dollars, euros, pounds, yen, and other currencies.
    return (
        (char.isascii() and char.isdecimal())
        or char in ".,"
        or char.isspace()
        or unicodedata.category(char) == "Sc"
    )


def _eval_node(node: ast.expr) -> Decimal:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            literal = node.value.strip()
            with contextlib.suppress(InvalidOperation):
                literal = format(Decimal(literal), "f")
            if not all(_is_real_literal_character(char) for char in literal):
                msg = f"Unsupported numeric literal: {literal!r}"
                raise exc.EvaluationError(msg)
            try:
                value = parsing.real(literal, precision=None)
            except InvalidOperation:
                value = None
            if value is None:
                msg = f"Unable to parse numeric literal: {literal!r}"
                raise exc.EvaluationError(msg) from None
            return value
        if isinstance(node.value, int | float):
            return Decimal(node.value)
        msg = f"Unknown constant type: {node.value}({type(node.value)})"
        raise TypeError(msg)
    if isinstance(node, ast.BinOp):
        return REAL_OPERATORS[type(node.op)](
            _eval_node(node.left),
            _eval_node(node.right),
        )
    if isinstance(node, ast.UnaryOp):
        return REAL_UNARY_OPERATORS[type(node.op)](_eval_node(node.operand))
    msg = f"Unsupported node: '{type(node)}'"
    raise exc.EvaluationError(msg)


def evaluate_real_statement(s: str | None, precision: int | None = 2) -> Decimal | None:
    """Evaluate statement, using Decimal for numbers.

    Args:
        s: Arithmetic statement whose literals may include currency formatting
        precision: Number of digits to round number to, or None to preserve it

    Returns:
        Evaluated statement

    """
    if s is None:
        return None
    # NOTE: Keep exponent signs inside numeric literals while leaving arithmetic
    # operators unquoted for the AST to interpret.
    s = _REGEX_REAL_STATEMENT_LITERAL.sub(lambda match: repr(match.group()), s)
    try:
        value = _eval_node(ast.parse(s, mode="eval").body)
    except (exc.EvaluationError, SyntaxError, TypeError):
        return None
    return value if precision is None else round(value, precision)


def range_date(
    start: datetime.date | int,
    end: datetime.date | int,
    *,
    include_end: bool = True,
) -> list[datetime.date]:
    """Create a range of dates from start to end.

    Args:
        start: First date
        end: Last date
        include_end: True will include end date in range, False will not

    Returns:
        [start, ..., end] if include_end is True
        [start, ..., end) if include_end is False

    """
    start_ord = start if isinstance(start, int) else start.toordinal()
    end_ord = end if isinstance(end, int) else end.toordinal()
    if include_end:
        end_ord += 1
    return [datetime.date.fromordinal(i) for i in range(start_ord, end_ord)]


def date_add_months(date: datetime.date, months: int) -> datetime.date:
    """Add a number of months to a date.

    Args:
        date: Starting date
        months: Number of months to add, negative okay

    Returns:
        datetime.date(date.year, date.month + months, date.day)

    """
    m_sum = date.month + months - 1
    y = date.year + int(m_sum // 12)
    m = (m_sum % 12) + 1
    # Keep day but max out at end of month
    d = min(date.day, calendar.monthrange(y, m)[1])
    return datetime.date(y, m, d)


def date_months_between(start: datetime.date, end: datetime.date) -> int:
    """Count the numbers of months from start to end.

    Args:
        start: Starting date
        end: Ending date

    Returns:
        Number of months between, ignoring day of month

    """
    dm = end.month - start.month
    dy = end.year - start.year
    return dm + dy * 12


def weekdays_in_month(weekday: int, month: datetime.date) -> int:
    """Count the number of weekdays in a month.

    Args:
        weekday: [0, 6] matching datetime.date.weekday
        month: Month to check

    Returns:
        Number of specific weekday fall inside month

    """
    y = month.year
    m = month.month
    n, remainder = divmod(calendar.monthrange(y, m)[1], DAYS_IN_WEEK)
    if (weekday - month.weekday()) % 7 < remainder:
        return n + 1
    return n


def start_of_month(date: datetime.date) -> datetime.date:
    """Get the start of the month of a date.

    Args:
        date: Starting date

    Returns:
        datetime.date(date.year, date.month, 1)

    """
    return datetime.date(date.year, date.month, 1)


def end_of_month(date: datetime.date) -> datetime.date:
    """Get the end of the month of a date.

    Args:
        date: Starting date

    Returns:
        datetime.date(date.year, date.month, 28 to 31)

    """
    y = date.year
    m = date.month
    return datetime.date(y, m, calendar.monthrange(y, m)[1])


def period_months(start_ord: int, end_ord: int) -> dict[str, tuple[int, int]]:
    """Split a period into months.

    Args:
        start_ord: First date ordinal of period
        end_ord: Last date ordinal of period

    Returns:
        A dictionary of months and the ordinals that start and end them
        dict{"2000-01": (start_ord_0, end_ord_0), "2000-02": ...}
        Results will not fall outside of start_ord and end_ord

    """
    date = datetime.date.fromordinal(start_ord)
    y = date.year
    m = date.month
    end = datetime.date.fromordinal(end_ord)
    end_y = end.year
    end_m = end.month
    months: dict[str, tuple[int, int]] = {}
    while y < end_y or (y == end_y and m <= end_m):
        start_of_month_ = datetime.date(y, m, 1).toordinal()
        end_of_month_ = datetime.date(y, m, calendar.monthrange(y, m)[1]).toordinal()
        months[f"{y:04}-{m:02}"] = (
            max(start_ord, start_of_month_),
            min(end_ord, end_of_month_),
        )
        y += m // 12
        m = (m % 12) + 1
    return months


def period_years(start_ord: int, end_ord: int) -> dict[str, tuple[int, int]]:
    """Split a period into years.

    Args:
        start_ord: First date ordinal of period
        end_ord: Last date ordinal of period

    Returns:
        A dictionary of years and the ordinals that start and end them
        dict{"2000": (start_ord_0, end_ord_0), "2001": ...}
        Results will not fall outside of start_ord and end_ord

    """
    year = datetime.date.fromordinal(start_ord).year
    end_year = datetime.date.fromordinal(end_ord).year
    years: dict[str, tuple[int, int]] = {}
    while year <= end_year:
        jan_1 = datetime.date(year, 1, 1).toordinal()
        dec_31 = datetime.date(year, 12, 31).toordinal()
        years[str(year)] = (max(start_ord, jan_1), min(end_ord, dec_31))
        year += 1
    return years


def round_list(list_: list[Decimal], precision: int = 6) -> list[Decimal]:
    """Round a list, carrying over error such that sum(list) == sum(round_list).

    Args:
        list_: List to round
        precision: Precision to round list to

    Returns:
        List with rounded elements

    """
    residual = Decimal()
    l_rounded: list[Decimal] = []
    for item in list_:
        v = item + residual
        v_round = round(v, precision)
        residual = v - v_round
        l_rounded.append(v_round)

    return l_rounded


def integrate(deltas: list[Decimal | None] | list[Decimal]) -> list[Decimal]:
    """Integrate a list starting.

    Args:
        deltas: Change in values, use None instead of zero for faster speed

    Returns:
        list(values) where
        values[0] = sum(deltas[:1])
        values[1] = sum(deltas[:2])
        ...
        values[n] = sum(deltas[:])

    """
    n = len(deltas)
    current = Decimal()
    result = [Decimal()] * n

    for i, v in enumerate(deltas):
        if v is not None:
            current += v
        result[i] = current

    return result


def interpolate_step(values: list[tuple[int, Decimal]], n: int) -> list[Decimal]:
    """Interpolate a list of (index, value)s using a step function.

    Indices can be outside of [0, n)

    Args:
        values: List of (index, value)
        n: Length of output array

    Returns:
        list of interpolated values where result[i] = most recent values <= i

    """
    result = [Decimal()] * n
    if len(values) == 0:
        return result

    v_current = Decimal()
    values_i = 0
    i_next, v_next = values[values_i]
    for i in range(n):
        # If at a valuation, update current and prep next
        if i >= i_next:
            v_current = v_next
            values_i += 1
            try:
                i_next, v_next = values[values_i]
            except IndexError:
                # End of list, set i_v to n to never change current
                i_next = n
        result[i] = v_current

    return result


def interpolate_linear(values: list[tuple[int, Decimal]], n: int) -> list[Decimal]:
    """Interpolate a list of (index, value)s using a linear function.

    Indices can be outside of [0, n) to interpolate on the boundary

    Args:
        values: List of (index, value)
        n: Length of output array

    Returns:
        list of interpolated values

    """
    result = [Decimal()] * n
    if len(values) == 0:
        return result

    # Starting value
    i_current = 0
    v_current = Decimal()
    values_i = 0
    i_next, v_next = values[values_i]

    if i_next < 0:
        i_current = i_next
        v_current = v_next
        values_i += 1
        slope_i = -i_next

        # Compute slope to next
        try:
            i_next, v_next = values[values_i]
            slope = (v_next - v_current) / (i_next - i_current)
        except IndexError:
            # End of list, set i_v to n to never change current
            i_next = n
            slope = 0

    else:
        slope = 0
        slope_i = 0

    for i in range(n):
        # If at a valuation, update current and prep next
        if i >= i_next:
            i_current = i_next
            v_current = v_next
            values_i += 1
            slope_i = 0

            # Compute slope to next
            try:
                i_next, v_next = values[values_i]
                slope = (v_next - v_current) / (i_next - i_current)
            except IndexError:
                # End of list set i_v to n to never change current
                i_next = n
                slope = 0
            slope_i = 0
        result[i] = v_current + slope * slope_i
        slope_i += 1

    return result


def clamp(
    value: Decimal,
    c_min: Decimal = Decimal(),
    c_max: Decimal = Decimal(1),
) -> Decimal:
    """Clamp value to range.

    Args:
        value: Value to clamp
        c_min: Minimum value
        c_max: Maximum value

    Returns:
        value clamped to [c_min, c_max]

    """
    if value > c_max:
        return c_max
    if value < c_min:
        return c_min
    return value


@overload
def element_multiply(
    a: list[Decimal],
    b: list[Decimal],
) -> list[Decimal]: ...


@overload
def element_multiply(
    a: list[Decimal | None],
    b: list[Decimal],
) -> list[Decimal | None]: ...


def element_multiply(
    a: list[Decimal] | list[Decimal | None],
    b: list[Decimal],
) -> list[Decimal] | list[Decimal | None]:
    """Multiply two lists element-wise.

    Args:
        a: First list
        b: Second list

    Returns:
        [a[0] * b[0], ..., a[n] * b[n]]

    """
    return [None if aa is None else (aa * bb) for aa, bb in zip(a, b, strict=True)]


def set_sub_keys[_, T, V](dicts: dict[_, dict[T, V]]) -> set[T]:
    """Create a set from the subkeys of a nested dict.

    Args:
        dicts: Dict of dicts

    Returns:
        Set{*d.keys() for d in dicts.values()}

    """
    keys: set[T] = set()
    for d in dicts.values():
        keys.update(d.keys())
    return keys


def json_mutate(obj: object, *, skip_decimal: bool = False) -> object:
    """Mutate an object into JSON representation.

    Args:
        obj: Object to mutate
        skip_decimal: True will not transform Decimal into a string

    Returns:
        JSON types only

    """
    if isinstance(obj, dict):
        obj_dict = cast("dict[object, object]", obj)
        return {
            k: json_mutate(v, skip_decimal=skip_decimal) for k, v in obj_dict.items()
        }
    if isinstance(obj, list | tuple):
        obj_seq = cast("list[object] | tuple[object, ...]", obj)
        return [json_mutate(v, skip_decimal=skip_decimal) for v in obj_seq]
    if isinstance(obj, Enum):
        return obj.name.lower()
    if not skip_decimal and isinstance(obj, Decimal):
        o_int = int(obj)
        return o_int if o_int == obj else str(obj)
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


def init_logger(*, debug: bool = False) -> None:
    """Initialize logger.

    Args:
        debug: True will set the level to DEBUG

    """
    logger = logging.getLogger("flask_htmx_template")

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
