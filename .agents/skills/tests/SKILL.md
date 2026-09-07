---
name: tests
description: >
  Pytest layout, fixtures, Flask client helpers, database setup, and HTML or
  API coverage for flask-htmx-template. Use when adding or reorganizing tests.
---

## Test layout

Mirror the source tree under `tests/` and keep every test directory as a Python
package with `__init__.py`. Name files `test_<topic>.py`. Resource controller
tests live under `tests/controllers/<resource>/`; model tests live under
`tests/models/`. Split large controller coverage by behavior, such as HTML,
JSON, context, or MCP handlers, while matching the existing resource layout.

## Fixtures and database sessions

Shared fixtures are in `tests/conftest.py`; controller-specific fixtures are in
`tests/controllers/conftest.py`. Use the provided `session` fixture for an
isolated SQLite database and active `Base.set_session()` binding. Common model
fixtures include `item`, `today`, and generated strings or decimals. Use the
`web_client` fixture for registered Flask routes and its named endpoint helpers
(`GET`, `POST`, `PUT`, and `DELETE`) instead of constructing requests manually.

When setup needs multiple writes, use the fixture session and a nested
transaction. Refresh ORM objects before asserting values changed through a
request. Freeze time with the existing time-machine fixtures when date or UTC
behavior matters.

## Test structure and names

Use one Act per test and separate Arrange, Act, and Assert phases with blank
lines when useful. Name tests for the behavior and condition, for example
`test_page_all_rejects_invalid_pagination`. Use noun-phrase fixture names and
type annotations on fixtures and test functions.

Prefer `pytest.mark.parametrize` for equivalent input and expected-output cases.
Keep imports at module scope and use `TYPE_CHECKING` for imports needed only by
annotations.

## HTTP and template assertions

Controller tests should cover status codes, response content, redirects,
HTMX headers, and persistence where relevant. HTML tests also exercise the
repository's structural checks in `tests/controllers/conftest.py`; preserve
valid HTMX targets, disabled elements, URL pushes, and attribute order. JSON
tests should assert the response shape and error status, not only a serialized
string. Add focused tests for migrations and schema compatibility when a
database change is introduced.

## Verification

Run a focused test file while iterating, then run `python -m pytest` before
handoff. Keep branch coverage at the repository's configured 100 percent and
run `./tools/linters.sh` when changing Python, templates, or test structure.
