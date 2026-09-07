# flask-htmx-template

`flask-htmx-template` is a reusable Flask, SQLAlchemy, HTMX, and Tailwind CSS
application template.

## Quick reference

- Application source is in `flask_htmx_template/`; tests are in `tests/`.
- Skip generated and dependency directories such as `node_modules/`, `dist/`,
  and `.venv/` when searching.
- Read `dev.md` before changing code. It contains setup, test, Docker, and
  style instructions.
- Load the applicable task skill before editing controllers, models, Jinja
  templates, tests, CLI commands, or deployment files.
- Use ASCII hyphens and arrows in source and documentation. UTF-8 Greek letters
  are allowed.
- Activate `.venv` from the repository root before changing into a
  subdirectory. Don't use parent-directory paths in commands.

## Git

A developer may have edited files created in an earlier session. Their version
is preferred. Don't restore another version without asking first and
explaining why it's needed.

Never amend a commit. Create a new commit and let the developer manage history
and rebasing.

## After completing a task

1. Add `# NOTE:` comments for non-obvious source-code corner cases.
1. Update `dev.md` when a change affects developer workflow or conventions.
1. Update these instructions when a recurring agent workflow needs routing.
