# Development guide

Developer reference for `flask-htmx-template`. Read a component's source and
docstrings for behavior that's specific to that component. Source files mark
non-obvious corner cases with `# NOTE:` comments.

## Environment

### Setup

Python 3.12 or later is required. Node 24 or later is used only for web
formatters, and Vale is used only for prose linting.

```shell
# Install the application and all development dependencies in editable mode.
uv pip install -e .[dev]
# Download the prose-linting styles declared in .vale.ini.
vale sync
# Install the repository's pre-commit and commit-message hooks.
prek install
# Install the tracked Prettier formatter and plugins used by CI.
npm ci
```

The virtual environment belongs at `.venv` in the repository root. Activate it
before changing into a subdirectory so commands don't need parent paths.

### Running the app

Run the Flask application in debug mode:

```shell
./tools/run_server.sh
```

Run the combined Flask and MCP ASGI application with reload support:

```shell
./tools/run_server.sh --asgi
```

The direct equivalents are `flask --app flask_htmx_template.web run` and
`uvicorn --factory flask_htmx_template.asgi:create_app --host 127.0.0.1 --port 5000`.

### Database and CLI

The console command accepts SQLite paths and PostgreSQL URLs through its
`--database` option. It provides `create`, `change-password`, `unlock`, and
`migrate` subcommands. Run `flask_htmx_template --help` for their arguments.

```shell
flask_htmx_template create
flask_htmx_template migrate
```

### API and MCP development

New databases receive an opaque API token stored as
`ConfigKey.API_BEARER_TOKEN`. Use it in an `Authorization: Bearer <token>`
header for JSON API and MCP requests. The Flask development server exposes the
HTML and JSON application only; start the ASGI server to expose `/mcp`.

Use `tools/mcp_connect.py` to inspect a running MCP server. Set `BEARER_TOKEN`
in the environment rather than placing the token in a command line.

### Database query time limits

Use `sql.time_limit()` inside an active SQLAlchemy session to bound a specific
query or group of queries:

```python
from sqlalchemy import text

from flask_htmx_template import sql

with database.begin_session() as session:
    with sql.time_limit(session, timeout_ms=2_000):
        result = session.execute(text("SELECT 1")).scalar_one()
```

Timeouts must be positive integers in milliseconds. SQLite limits are
approximate because they're checked between virtual-machine instruction
batches. PostgreSQL applies the limit to each statement in the context. A
PostgreSQL cancellation can leave the transaction aborted, so callers that
catch `TimeoutError` may need to roll it back. Unsupported database drivers
raise `TypeError`.

## Docker

### Docker image

The Dockerfile builds a wheel in a Python 3.12 build stage, then installs it in
a non-root runtime image. The runtime image stores SQLite data in `/data` and
exposes the application on port 8000 and Prometheus metrics on port 8001.

```shell
docker build --tag flask_htmx_template .
docker run --detach --name flask_htmx_template \
  --publish 8000:8000 --publish 8001:8001 \
  --volume flask_htmx_template-data:/data flask_htmx_template
```

At startup, the entrypoint creates a new database when needed, changes its web
password, runs migrations, and starts gunicorn with the ASGI application.

### Runtime configuration

| Variable           | Default             | Purpose                                   |
| ------------------ | ------------------- | ----------------------------------------- |
| `DB_PATH`          | `/data/database.db` | SQLite path or PostgreSQL URL             |
| `DB_WEB_KEY`       | `web-admin`         | Web password for a newly created database |
| `WEB_PORT`         | `8000`              | Application listener port                 |
| `WEB_PORT_METRICS` | `8001`              | Prometheus metrics listener port          |
| `WEB_CONCURRENCY`  | CPU count x 2 + 1   | gunicorn worker count                     |
| `WEB_N_THREADS`    | `1`                 | Threads per worker                        |
| `WEB_TIMEOUT`      | `30`                | gunicorn silent timeout, in seconds       |

### PostgreSQL deployment

Set `DB_PATH` to a `postgres://` or `postgresql://` URL. Optional SQLAlchemy
driver suffixes are supported. PostgreSQL connections use `sslmode=require`.
The database server must therefore provide TLS and an existing database for the
application user. The entrypoint creates the application's tables and applies
migrations; it doesn't create the PostgreSQL database itself.

Store passwords in your deployment platform's secret manager. Don't commit
database credentials, certificates, or private keys to this repository.

### CI image

GitHub Actions runs unit tests on Python 3.12 and 3.13. Static analysis uses
Python 3.13, and web formatting uses Node 24. Keep `package-lock.json` in sync
with `package.json` so CI uses the same Prettier build as local development.

## Language guidelines

### Python

Target Python 3.12. The project uses Ruff with all rules enabled, Black,
isort, and strict basedpyright checking. Follow nearby code for imports,
typing, exception handling, and SQLAlchemy patterns.

### Docstrings

Write docstrings for public Python modules, classes, and functions. Describe
arguments, returns, and raised exceptions when they're useful to callers.

### HTML and Jinja

Templates use the `.jinja` extension and are checked with djLint and Prettier.
Keep presentation logic in templates and request, database, and authorization
logic in Python controllers and context helpers.

### JavaScript and CSS

Source assets live under `flask_htmx_template/static/src/`. Rebuild Tailwind
while editing styles with `./tools/run_tailwindcss.sh`.

## Testing

Run the full test suite with `python -m pytest`. Coverage is branch-sensitive
and configured to require 100 percent:

```shell
python -m coverage run
python -m coverage report
```

Tests don't exercise browser interactions. Add focused pytest coverage for
server-side behavior, including migrations where a schema change is involved.

## Linters

Run every local code linter with:

```shell
./tools/linters.sh
```

This runs Ruff, djLint, codespell, and basedpyright. Vale checks prose files
through the pre-commit hook; run `vale readme.md dev.md AGENTS.md` when editing
documentation without invoking the hook.

## Formatters

Run every formatter with:

```shell
./tools/formatters.sh
```

This runs isort, Black, Prettier, and Taplo. Pre-commit hooks also enforce
formatting and checks for Python, Jinja, CSS, JavaScript, Markdown, TOML, and
YAML changes.

## Tools

- `tools/run_server.sh`: Start the Flask or combined ASGI development server.
- `tools/run_tailwindcss.sh`: Watch and optimize the Tailwind stylesheet.
- `tools/run_coverage.py`: Run isolated test targets and combine coverage.
- `tools/mcp_connect.py`: Call or inspect a running authenticated MCP server.
