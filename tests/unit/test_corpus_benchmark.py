from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from posejdon.anonymizer import TextAnonymizer
from posejdon.benchmarks import _detect_entities, run_corpus_benchmark
from posejdon.domain.entities import SensitiveEntity

CORPUS_PATH = Path("tests/fixtures/benchmarks/polish_pii_corpus.json")


def test_polish_pii_corpus_benchmark_passes_leakage_gate() -> None:
    report = run_corpus_benchmark(CORPUS_PATH)

    assert report["passed"] is True
    assert report["overall"]["recall"] >= report["overall_recall_target"]
    assert report["leakage"]["leaked_values_detected"] is False
    assert report["leakage"]["findings"] == []
    assert {"PERSON", "BANK_ACCOUNT", "VEHICLE_REGISTRATION"}.issubset(report["entity_types"])


def test_benchmark_detector_failure_is_not_silently_downgraded() -> None:
    class FailingDetector:
        def detect(self, text: str) -> list[SensitiveEntity]:
            raise RuntimeError("detector failed")

    anonymizer = TextAnonymizer()
    anonymizer.detectors.append(FailingDetector())

    with pytest.raises(RuntimeError, match="detector failed"):
        _detect_entities(anonymizer, "Jan Kowalski")


def test_polish_pii_corpus_benchmark_command_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmark-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "posejdon.benchmarks",
            "--corpus",
            str(CORPUS_PATH),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["leakage"]["findings"] == []
