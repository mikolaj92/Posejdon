"""Mapping vault integrity: HMAC is mandatory; no unsigned-vault load path."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from posejdon.core.enums import ProcessingMode
from posejdon.core.errors import VaultIntegrityError
from posejdon.domain.artifacts import MappingVaultRecord
from posejdon.storage.vault import MappingVaultStore


def _record(vault_id: str = "VAULT_001") -> MappingVaultRecord:
    return MappingVaultRecord(
        vault_id=vault_id,
        mode=ProcessingMode.REVERSIBLE,
        input_artifact_id="abc",
        original_artifact_path="/tmp/original.docx",
        original_artifact_hash="hash1",
        output_artifact_path="/tmp/output.docx",
        output_artifact_hash="hash2",
        report_path="/tmp/report.json",
        report_hash="hash3",
        injector_export_path="/tmp/export.json",
        injector_export_hash="hash4",
        audit_id="AUD_001",
        created_at=datetime.now(UTC).isoformat(),
        operator="system",
        policy_profile="external_irreversible",
    )


def test_vault_load_fails_when_hmac_missing(tmp_path: Path) -> None:
    store = MappingVaultStore(str(tmp_path / "vaults"), hmac_key="secret-key")
    path = store.path_for("VAULT_UNSIGNED")
    path.write_text(_record("VAULT_UNSIGNED").model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(VaultIntegrityError, match="missing vault_hmac"):
        store.load("VAULT_UNSIGNED")


def test_vault_round_trip_with_hmac(tmp_path: Path) -> None:
    store = MappingVaultStore(str(tmp_path / "vaults"), hmac_key="secret-key")
    store.save(_record("VAULT_OK"))
    loaded = store.load("VAULT_OK")
    assert loaded.vault_id == "VAULT_OK"
