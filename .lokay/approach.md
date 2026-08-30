# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/Posejdon issue=46 -->

Repository: `mikolaj92/Posejdon`  
Issue: #46 — [BUG] Leakage validator fail-closes on unmatched legal-role common nouns

## Goal

Product irreversible/reversible anonymize can fail closed with `Leakage detected for 1 values` after a successful render, when the leaked string is a legal-role common noun already present in the source (not a residual PERSON/EMAIL span).

## Files likely touched

- `src/posejdon/validators/leakage_validator.py`
- `tests/unit/test_text_validators.py`

## Test plan

- Synthetic fixture with a legal-role common noun does not trip `leaked_values_detected` when no EMAIL/NIP/KRS/PERSON-name residual exists.
- Residual EMAIL still fail-closes.
- Temida TAP ZGODA can be re-run after the pin bump.

## Non-goals

- Disabling leakage validation.
- Argus reviewing the original after Posejdon fails (#5183 already closed that).

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
