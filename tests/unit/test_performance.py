"""Performance benchmarks for Posejdon hot paths."""

from __future__ import annotations

import time

import pytest

from posejdon.core.enums import PolicyProfileName, ReplacementKind
from posejdon.domain.artifacts import MappingVaultRecord, ProcessingMode
from posejdon.domain.entities import SensitiveEntity
from posejdon.domain.models import MetadataPolicy
from posejdon.domain.policies import OutputNamingRules, PolicyProfileDefinition
from posejdon.planners.replacement_planner import ReplacementPlanner
from posejdon.storage.vault import MappingVaultStore


@pytest.mark.benchmark
class TestPosejdonPerformance:
    """Performance regression tests for Posejdon anonymization pipeline."""

    def test_replacement_planner_completes_within_timeout(self) -> None:
        policy = PolicyProfileDefinition(
            name=PolicyProfileName.EXTERNAL_IRREVERSIBLE,
            entity_classes=["PERSON", "ADDRESS"],
            replacement_style=ReplacementKind.CATEGORY_PLACEHOLDER,
            output_naming=OutputNamingRules(suffix="_anonymized"),
            metadata_policy=MetadataPolicy(),
            llm_review_allowed=False,
            confidence_thresholds={"PERSON": 0.5, "ADDRESS": 0.5},
        )
        planner = ReplacementPlanner(policy=policy)

        entities = [
            SensitiveEntity(
                entity_id="e1", entity_type="PERSON", raw_text="John Doe",
                normalized_text="john doe", confidence=0.9, source_detector="regex",
            ),
            SensitiveEntity(
                entity_id="e2", entity_type="ADDRESS", raw_text="123 Main St",
                normalized_text="123 main st", confidence=0.9, source_detector="regex",
            ),
        ]

        timeout_seconds = 5.0
        start = time.perf_counter()
        result = planner.plan(entities=entities, document_kind="docx")
        elapsed = time.perf_counter() - start

        assert result is not None
        assert elapsed < timeout_seconds, (
            f"Replacement planning took {elapsed:.2f}s, exceeding {timeout_seconds}s timeout"
        )

    def test_vault_store_and_load_completes_within_timeout(self, tmp_path) -> None:
        vault_store = MappingVaultStore(root=str(tmp_path / "vault"))
        record = MappingVaultRecord(
            vault_id="doc1",
            mode=ProcessingMode.IRREVERSIBLE,
            input_artifact_id="input1",
            original_artifact_path="/tmp/original.docx",
            original_artifact_hash="abc123",
            output_artifact_path="/tmp/output.docx",
            output_artifact_hash="def456",
            report_path="/tmp/report.json",
            report_hash="ghi789",
            injector_export_path="/tmp/injector.json",
            injector_export_hash="jkl012",
            audit_id="audit1",
            created_at="2024-01-01T00:00:00Z",
            operator="test",
            policy_profile="default",
        )

        timeout_seconds = 1.0
        start = time.perf_counter()
        vault_store.save(record)
        retrieved = vault_store.load("doc1")
        elapsed = time.perf_counter() - start

        assert retrieved.vault_id == record.vault_id
        assert elapsed < timeout_seconds, (
            f"Vault operations took {elapsed:.2f}s, exceeding {timeout_seconds}s timeout"
        )
