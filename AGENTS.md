# AGENTS.md

Non-negotiable guidance for humans and coding agents working in this repository.

## Composition

1. Prefer small Unix-style modules/processes and compose them.
2. Multi-step flows use Fala (Python/Mojo). Multiple Fala journals/runtimes are OK — not one global Fala.
3. Nested Fala is OK and preferred when a domain engine already ships its own Fala pipeline.
4. Domain engines stay domain-owned: Posejdon stays the anonymize/correlation engine. Do not re-implement orchestration as a fat god-file or second process engine inside Posejdon.
5. Posejdon is consumed by Temida/Argus via Fala packages (`host_run_package`); do not invent parallel orchestration.
