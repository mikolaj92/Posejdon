from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from posejdon.core.errors import VaultIntegrityError
from posejdon.domain.artifacts import MappingVaultRecord


class MappingVaultStore:
    def __init__(self, root: str, hmac_key: str) -> None:
        if not hmac_key:
            raise ValueError("Vault hmac_key must be provided.")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self._hmac_key = hmac_key.encode("utf-8")

    def save(self, record: MappingVaultRecord) -> Path:
        path = self.root / f"{record.vault_id}.json"
        payload = record.model_dump(mode="json")
        payload.pop("vault_hmac", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        record.vault_hmac = hmac.new(
            self._hmac_key,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def load(self, vault_id: str) -> MappingVaultRecord:
        path = self.root / f"{vault_id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        stored_hmac = raw.pop("vault_hmac", None)
        if not stored_hmac:
            raise VaultIntegrityError(
                f"Vault {vault_id} is missing vault_hmac: unsigned vaults are not accepted."
            )
        record = MappingVaultRecord.model_validate(raw)
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        computed = hmac.new(
            self._hmac_key,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(stored_hmac, computed):
            raise VaultIntegrityError(
                f"Vault {vault_id} HMAC mismatch: vault may have been tampered."
            )
        if record.expires_at is not None:
            expires = datetime.fromisoformat(record.expires_at)
            if datetime.now(UTC) > expires:
                raise VaultIntegrityError(
                    f"Vault {vault_id} has expired (retention deadline passed)."
                )
        return record

    def path_for(self, vault_id: str) -> Path:
        return self.root / f"{vault_id}.json"

    def delete(self, vault_id: str) -> Path:
        path = self.path_for(vault_id)
        path.unlink(missing_ok=True)
        return path
