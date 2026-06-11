from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from posejdon.domain.artifacts import AnonymizationAuditTrail, AuditRecord


class AuditStore:
    def __init__(self, root: str, secret: str = "posejdon") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = secret

    def save(self, record: AuditRecord) -> Path:
        path = self.root / f"{record.audit_id}.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, audit_id: str) -> AuditRecord:
        path = self.root / f"{audit_id}.json"
        return AuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save_trail(self, trail: AnonymizationAuditTrail) -> Path:
        trail_with_hash = self._compute_tamper_hash(trail)
        path = self.root / f"{trail_with_hash.audit_id}.json"
        path.write_text(trail_with_hash.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_trail(self, audit_id: str) -> AnonymizationAuditTrail:
        path = self.root / f"{audit_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        stored_hash = data.get("tamper_evidence_hash")
        if stored_hash is not None:
            payload = dict(data)
            payload.pop("tamper_evidence_hash", None)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            expected = hmac.new(
                self._secret.encode(), canonical.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(stored_hash, expected):
                raise ValueError(
                    f"Audit trail {audit_id} has been tampered with. Hash mismatch detected."
                )
        trail = AnonymizationAuditTrail.model_validate(data)
        return trail

    def _compute_tamper_hash(self, trail: AnonymizationAuditTrail) -> AnonymizationAuditTrail:
        payload = trail.model_dump()
        payload.pop("tamper_evidence_hash", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        hash_value = hmac.new(self._secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        return trail.model_copy(update={"tamper_evidence_hash": hash_value})

    def list_all(self) -> list[AuditRecord]:
        records = []
        for path in sorted(self.root.glob("AUD_*.json")):
            records.append(AuditRecord.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return records

    def compute_chain_hash(self, record: AuditRecord) -> str:
        data = record.model_dump()
        data.pop("audit_chain_hash", None)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_previous_audit_hash(self) -> str | None:
        records = self.list_all()
        if not records:
            return None
        latest = max(records, key=lambda r: r.created_at)
        return self.compute_chain_hash(latest)

    def verify_chain(self) -> list[tuple[str, bool]]:
        records = self.list_all()
        results = []
        for record in records:
            stored_hash = record.audit_chain_hash
            computed_hash = self.compute_chain_hash(record)
            results.append((record.audit_id, stored_hash == computed_hash))
        return results
