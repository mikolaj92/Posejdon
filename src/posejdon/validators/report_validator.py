from __future__ import annotations

from posejdon.domain.reports import ProcessingReport


class ReportValidator:
    def validate(self, report: ProcessingReport) -> ProcessingReport:
        return ProcessingReport.model_validate(report.model_dump())
