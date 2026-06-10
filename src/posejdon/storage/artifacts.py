from __future__ import annotations

import shutil
from pathlib import Path


class ArtifactStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.originals = self.root / "originals"
        self.anonymized = self.root / "anonymized"
        self.reinjected = self.root / "reinjected"
        self.restored = self.root / "restored"
        self.reports = self.root / "reports"
        self.reinjection_reports = self.root / "reinjection_reports"
        self.restore_reports = self.root / "restore_reports"
        self.vaults = self.root / "vaults"
        self.temp = self.root / "temp"
        for directory in [
            self.originals,
            self.anonymized,
            self.reinjected,
            self.restored,
            self.reports,
            self.reinjection_reports,
            self.restore_reports,
            self.vaults,
            self.temp,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def stage_original(self, source_path: str, artifact_id: str) -> Path:
        destination = self.originals / f"{artifact_id}{Path(source_path).suffix}"
        shutil.copy2(source_path, destination)
        return destination

    def allocate_output_path(self, artifact_id: str, suffix: str) -> Path:
        return self.anonymized / f"{artifact_id}{suffix}"

    def allocate_reinjected_output_path(self, artifact_id: str, suffix: str) -> Path:
        return self.reinjected / f"{artifact_id}{suffix}"

    def allocate_report_path(self, report_id: str) -> Path:
        return self.reports / f"{report_id}.json"

    def allocate_reinjection_report_path(self, report_id: str) -> Path:
        return self.reinjection_reports / f"{report_id}.json"

    def allocate_injector_export_path(self, report_id: str) -> Path:
        return self.reports / f"{report_id}.injector.json"

    def allocate_mapping_vault_path(self, vault_id: str) -> Path:
        return self.vaults / f"{vault_id}.json"

    def allocate_restore_output_path(self, artifact_id: str, suffix: str) -> Path:
        return self.restored / f"{artifact_id}{suffix}"

    def allocate_restore_report_path(self, restore_id: str) -> Path:
        return self.restore_reports / f"{restore_id}.json"

    def allocate_temp_path(self, file_name: str) -> Path:
        return self.temp / file_name
