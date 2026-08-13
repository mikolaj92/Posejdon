# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/Posejdon issue=38 -->

Repository: `mikolaj92/Posejdon`  
Issue: #38 — README kłamie, że current host pins to BOM v0.5.19

## Goal

Correct the README host BOM so it matches the current app-factory COMPAT row and Anonimizator3000 pins:

- `app-factory v0.6.5`
- `my-auth v0.4.2`
- `my-usermanager v0.5.4`

Point the COMPAT.md link at the `v0.6.5` tag, and lock the documented tags with the existing platform-boundary test.

## Files likely touched

- `README.md`
- `tests/test_platform_boundary.py`

## Test plan

- `uv run --extra dev pytest tests/test_platform_boundary.py`

## Non-goals

- Do not add platform packages to Posejdon `pyproject.toml` / `uv.lock`.
- Do not change anonymizer/runtime code.
- Do not bump Posejdon itself to consume the host BOM.

## Notes

- Closed #18 introduced the v0.5.19 table + tag-link test; later README edits collapsed that back to an inline stale pin.
- Verified live COMPAT.md latest row and `anonimizator3000` `tool.uv.sources` both pin v0.6.5 / v0.4.2 / v0.5.4.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
