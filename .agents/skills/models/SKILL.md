---
name: models
description: >
  SQLAlchemy ORM model definitions, active-record queries, sessions, validation,
  URI identifiers, and migrations for flask-htmx-template. Use when adding or
  editing models, model helpers, or schema changes.
---

## Model definitions

Inherit application models from `flask_htmx_template.models.base.Base` and use
the `ORM*` aliases for mapped columns:

```python
class Item(Base):
    __tablename__ = "item"
    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    value: ORMReal = orm.mapped_column(Decimal6, default=Decimal())
```

The base class assigns table identifiers in model-name order. Set
`__table_id__` to `0x00000000` for a persisted model and keep model table names
stable. Public object identifiers are encoded URIs: use `obj.uri`,
`Model.id_to_uri()`, and `Model.uri_to_id()` instead of exposing integer IDs in
URLs.

## Validation and constraints

Use `string_column_args()` in `__table_args__` for string length and whitespace
constraints. Add SQLAlchemy validation methods that delegate to
`Base.clean_strings()` and `Base.clean_decimals()` so assignments and database
loads use the same normalization rules. Keep database constraints for
invariants such as uniqueness; controllers can convert the resulting
`IntegrityError` or `InvalidORMValueError` into a user-facing response.

## Active-record queries

An active session must be bound before model methods run. Prefer the provided
query API over direct `session.query(Model)` calls:

```python
items = Item.all()
item = Item.one()
query = Item.query().where(Item.name == "foo").order_by(Item.date_ord)
```

Use `Item.create()`, `obj.delete()`, and `obj.refresh()` for writes and
refreshes. Use helpers in `flask_htmx_template.sql`, such as `sql.yield_()`,
`sql.scalar()`, `sql.one()`, `sql.any_()`, `sql.count()`, and `sql.to_dict()`.
For normal application code, open sessions with `web.db.begin_session()`.
Tests may bind a SQLAlchemy session with `Base.set_session()`.

## Transactions and migrations

Use nested transactions when a controller needs to catch a model or constraint
error without discarding the outer request session. Schema changes belong in a
new versioned module under `flask_htmx_template/migrations/`; migration
`upgrade()` methods use raw SQL and inherit from the previous migration. Add
focused migration tests and preserve compatibility with SQLite and PostgreSQL.

## Query and context boundaries

Models own persistence, validation, and reusable query logic. Resource
`controllers/<resource>/ctx.py` modules translate models into typed
`TypedDict` or `NamedTuple` contexts for HTML, JSON, and MCP consumers. Don't
put request parsing or template presentation logic in model classes.
