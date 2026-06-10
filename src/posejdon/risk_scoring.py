"""Re-identification risk scoring for anonymized documents.

Implements k-anonymity inspired metrics to assess anonymization strength.
Lower scores indicate better anonymization.
"""

from __future__ import annotations

from dataclasses import dataclass

from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.reports import ProcessingReport


@dataclass(frozen=True)
class RiskScore:
    overall_score: float
    risk_level: str
    entity_type_scores: dict[str, float]
    metrics: dict[str, object]


def calculate_reidentification_risk(
    report: ProcessingReport,
) -> RiskScore:
    entities = report.entities_found
    if not entities:
        return RiskScore(
            overall_score=0.0,
            risk_level="low",
            entity_type_scores={},
            metrics={"total_entities": 0, "unique_types": 0},
        )

    entity_types: dict[str, list[SensitiveEntity]] = {}
    for entity in entities:
        entity_types.setdefault(entity.entity_type, []).append(entity)

    entity_type_scores: dict[str, float] = {}
    total_risk = 0.0

    for entity_type, type_entities in entity_types.items():
        count = len(type_entities)
        unique_values = len({e.raw_text for e in type_entities})
        diversity_ratio = unique_values / count if count > 0 else 0.0

        if count == 1:
            type_risk = 1.0
        elif count <= 3:
            type_risk = 0.7
        elif diversity_ratio < 0.3:
            type_risk = 0.5
        elif diversity_ratio < 0.6:
            type_risk = 0.3
        else:
            type_risk = 0.1

        entity_type_scores[entity_type] = type_risk
        total_risk += type_risk

    overall_score = min(total_risk / len(entity_types), 1.0) if entity_types else 0.0

    if overall_score >= 0.7:
        risk_level = "high"
    elif overall_score >= 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"

    return RiskScore(
        overall_score=round(overall_score, 3),
        risk_level=risk_level,
        entity_type_scores=entity_type_scores,
        metrics={
            "total_entities": len(entities),
            "unique_types": len(entity_types),
            "entities_per_type": {
                t: len(e) for t, e in entity_types.items()
            },
        },
    )
