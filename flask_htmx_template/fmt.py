"""Generic display formatters."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from flask_htmx_template import exceptions as exc
from flask_htmx_template import utils

if TYPE_CHECKING:
    from decimal import Decimal

THRESHOLD_MONTHS = 12 * 1.5
THRESHOLD_WEEKS = 4 * 2
THRESHOLD_DAYS = 7 * 1.5

THRESHOLD_HOURS = 96
THRESHOLD_MINUTES = 90
THRESHOLD_SECONDS = 90
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE
SECONDS_IN_DAY = 24 * SECONDS_IN_HOUR
PPM_THRESHOLD = 0.001


def days(days: int, labels: list[str] | None = None) -> str:
    """Format a day count as days, weeks, months, or years.

    Args:
        days: Number of days to format
        labels: Override labels for days, weeks, months, and years

    Returns:
        Day count with an appropriate unit

    """
    labels = labels or ["days", "weeks", "months", "years"]
    years = days / utils.DAYS_IN_YEAR
    months = years * utils.MONTHS_IN_YEAR
    if months > THRESHOLD_MONTHS:
        return f"{years:.0f} {labels[3]}"
    weeks = days / utils.DAYS_IN_WEEK
    if weeks > THRESHOLD_WEEKS:
        return f"{months:.0f} {labels[2]}"
    if days > THRESHOLD_DAYS:
        return f"{weeks:.0f} {labels[1]}"
    return f"{days} {labels[0]}"


def seconds(
    seconds: float,
    labels: list[str] | None = None,
    labels_days: list[str] | None = None,
) -> str:
    """Format elapsed seconds using the largest suitable time unit.

    Args:
        seconds: Number of seconds to format
        labels: Override labels for seconds, minutes, and hours
        labels_days: Override day labels passed to :func:`days`

    Returns:
        Elapsed time with an appropriate unit

    """
    labels = labels or ["seconds", "minutes", "hours"]
    hours = seconds / SECONDS_IN_HOUR
    if hours > THRESHOLD_HOURS:
        days_count = int(seconds // SECONDS_IN_DAY)
        return days(days_count, labels=labels_days)
    minutes = seconds / SECONDS_IN_MINUTE
    if minutes > THRESHOLD_MINUTES:
        return f"{hours:.1f} {labels[2]}"
    if seconds > THRESHOLD_SECONDS:
        return f"{minutes:.1f} {labels[1]}"
    return f"{seconds:.1f} {labels[0]}"


def price(value: Decimal | float, currency: str = "$") -> str:
    """Format a numeric value as a currency amount.

    Args:
        value: Amount to format
        currency: Currency symbol or label to place before the amount

    Returns:
        Currency amount with three decimal places

    """
    return f"{currency}{value:,.3f}"


def percent(value: Decimal | float) -> str:
    """Format a ratio as a percentage or parts per million.

    Ratios with an absolute value below 0.001 are displayed as ppm to retain
    useful precision.

    Args:
        value: Ratio to format

    Returns:
        Percentage or ppm string

    """
    # NOTE: ppm uses a float conversion so Decimal and float inputs share one
    # threshold and output path without mixed-type comparisons.
    ratio = float(value)
    if ratio == 0:
        return "0 %"
    if abs(ratio) < PPM_THRESHOLD:
        return f"{ratio * 1e6:,.0f} ppm"
    return f"{ratio * 100:,.2f} %"


def comma(value: Decimal | float) -> str:
    """Format a value with commas and two decimal places.

    Args:
        value: Numeric value to format

    Returns:
        Value with thousands separators and two decimal places

    """
    return f"{value:,.2f}"


def qty(value: Decimal | float) -> str:
    """Format a quantity with commas and six decimal places.

    Args:
        value: Quantity to format

    Returns:
        Quantity with thousands separators and six decimal places

    """
    return f"{value:,.6f}"


def input_value(value: object) -> str:
    """Format a value for use in a numeric input field.

    Trailing zeroes and a trailing decimal point are removed. Falsy values use
    an empty string so zero-valued fields retain the existing template behavior.

    Args:
        value: Value to place in an input field

    Returns:
        String representation with insignificant trailing zeroes removed

    """
    return str(value or "").rstrip("0").rstrip(".")


def pretty_table(table: list[list[str] | None]) -> list[str]:
    """Pretty print tabular data.

    First row is header, able to configure how columns behave
    "<Header" will left align text, default
    ">Header" will right align text
    "^Header" will center align text
    "Header." will prioritize this column for truncation with ellipsis if too long
    "Header/" will prevent this column being truncated

    Args:
        table: List of table rows, None will print a horizontal line

    Returns:
        List of rendered lines

    Raises:
        InvalidTableError: If table has no rows or the first row is None

    """
    if len(table) < 1:
        msg = "Table has no rows"
        raise exc.InvalidTableError(msg)
    table = list(table)

    header_raw = table.pop(0)
    if header_raw is None:
        msg = "First row cannot be None"
        raise exc.InvalidTableError(msg)

    header = [cell.strip("<>^./") for cell in header_raw]
    label_widths = [max(4, len(cell)) for cell in header]
    col_widths = [
        (
            max(len(cell), *[len(row[i]) if row else 0 for row in table])
            if table
            else len(cell)
        )
        for i, cell in enumerate(header)
    ]

    # Adjust column widths if their total exceeds terminal width.
    margin = shutil.get_terminal_size()[0] - sum(col_widths) - len(col_widths) - 2
    excess: list[int] = []
    extra = True
    has_extra: list[bool] = [False] * len(header_raw)
    for i, cell in enumerate(header_raw):
        n_label = label_widths[i]
        if extra and margin > 1:
            col_widths[i] += 2
            margin -= 2
            has_extra[i] = True
        if margin < 0 and cell[-1] == ".":
            n = max(n_label, col_widths[i] + margin)
            n_trim = col_widths[i] - n
            col_widths[i] = n
            margin += n_trim
            extra = False
        excess.append(0 if cell[-1] == "/" else max(0, col_widths[i] - n_label))

    while margin < 0 and any(excess):
        for i, column_excess in enumerate(excess):
            if margin < 0 and column_excess > 0:
                col_widths[i] -= 1
                excess[i] -= 1
                margin += 1

    formats: list[str] = []
    for cell, width in zip(header_raw, col_widths, strict=True):
        align = cell[0]
        align = align if align in "<>^" else ""
        formats.append(f"{align}{width}")
    return _table_to_lines(header, table, col_widths, formats, has_extra)


def _table_to_lines(
    header: list[str],
    table: list[list[str] | None],
    col_widths: list[int],
    formats: list[str],
    has_extra: list[bool],
) -> list[str]:
    lines: list[str] = []
    lines.append("╭" + "┬".join("─" * width for width in col_widths) + "╮")
    header_row = "│".join(
        f"{cell:^{width}}" for cell, width in zip(header, col_widths, strict=True)
    )
    lines.append("│" + header_row + "│")
    for row in table:
        if row is None:
            lines.append("╞" + "╪".join("═" * width for width in col_widths) + "╡")
            continue
        formatted_row = [
            (
                cell[: col_widths[i] - 1] + "…"
                if len(cell) > col_widths[i]
                else f"{{:{formats[i]}}}".format(
                    f" {cell} " if has_extra[i] else cell,
                )
            )
            for i, cell in enumerate(row)
        ]
        lines.append("│" + "│".join(formatted_row) + "│")

    lines.append("╰" + "┴".join("─" * width for width in col_widths) + "╯")
    return lines
