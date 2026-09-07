---
name: deploy
description: >
  Docker image, entrypoint, and gunicorn deployment conventions. Use when
  editing deployment files, container runtime configuration, or release checks.
---

## Deployment files

- `Dockerfile` builds a wheel in the `app-build` stage and installs it in the
  non-root `app` stage.
- `docker/entrypoint.sh` initializes or opens the configured database, updates
  the initial web password only for a newly created database, runs migrations,
  then starts gunicorn.
- `docker/gunicorn.conf.py` runs the combined ASGI application and starts the
  Prometheus metrics HTTP server.

## Runtime contract

The image stores SQLite data in `/data`, serves the application on port 8000,
and exposes Prometheus metrics on port 8001. PostgreSQL is supported by setting
`DB_PATH` to a PostgreSQL URL; the target database must already exist and
provide TLS.

| Variable           | Default             | Purpose                       |
| ------------------ | ------------------- | ----------------------------- |
| `DB_PATH`          | `/data/database.db` | SQLite path or PostgreSQL URL |
| `DB_WEB_KEY`       | `web-admin`         | Initial web password          |
| `WEB_PORT`         | `8000`              | Application listener port     |
| `WEB_PORT_METRICS` | `8001`              | Prometheus listener port      |
| `WEB_CONCURRENCY`  | CPU count x 2 + 1   | gunicorn workers              |
| `WEB_N_THREADS`    | `1`                 | Threads per worker            |
| `WEB_TIMEOUT`      | `30`                | gunicorn timeout in seconds   |

## Change guidance

- Keep database initialization and migration behavior safe for both a fresh
  SQLite file and an existing PostgreSQL database.
- Preserve the non-root runtime user and `/data` volume ownership.
- Keep `Dockerfile`, the entrypoint, `dev.md`, and deployment tests consistent
  when changing ports, environment variables, startup behavior, or image
  dependencies.
- Run focused deployment tests, then the relevant formatter and linter checks.
