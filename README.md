# Posejdon

Text anonymization package.

Scope:

- Polish regex recognizers
- checksum validators for identifiers
- optional GLiNER recognizer

No document parsing. No web server. No queue.

Leakage and structural checks take host-supplied text segments or stdlib
DOCX zip snapshots. DOCX / JSON / XML / PDF parsers live in the host
(`posejdon-docs` / Docxtor), not in this wheel.

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
- keep the platform BOM aligned with the app-factory COMPAT row.

The current host BOM (Anonimizator3000):

| Component | Production host tag |
| --- | --- |
| app-factory | [`v0.6.11`](https://github.com/mikolaj92/app-factory/releases/tag/v0.6.11) |
| my-auth | [`v0.4.6`](https://github.com/mikolaj92/my-auth/releases/tag/v0.4.6) |
| my-usermanager | [`v0.5.8`](https://github.com/mikolaj92/my-usermanager/releases/tag/v0.5.8) |

These are the three tags pinned by Anonimizator3000. Posejdon has no platform dependency or source entry, so its `pyproject.toml` and `uv.lock` intentionally contain none of these packages; adding host pins here would violate the package boundary.

The current FastAPI host is [Anonimizator3000](https://github.com/mikolaj92/anonimizator3000). Product shell, login, account, and admin behavior must be implemented and smoke-tested there. Posejdon remains host-agnostic: adding platform dependencies or an unconsumed `platform_ui` module here would create a second, non-functional integration.

Compatibility source: [app-factory COMPAT.md](https://github.com/mikolaj92/app-factory/blob/main/COMPAT.md). Latest COMPAT row: app-factory `v0.6.12` / my-auth `v0.4.6` / my-usermanager `v0.5.8`.

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

`PosejdonSettings` defaults to `enable_gliner=false` and `enable_spacy=false`.
Set `POSEJDON_ENABLE_GLINER=true` or `POSEJDON_ENABLE_SPACY=true` to enable
that settings flag. These flags do not configure `TextAnonymizer`: GLiNER
requires `gliner_enabled=True`, and spaCy is not connected to the facade.
The facade uses regex by default; it does not invoke Presidio or LLM review.

LLM prompt YAML ships inside the wheel (`posejdon/prompts/`). The registry
loads it via `importlib.resources`; it does not search CWD. Override the
search root with `POSEJDON_PROMPT_ROOT` or `PosejdonPromptRegistry(root)`.
A missing prompt raises `FileNotFoundError`.

## Host-supplied LLM interface

Hosts that implement LLM review use `LocalLLMProvider` from
`posejdon.detectors.llm_review`. The protocol exposes `probe_availability`,
`provider_id`, `runtime_model_id`, `review`, and `verify_anonymization`.
Posejdon supplies structured response models, not a concrete LLM client.
`TextAnonymizer` does not accept or invoke this provider.

The host owns runtime, transport, client construction, response validation,
and invocation. It must check provider readiness before requests. Unavailability
must be reported explicitly; review and verification failures must raise instead of
returning empty success responses or switching clients. Settings such as
`llm_provider` and `llm_model` do not construct a client in this package.
The embedded MLX runtime was removed in issue #65. Do not restore its imports,
compatibility aliases, or automatic fallbacks.

## Fallback policy

Runtime compatibility and degraded-execution paths are recorded in
[`docs/fallback-inventory.md`](docs/fallback-inventory.md). Explicitly enabled detectors fail
clearly when unavailable; Posejdon does not silently claim success with reduced detector coverage.

## Dependency audit

Audited source: `c121fef9835ad30ac7fcd26d876eabac51d564c7` on `lokay/82`.
The table describes the resulting `uv.lock` after raising spaCy's minimum to
3.8.16. Only `pyproject.toml`, `uv.lock`, and `.github/workflows/test.yml` are
active dependency/CI inputs in this checkout. Host BOM tags above are not wheel
requirements.

**Confirmed audited remnants: 2 distinct packages** (`httpx`, `spacy-legacy`),
not a security finding or a claim that the entire tree is legacy-free.
Base installation: 0 of these packages. `detectors`: `httpx`.
`spacy`: both. There is no `llm` extra, `openai`, or `httpx2` in this lock;
`uv export --locked --extra llm` fails rather than proving an LLM installation.
The host-supplied LLM protocol remains available without an SDK dependency.

All paths below start at Posejdon 0.2.3. Metadata evidence is the exact-version
PyPI JSON `info.requires_dist`, cross-checked against the lock and reverse tree.

| Package/version | Extra | Full parent path(s) after Posejdon | Evidence | Decision | Next step / acceptance |
| --- | --- | --- | --- | --- | --- |
| httpx 0.28.1 | detectors | gliner 0.2.26 → huggingface-hub 1.16.1 → httpx; gliner 0.2.26 → transformers 5.1.0 → huggingface-hub 1.16.1 → httpx; gliner 0.2.26 → transformers 5.1.0 → tokenizers 0.22.2 → huggingface-hub 1.16.1 → httpx | [GLiNER](https://pypi.org/pypi/gliner/0.2.26/json), [Transformers](https://pypi.org/pypi/transformers/5.1.0/json), [tokenizers](https://pypi.org/pypi/tokenizers/0.22.2/json), [Hub](https://pypi.org/pypi/huggingface-hub/1.16.1/json) | Keep: Hub requires `httpx>=0.23.0,<1`; deleting it breaks model transport. | Hub [2.2.0](https://pypi.org/pypi/huggingface-hub/2.2.0/json) exists and requires `httpx2>=2,<3`, but Transformers and tokenizers require Hub `<2`: blocked for this graph. First select GLiNER-compatible Transformers/tokenizers whose exact metadata permits Hub 2; regenerate with uv and pass live GLiNER regression without skips. No compatible target pair established. |
| httpx 0.28.1 | spacy | spacy 3.8.16 → weasel 1.0.0 → httpx | [spaCy](https://pypi.org/pypi/spacy/3.8.16/json), [weasel](https://pypi.org/pypi/weasel/1.0.0/json) | Keep: weasel requires `httpx>=0.24.0`. Updating Hub alone cannot remove this path. | Check a future spaCy-compatible weasel release for removal/replacement of httpx before choosing a version; regenerate and verify spaCy import, Polish model loading and detection. No replacement release verified. |
| spacy-legacy 3.0.12 | spacy | spacy 3.8.16 → spacy-legacy | [spaCy](https://pypi.org/pypi/spacy/3.8.16/json), [legacy](https://pypi.org/pypi/spacy-legacy/3.0.12/json) | Keep: spaCy explicitly requires `>=3.0.11,<3.1.0` for compatibility registrations. | Check the next spaCy release's metadata; upgrade only when legacy is no longer required, then verify existing Polish model configurations and detector regression. 3.8.16 still requires it: removal blocked. |

### Correction and reproducibility

spaCy 3.8.14 installed successfully and existing tests passed, but an actual
`import spacy` failed with `ModuleNotFoundError: click`. The locked Typer 0.26.7
no longer supplies Click. Verified spaCy 3.8.16 metadata adds
`click>=8.2.1,<9.0.0`; its published wheels cover CPython 3.12/3.13 on macOS
ARM64 and Linux x86_64. Raising the direct spaCy minimum fixes that missing
requirement without pinning a transitive package. `uv lock` regenerated the
lock (spaCy 3.8.16 and Click 8.4.2). Optional detectors and the LLM protocol
are unchanged. CI now checks the lock and uses `--locked`, so it cannot silently
repair inconsistent inputs during checks.

Before the correction, `uv lock --check` passed. With uv 0.11.20,
`uv tree --locked --all-extras` fails with an unsupported-option error;
`uv tree --locked --no-dev` already shows every optional path. Use exports to
select extras rather than treating that combined tree as a base installation:

```bash
uv lock --check
uv tree --locked --no-dev --universal
uv tree --locked --no-dev --invert --package httpx
uv tree --locked --no-dev --invert --package spacy-legacy
uv export --locked --no-dev --no-emit-project --format requirements.txt
uv export --locked --no-dev --no-emit-project --extra detectors
uv export --locked --no-dev --no-emit-project --extra spacy
# Repeat for Python 3.12 and 3.13, on each target platform:
uv tree --locked --no-dev --python-version 3.12 --python-platform aarch64-apple-darwin
uv tree --locked --no-dev --python-version 3.13 --python-platform x86_64-unknown-linux-gnu
uv tree --locked --no-dev --python-version 3.13 --python-platform x86_64-pc-windows-msvc
```

The audited edges have no Python/platform exclusion within Posejdon's
`>=3.12,<3.14` range. Matrix trees were checked for both versions on all three
platforms above; they predict resolution, not successful installation there.
Other edges do have markers (for example Hub's `hf-xet` architecture list and
Torch's Linux-only NVIDIA packages). Exports preserve those markers; the
universal lock is not the list of packages installed on macOS.

Validation used fresh environments inside this checkout, not the old `.venv`,
on macOS ARM64 / CPython 3.12.13:

- Base + dev: full suite **213 passed, 1 skipped** (live GLiNER absent); Ruff passed.
- `detectors` + dev: full suite **214 passed, 0 skipped**, including live model regression.
- `spacy` + dev: full suite **213 passed, 1 skipped** (GLiNER absent).
  Actual spaCy import and `spacy.blank('pl')` + entity-ruler detection passed.
  This does not establish trained Polish model accuracy.
- No tests were added or changed. No LLM SDK installation is claimed.

Run suites with `uv run --locked --extra dev pytest` and Ruff with
`uv run --locked --extra dev ruff check .`; add each detector extra separately.
Use a fresh `UV_PROJECT_ENVIRONMENT`, and keep `UV_CACHE_DIR`,
`UV_PYTHON_INSTALL_DIR`, and `HF_HOME` inside the checkout when reproducing.
The checked-in CI job `test` runs `uv lock --check`,
`uv run --locked --group dev pytest`, and `uv run --locked --group dev ruff check .`.
Local execution of these commands is not remote CI success.
Unauthenticated GitHub branch-protection and effective branch-rules requests
both returned HTTP 403. Required external checks and final-SHA remote results
are therefore **unconfirmed**; the audit does not close that acceptance gate.

## Tests

```bash
uv run --group dev pytest
uv run --group dev ruff check .
```
