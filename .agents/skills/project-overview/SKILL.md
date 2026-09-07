---
name: project-overview
description: >
  flask-htmx-template structure, technology, and navigation. Load at the start
  of any task in this repository or when exploring unfamiliar components.
---

## Purpose

flask-htmx-template is a reusable Flask application template built with
SQLAlchemy, HTMX, Tailwind CSS, and Docker. The example Item feature demonstrates
the application's HTML, JSON API, and MCP patterns.

## Project structure

```
flask_htmx_template/
  commands/         # CLI subcommands
  controllers/      # HTML, JSON, and MCP request handlers by feature
  migrations/       # Versioned schema migrations
  models/           # SQLAlchemy ORM models and shared helpers
  static/src/       # Tailwind CSS and JavaScript source
  templates/        # Jinja templates, shared components, and feature views
  asgi.py           # Combined Flask and MCP ASGI app factory
  database.py       # SQLite and PostgreSQL database abstraction
  main.py           # CLI entry point
  sql.py            # SQL session and query helpers
  web.py            # Flask application factory and extensions
docker/             # Image entrypoint and Gunicorn configuration
tests/              # Pytest suite mirroring the source layout
tools/              # Development, formatting, linting, and server scripts
```

## Working conventions

- Read `dev.md` before changing code. It covers setup, tests, formatting, and
  Docker behavior.
- Load the skill for the component being changed before editing it.
- Skip generated and dependency directories, including `node_modules/`,
  `dist/`, and `.venv/`, during searches.
- Activate `.venv` from the repository root before changing to a subdirectory.
- Use ASCII hyphens and arrows in source and documentation. UTF-8 Greek letters
  are allowed.

## After completing a task

1. Add `# NOTE:` comments for non-obvious source-code corner cases.
1. Update `dev.md` when developer workflow or conventions change.
1. Update `AGENTS.md` or a relevant skill when a recurring agent workflow needs
   routing.
