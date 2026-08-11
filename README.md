# Posejdon

Text anonymization package.

Scope:

- Polish regex recognizers
- checksum validators for identifiers
- optional GLiNER recognizer

No document parsing. No web server. No queue.

## Host application boundary

Posejdon is an anonymization library. It intentionally does not provide a web server, FastAPI routes, HTML templates, `product_shell`, authentication/account/admin screens, or frontend assets. This section documents the package boundary only; it does not implement or complete the host UI work tracked in issue #16.

The host integration contract is:

- extend `app_factory/product_shell.html` for authenticated pages; keep domain content in host templates;
- serve Basecoat, HTMX, and Alpine from the app-factory same-origin `/static/platform/...` paths; do not add CDN or vendored chrome assets;
- install authentication and account/admin UI through `my-auth[fastapi-htmx]` and `my-usermanager`, rather than reimplementing those surfaces in Posejdon;
- keep HTMX state on the server: mutation routes return server-rendered HTML using the same partials as full-page responses, with stable `id`/`hx-target` pairs and explicit swaps;
- limit Alpine to component-local presentation state for toggles, menus, dialogs, and disclosures; do not put server data, business rules, or validation in Alpine stores;
- keep menus and dialogs keyboard accessible, including focus management, Escape handling, and accurate `aria-expanded`/`aria-controls` state;
- keep links and forms functional without JavaScript where practical; do not return JSON for client-side rendering of product or platform chrome;
- keep the platform BOM aligned with the app-factory COMPAT row: `app-factory v0.5.19`, `my-auth v0.3.23`, and `my-usermanager v0.4.5` (the current host integration pins).

The current FastAPI host is [Anonimizator3000](https://github.com/mikolaj92/anonimizator3000). Product shell, login, account, and admin behavior must be implemented and smoke-tested there. Posejdon remains host-agnostic: adding platform dependencies or an unconsumed `platform_ui` module here would create a second, non-functional integration.

Compatibility source: [app-factory COMPAT.md](https://github.com/mikolaj92/app-factory/blob/main/COMPAT.md).

## Usage

```python
from posejdon import TextAnonymizer

anonymizer = TextAnonymizer()
result = anonymizer.anonymize("Jan Kowalski PESEL 44051401359")

print(result.text)
print(result.findings)
```

## Optional GLiNER

```bash
uv sync --extra detectors
```

```python
from posejdon import TextAnonymizer

anonymizer = TextAnonymizer(gliner_enabled=True)
```

## Tests

```bash
uv run --extra dev pytest
```
