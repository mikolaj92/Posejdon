# Posejdon

Text anonymization package.

Scope:

- Polish regex recognizers
- checksum validators for identifiers
- optional GLiNER recognizer

No document parsing. No web server. No queue.

## Platform UI integration boundary

Posejdon is the anonymization library used by a host application. It intentionally does not provide a web server, FastAPI routes, HTML templates, `product_shell`, authentication/account/admin screens, or frontend assets. The platform UI acceptance criteria in issue #16 therefore belong to the host, not this package.

The host integration contract is:

- extend `app_factory/product_shell.html` for authenticated pages; keep domain content in host templates;
- serve Basecoat, HTMX, and Alpine from the app-factory same-origin `/static/platform/...` paths; do not add CDN or vendored chrome assets;
- install authentication and account/admin UI through `my-auth[fastapi-htmx]` and `my-usermanager`, rather than reimplementing those surfaces in Posejdon;
- keep the platform BOM aligned with the app-factory COMPAT row: `app-factory v0.5.19`, `my-auth v0.3.23`, and `my-usermanager v0.4.5` (the current host integration pins).

The current FastAPI host is [Anonimizator3000](https://github.com/mikolaj92/anonimizator3000). Its shell, login, account, and admin smoke checks are the correct place to verify issue #16. Posejdon must remain host-agnostic: adding platform dependencies or an unconsumed `platform_ui` module here would create a second, non-functional integration instead of satisfying the contract.

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
