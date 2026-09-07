---
name: templates
description: >
  Jinja2, TailwindCSS, Material You, and HTMX template conventions for
  flask-htmx-template. Use when adding or editing `.jinja` templates or their
  server-rendered interactions.
---

## File and layout conventions

Templates use the `.jinja` extension under
`flask_htmx_template/templates/`. Keep reusable layout and controls in
`shared/`, and keep resource pages and fragments under a resource directory.
Content templates are standalone partials: `base.page()` supplies the shared
layout and `shared/base.jinja` provides the required `content` block.

## HTMX pages and dialog content

Use `url_for()` for every application URL. A page that refreshes after a
resource event can follow this pattern:

```jinja
<div
  hx-get="{{ url_for('items.page_all') }}"
  hx-trigger="item from:body"
  hx-target="#main"
>
  <h1>Items</h1>
</div>
```

Dialog content normally includes `shared/dialog-headline.jinja`, a form, a
`<div id="dialog-error" class="status-error"></div>`, and
`<script>dialog.onLoad();</script>`. Use `hx-target="#dialog"`,
`hx-swap="innerHTML show:#dialog:top"`, and `hx-push-url="#dialog"` for dialog
links. Use `hx-target="#main"`, an appropriate swap, and
`hx-push-url="true"` for navigable page updates.

## Design-system classes and icons

Use component classes such as `btn-filled`, `btn-tonal`, `btn-outlined`,
`btn-text`, `input-outlined`, and `status-error`. Use Material You color
utilities such as `bg-surface-container-high`, `text-on-surface`, and
`text-primary` rather than hard-coded colors. Use `<icon>name</icon>` for
Material Symbols.

Don't use `text-sm` or `text-xs`; the design system sets typography globally.
Use semantic elements such as headings, labels, and `<small>` instead.

## Fields, filters, and data

Outlined fields put the input, floating label, and helper or `<error>` target
inside the `input-outlined` label. Use the registered filters (`comma`, `qty`,
`input_value`, `percent`, `days`, `days_abv`, and `seconds`) for display
formatting. Pass structured data from a controller context; keep database and
authorization logic out of templates.

When embedding JSON in a script, use `{{ ctx | tojson }}` inside single quotes
and preserve the template formatter suppression around `JSON.parse()` when
needed. Use `onLoad(() => { ... })` for client behavior that runs after a
fragment loads.

## Formatting and validation

Templates are checked by djLint and Prettier with the Jinja plugin. Preserve
the repository's attribute ordering and HTMX targets, and use a narrow
`{# djlint: off #}` block only when a warning is intentional. Run the template
tests and formatters after changing markup.
