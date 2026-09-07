# flask-htmx-template

[![Unit Test][unittest-image]][unittest-url] [![Static Analysis][static-analysis-image]][static-analysis-url] [![Coverage][coverage-image]][coverage-url] [![Latest Version][pypi-image]][pypi-url]

A production-ready Flask + HTMX template for building modern web applications without a JavaScript framework. Clone it, rename it, and ship.

---

## What's Included

| Feature               | Details                                                                         |
| --------------------- | ------------------------------------------------------------------------------- |
| **Authentication**    | Password/session authentication, debug login, and database-backed bearer tokens |
| **Database**          | SQLAlchemy 2 with active-record helpers, PostgreSQL support                     |
| **Migrations**        | Versioned schema migrations with automatic detection on startup                 |
| **Material Design 3** | Icons, dynamic color palettes from a single swatch color + mood selector        |
| **Theme editor**      | Live-preview dialog with hue slider and mood picker, saved to cookies           |
| **HTMX patterns**     | Dialog system, snackbar notifications, partial page swaps, nav components       |
| **JSON API**          | Type-validated JSON endpoints with full error reporting                         |
| **MCP server**        | Authenticated Streamable HTTP endpoint with typed tool registration             |
| **CLI**               | `create`, `migrate`, `unlock`, and `change-password`                            |
| **Metrics**           | Prometheus metrics for the web application                                      |
| **Asset pipeline**    | Tailwind CSS v4, JS minification, automatic rebuild on package install          |
| **Testing**           | 100% coverage enforced, migration tests                                         |
| **Docker**            | Multi-stage build, non-root user, configurable via environment variables        |

---

## Project Structure

```
flask_htmx_template/
├── controllers/        # Route handlers (auth, common, items)
├── commands/           # CLI subcommands
├── models/             # SQLAlchemy ORM models
├── migrations/         # Versioned schema migrations
├── templates/          # Jinja2 HTML (shared components + per-controller)
├── static/src/         # Tailwind CSS + JavaScript source
├── static/dist/        # Compiled assets (generated, not committed)
├── web.py              # Flask app factory + extension
├── asgi.py             # Combined Flask + MCP ASGI app factory
├── mcp.py              # MCP server, tool registration, and metrics
├── web_theme.py        # Material Design 3 color generation
└── main.py             # CLI entry point
```

---

## Using This Template

1. Clone or use "Use this template" on GitHub
1. Find and replace `flask_htmx_template` with your project name (files, folders, pyproject.toml)
1. Update the package description in `pyproject.toml` and `main.py`
1. Add your models in `flask_htmx_template/models/`
1. Add your controllers in `flask_htmx_template/controllers/` and register them in `web.py`
1. Update `flask_htmx_template/static/src/css/main.css` fallback theme values if desired

---

## Start a new application

For a production installation:

```bash
python -m pip install .
# For autocomplete
activate-global-python-argcomplete
```

For local development, testing, Docker, PostgreSQL deployment, and code-style
commands, see [the development guide](dev.md).

## Run locally

```bash
# Create a new database
flask_htmx_template create

# Start the development server
flask --app flask_htmx_template.web run

# Start the combined web and MCP service
uvicorn --factory flask_htmx_template.asgi:create_app --host 127.0.0.1 --port 5000
```

### API bearer token

New databases receive an opaque API token in `ConfigKey.API_BEARER_TOKEN`. Send it
as `Authorization: Bearer <token>` to authenticate API requests. The token is stored
only in the database and isn't issued or validated by an external identity provider.

### Model Context Protocol

The combined ASGI service exposes a stateless Streamable HTTP MCP endpoint at
`http://127.0.0.1:5000/mcp`. Its item tools support the same list, get, create,
update, and delete operations as the HTML and JSON interfaces. The server records
per-tool call count and duration metrics in the web application's Prometheus registry.

The `get_items` response reports `count` as the number of items matching the
`before` filter before `limit` and `offset` are applied. Its `total` is the sum of
the `value` fields in the returned page, rather than the sum across all matches.
Missing item URIs return an MCP tool error with `_meta.errorCode` set to `-32004`
and the safe message `Requested resource was not found.`

Clients can discover stable JSON metadata with `resources/list` and
`resources/read`:

- `flask-htmx-template://metadata/server` identifies the application and version.
- `flask-htmx-template://metadata/capabilities` lists the transport,
  authentication method, tools, and resource URIs.

MCP requests must send the same database-backed API token as the JSON API:

```text
Authorization: Bearer <ConfigKey.API_BEARER_TOKEN>
```

Add tools in a controller's `mcp.py` and decorate each one with `base.mcp_tool`. The
plain Flask development command doesn't expose MCP; use the ASGI command above.

Use the project-local client to inspect a running server without putting the bearer
token in shell history or the process list:

```bash
export BEARER_TOKEN="<ConfigKey.API_BEARER_TOKEN>"
python tools/mcp_connect.py list-tools
python tools/mcp_connect.py list-resources
python tools/mcp_connect.py read-resource flask-htmx-template://metadata/server
python tools/mcp_connect.py read-resource flask-htmx-template://metadata/capabilities
python tools/mcp_connect.py call get_items
```

---

## Versioning

Follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html), implemented via git tags with `setuptools-scm`.

[pypi-image]: https://img.shields.io/pypi/v/flask-htmx-template.svg
[pypi-url]: https://pypi.org/project/flask-htmx-template/
[unittest-image]: https://github.com/WattsUp/flask-htmx-template/actions/workflows/test.yml/badge.svg
[unittest-url]: https://github.com/WattsUp/flask-htmx-template/actions/workflows/test.yml
[static-analysis-image]: https://github.com/WattsUp/flask-htmx-template/actions/workflows/static-analysis.yml/badge.svg
[static-analysis-url]: https://github.com/WattsUp/flask-htmx-template/actions/workflows/static-analysis.yml
[coverage-image]: https://gist.githubusercontent.com/WattsUp/36d9705addcd44fb0fccec1d23dc1338/raw/flask-htmx-template__heads_main.svg
[coverage-url]: https://github.com/WattsUp/flask-htmx-template/actions/workflows/coverage.yml
