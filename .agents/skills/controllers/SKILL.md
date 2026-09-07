---
name: controllers
description: >
  Flask controller structure, route registration, database sessions, JSON API
  responses, and HTMX interactions for flask-htmx-template. Use when adding or
  editing controller modules and routes.
---

## Controller layout

- `flask_htmx_template/controllers/base.py` contains shared response, parsing,
  pagination, and context helpers.
- Put resource code in `controllers/<resource>/` and keep request context
  builders in `ctx.py`.
- Put browser routes in `html.py`, JSON routes in `json.py`, and database MCP
  tools in `mcp.py` when a resource needs them.
- Register each module's routes in a `ROUTES` mapping and set `ROUTE_PREFIX`.
  `web.FlaskExtension._add_routes()` derives endpoint names from these values.

## Route conventions

Use resource paths for full pages, `/h/` for HTMX fragments and mutations, and
`/j/` for JSON endpoints. A typical resource route table is:

```python
ROUTE_PREFIX = "items"
ROUTES: base.Routes = {
    "/items": (page_all, ["GET"]),
    "/h/items/new": (new, ["GET", "POST"]),
    "/j/items": (json_all, ["GET"]),
}
```

Keep view functions small: parse request data, open the database session, call
context or model helpers, and return a response. Add public docstrings that
describe arguments, return values, and invalid-input errors.

## Sessions and mutations

Open a session with `web.db.begin_session()` around every database operation.
Use `session.begin_nested()` around a mutation whose validation or uniqueness
failure should return an error while leaving the outer session usable:

```python
with web.db.begin_session() as session:
    try:
        with session.begin_nested():
            Item.create(name=form["name"], date_ord=today.toordinal())
    except (exc.IntegrityError, exc.InvalidORMValueError) as error:
        return base.error(error)
```

Use `base.find(Model, uri)` for public model URIs. Keep authorization and
request policy in controller helpers rather than templates.

## HTML and JSON responses

Full pages use `base.page()` so the shared layout wraps a standalone content
template. HTMX dialog content generally renders a fragment on GET and returns
`base.dialog_swap(event=..., snackbar=...)` after a successful mutation.
Validation failures should use `base.error()` for HTML and an
`{"errors": [...]}` response with an appropriate HTTP status for JSON.

Parse JSON query arguments and bodies through `controllers.json_api` and return
typed context dictionaries. JSON resource handlers should use the same context
builders as HTML handlers so both interfaces expose the same data contract.

## Authentication and exemptions

The application applies the default login requirement before requests. Mark
health, theme, or other intentionally public handlers with
`@auth_ctx.login_exempt`. Keep route registration in the module `ROUTES` map so
the application factory remains the single place that installs routes.
