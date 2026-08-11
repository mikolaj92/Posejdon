# Fallback inventory

Issue #31 audited compatibility, legacy, shim, and degraded-execution paths in the
runtime package. This inventory records the decision for each path so accidental
fallbacks are not reintroduced.

| Symbol/path | Previous behavior | Decision |
| --- | --- | --- |
| `TextAnonymizer.__init__`: implicit Presidio detector | Attempted to construct an undeclared optional integration and silently continued on every error. | **Delete.** Presidio is neither a declared extra nor part of the documented `TextAnonymizer` contract. Regex remains the explicit default. |
| `TextAnonymizer.__init__`: enabled GLiNER initialization | Silently continued with regex only when explicitly requested GLiNER could not initialize. | **Promote.** `gliner_enabled=True` is an explicit feature and now fails clearly when unavailable. |
| `TextAnonymizer.anonymize`: detector execution | Silently omitted any detector that raised. | **Delete.** Detector failures now propagate rather than producing output with undisclosed reduced coverage. |
| `GLiNERDetector._load_model`: local-cache retry | Tries local model files first, then downloads the public model once. | **Promote.** This is documented Optional GLiNER behavior; initialization has an explicit availability check at the facade boundary. |
| `GLiNERDetector.detect`: inference failure | Returned no findings on any model error. | **Delete.** Inference errors now propagate. An empty result means successful inference found nothing. |
| `benchmarks._detect_entities`: benchmark detector execution | Silently omitted any detector that raised, so a benchmark could report coverage measured with a reduced detector set. | **Delete.** Detector failures now propagate, matching the facade: benchmark results never silently reflect reduced detector coverage. |
| `SpacyDetector` unavailable/model failure no-op | Returns no findings if the optional model is absent or inference fails. | **Retain outside the facade.** It remains a directly instantiated optional detector whose standalone contract is a no-op on unavailable model or inference failure, documented by tests. It is not silently installed by `TextAnonymizer`. |
| `PresidioDetector` unavailable/analyzer failure no-op | Returns no findings when its independently used optional engine is unavailable or fails. | **Retain outside the facade.** It is no longer an implicit super-fallback. Promoting its standalone API requires a separately scoped dependency/API decision. |
| `MLXProvider` missing configuration/runtime or invalid response | Historically returned empty review/verification results. | **Already promoted by issue #30.** These paths raise or report explicit unavailability and are covered by fail-closed tests. |
| Reinjection fuzzy matching (`enable_fuzzy`) | Optional bounded lookup when exact segment identity is unavailable. | **Retain as explicit feature.** It is opt-in by parameter and reports conflicts instead of silently changing processing mode. |

Normal optional-value branches, validation outcomes, overlap resolution, and parsing
misses are not compatibility fallbacks and are outside this inventory.
