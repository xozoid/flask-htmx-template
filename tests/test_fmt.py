from __future__ import annotations

import textwrap
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from flask_htmx_template import exceptions as exc
from flask_htmx_template import fmt, parsing

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    ("day_count", "target"),
    [
        (0, "0 days"),
        (10, "10 days"),
        (11, "2 weeks"),
        (8 * 7, "8 weeks"),
        (8 * 7 + 1, "2 months"),
        (int(18 * 365.25 / 12), "18 months"),
        (int(18 * 365.25 / 12 + 1), "2 years"),
    ],
)
def test_days_selects_largest_suitable_unit(day_count: int, target: str) -> None:
    assert fmt.days(day_count) == target


def test_days_uses_custom_labels() -> None:
    result = fmt.days(14, labels=["d", "wk", "mo", "yr"])

    assert result == "2 wk"


@pytest.mark.parametrize(
    ("second_count", "target"),
    [
        (0, "0.0 seconds"),
        (60, "60.0 seconds"),
        (90.1, "1.5 minutes"),
        (5400.1, "1.5 hours"),
        (86400, "24.0 hours"),
        (86400 * 4, "96.0 hours"),
        (86400 * 4.1, "4 days"),
    ],
)
def test_seconds_selects_largest_suitable_unit(
    second_count: float,
    target: str,
) -> None:
    assert fmt.seconds(second_count) == target


def test_seconds_uses_custom_labels() -> None:
    result = fmt.seconds(
        120,
        labels=["sec", "min", "hr"],
    )

    assert result == "2.0 min"


@pytest.mark.parametrize(
    ("value", "currency", "target"),
    [
        (Decimal("1234.5"), "$", "$1,234.500"),
        (Decimal(12), "EUR ", "EUR 12.000"),
    ],
)
def test_price_formats_currency(
    value: Decimal,
    currency: str,
    target: str,
) -> None:
    assert fmt.price(value, currency) == target


@pytest.mark.parametrize(
    ("value", "target"),
    [
        (Decimal(0), "0 %"),
        (Decimal("0.1234"), "12.34 %"),
        (Decimal("0.000001"), "1 ppm"),
        (Decimal("-0.000001"), "-1 ppm"),
        (Decimal("0.001"), "0.10 %"),
    ],
)
def test_percent_formats_ratio(value: Decimal, target: str) -> None:
    assert fmt.percent(value) == target


@pytest.mark.parametrize(
    ("formatter", "value", "target"),
    [
        (fmt.comma, Decimal("1000.1"), "1,000.10"),
        (fmt.qty, Decimal("1000.1"), "1,000.100000"),
    ],
)
def test_numeric_formatters(
    formatter: Callable[[Decimal], str],
    value: Decimal,
    target: str,
) -> None:
    assert formatter(value) == target


@pytest.mark.parametrize(
    ("formatter", "value", "target"),
    [
        (fmt.comma, Decimal("1234.5"), Decimal("1234.50")),
        (fmt.qty, Decimal("1234.5"), Decimal("1234.500000")),
        (fmt.price, Decimal("1234.5"), Decimal("1234.500")),
        (fmt.input_value, Decimal("1234.500000"), Decimal("1234.5")),
    ],
)
def test_numeric_formatter_output_can_be_parsed(
    formatter: Callable[[Decimal], str],
    value: Decimal,
    target: Decimal,
) -> None:
    formatted = formatter(value)

    assert parsing.real(formatted, precision=None) == target


def test_pretty_table_no_rows() -> None:
    with pytest.raises(exc.InvalidTableError, match="Table has no rows"):
        fmt.pretty_table([])


def test_pretty_table_no_header() -> None:
    with pytest.raises(exc.InvalidTableError, match="First row cannot be None"):
        fmt.pretty_table([None])


@pytest.fixture
def fixed_terminal(
    monkeypatch: pytest.MonkeyPatch,
    width: int,
    height: int,
) -> None:
    def mock_terminal_size(**_: object) -> tuple[int, int]:
        return width, height

    monkeypatch.setattr("shutil.get_terminal_size", mock_terminal_size)


@pytest.mark.parametrize(("width", "height"), [(80, 24)])
def test_pretty_table_only_header(fixed_terminal: None) -> None:
    table: list[list[str] | None] = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
    ]
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
    ╰────┴────┴────┴────┴────┴────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.mark.parametrize(("width", "height"), [(80, 24)])
def test_pretty_table_only_separator(fixed_terminal: None) -> None:
    table: list[list[str] | None] = [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
        None,
    ]
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │ H6 │
    ╞════╪════╪════╪════╪════╪════╡
    ╰────┴────┴────┴────┴────┴────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.fixture
def table() -> list[list[str] | None]:
    return [
        ["H1", ">H2", "<H3", "^H4", "H5.", "H6/"],
        None,
        ["Short"] * 6,
        None,
        ["Long word"] * 6,
    ]


@pytest.mark.parametrize(("width", "height"), [(80, 24)])
def test_pretty_table_width_80(
    fixed_terminal: None,
    table: list[list[str] | None],
) -> None:
    target = textwrap.dedent(
        """\
    ╭───────────┬───────────┬───────────┬───────────┬───────────┬───────────╮
    │    H1     │    H2     │    H3     │    H4     │    H5     │    H6     │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
    │ Short     │     Short │ Short     │   Short   │ Short     │ Short     │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═══════════╪═══════════╡
    │ Long word │ Long word │ Long word │ Long word │ Long word │ Long word │
    ╰───────────┴───────────┴───────────┴───────────┴───────────┴───────────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.mark.parametrize(("width", "height"), [(70, 24)])
def test_pretty_table_width_70(
    fixed_terminal: None,
    table: list[list[str] | None],
) -> None:
    target = textwrap.dedent(
        """\
    ╭───────────┬───────────┬───────────┬───────────┬─────────┬─────────╮
    │    H1     │    H2     │    H3     │    H4     │   H5    │   H6    │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═════════╪═════════╡
    │ Short     │     Short │ Short     │   Short   │Short    │Short    │
    ╞═══════════╪═══════════╪═══════════╪═══════════╪═════════╪═════════╡
    │ Long word │ Long word │ Long word │ Long word │Long word│Long word│
    ╰───────────┴───────────┴───────────┴───────────┴─────────┴─────────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.mark.parametrize(("width", "height"), [(60, 24)])
def test_pretty_table_width_60(
    fixed_terminal: None,
    table: list[list[str] | None],
) -> None:
    target = textwrap.dedent(
        """\
    ╭─────────┬─────────┬─────────┬─────────┬───────┬─────────╮
    │   H1    │   H2    │   H3    │   H4    │  H5   │   H6    │
    ╞═════════╪═════════╪═════════╪═════════╪═══════╪═════════╡
    │Short    │    Short│Short    │  Short  │Short  │Short    │
    ╞═════════╪═════════╪═════════╪═════════╪═══════╪═════════╡
    │Long word│Long word│Long word│Long word│Long w…│Long word│
    ╰─────────┴─────────┴─────────┴─────────┴───────┴─────────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.mark.parametrize(("width", "height"), [(50, 24)])
def test_pretty_table_width_50(
    fixed_terminal: None,
    table: list[list[str] | None],
) -> None:
    target = textwrap.dedent(
        """\
    ╭───────┬───────┬───────┬────────┬────┬─────────╮
    │  H1   │  H2   │  H3   │   H4   │ H5 │   H6    │
    ╞═══════╪═══════╪═══════╪════════╪════╪═════════╡
    │Short  │  Short│Short  │ Short  │Sho…│Short    │
    ╞═══════╪═══════╪═══════╪════════╪════╪═════════╡
    │Long w…│Long w…│Long w…│Long wo…│Lon…│Long word│
    ╰───────┴───────┴───────┴────────┴────┴─────────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target


@pytest.mark.parametrize(("width", "height"), [(10, 24)])
def test_pretty_table_width_10(
    fixed_terminal: None,
    table: list[list[str] | None],
) -> None:
    target = textwrap.dedent(
        """\
    ╭────┬────┬────┬────┬────┬─────────╮
    │ H1 │ H2 │ H3 │ H4 │ H5 │   H6    │
    ╞════╪════╪════╪════╪════╪═════════╡
    │Sho…│Sho…│Sho…│Sho…│Sho…│Short    │
    ╞════╪════╪════╪════╪════╪═════════╡
    │Lon…│Lon…│Lon…│Lon…│Lon…│Long word│
    ╰────┴────┴────┴────┴────┴─────────╯""",
    )
    assert "\n".join(fmt.pretty_table(table)) == target
