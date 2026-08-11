from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from posejdon.anonymizer import TextAnonymizer
from posejdon.detectors.mention_memory import expand_person_mentions

CONNECTOR_CHARS = r"\w@._-"


def run_corpus_benchmark(corpus_path: str | Path) -> dict[str, Any]:
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    samples = corpus["samples"]
    recall_target = float(corpus.get("overall_recall_target", 0.99))
    anonymizer = TextAnonymizer()
    expected_by_type: dict[str, int] = defaultdict(int)
    predicted_by_type: dict[str, int] = defaultdict(int)
    true_positive_by_type: dict[str, int] = defaultdict(int)
    leakage_findings: list[dict[str, str]] = []

    for sample in samples:
        text = sample["text"]
        expected = sample["entities"]
        predicted = _detect_entities(anonymizer, text)
        matched_prediction_indexes: set[int] = set()

        for entity in expected:
            entity_type = entity["type"]
            expected_by_type[entity_type] += 1
            match_index = next(
                (
                    index
                    for index, prediction in enumerate(predicted)
                    if index not in matched_prediction_indexes
                    and prediction.entity_type == entity_type
                    and _surfaces_match(entity["text"], prediction.raw_text)
                ),
                None,
            )
            if match_index is not None:
                matched_prediction_indexes.add(match_index)
                true_positive_by_type[entity_type] += 1

        for prediction in predicted:
            predicted_by_type[prediction.entity_type] += 1

        anonymized = anonymizer.anonymize(text).text
        for entity in expected:
            surface = entity["text"]
            if _contains_surface(anonymized, surface) or _normalized_contains(
                anonymized, surface
            ):
                leakage_findings.append(
                    {
                        "sample_id": sample["id"],
                        "entity_type": entity["type"],
                        "surface": surface,
                    }
                )

    entity_types = sorted(set(expected_by_type) | set(predicted_by_type))
    per_type = {
        entity_type: _metrics(
            expected=expected_by_type[entity_type],
            predicted=predicted_by_type[entity_type],
            true_positive=true_positive_by_type[entity_type],
        )
        for entity_type in entity_types
    }
    overall = _metrics(
        expected=sum(expected_by_type.values()),
        predicted=sum(predicted_by_type.values()),
        true_positive=sum(true_positive_by_type.values()),
    )
    passed = overall["recall"] >= recall_target and not leakage_findings
    return {
        "benchmark_id": corpus["benchmark_id"],
        "sample_count": len(samples),
        "overall_recall_target": recall_target,
        "passed": passed,
        "overall": overall,
        "entity_types": per_type,
        "leakage": {
            "leaked_values_detected": bool(leakage_findings),
            "findings": leakage_findings,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Posejdon PII corpus benchmark.")
    parser.add_argument("--corpus", required=True, help="Path to labeled corpus JSON.")
    parser.add_argument("--output", default=None, help="Optional path for benchmark report JSON.")
    args = parser.parse_args(argv)

    report = run_corpus_benchmark(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(f"{text}\n", encoding="utf-8")
    print(text)
    return 0 if report["passed"] else 1


def _detect_entities(anonymizer: TextAnonymizer, text: str):
    # Detector failures propagate: a benchmark must never report coverage
    # measured with a silently reduced detector set.
    candidates = []
    for detector in anonymizer.detectors:
        candidates.extend(detector.detect(text))
    return expand_person_mentions(text, anonymizer.fusion.merge(candidates))


def _surfaces_match(expected: str, actual: str) -> bool:
    expected_normalized = _normalize_text(expected)
    actual_normalized = _normalize_text(actual)
    return expected_normalized in actual_normalized or actual_normalized in expected_normalized


def _contains_surface(text: str, surface: str) -> bool:
    cleaned = " ".join(surface.split())
    if not cleaned:
        return False
    pattern = r"\s+".join(re.escape(part) for part in cleaned.split(" "))
    return re.search(rf"(?<![{CONNECTOR_CHARS}]){pattern}(?![{CONNECTOR_CHARS}])", text) is not None


def _normalized_contains(text: str, surface: str) -> bool:
    cleaned = _normalize_text(surface)
    if not cleaned:
        return False
    pattern = r"\s+".join(re.escape(part) for part in cleaned.split(" "))
    return re.search(rf"(?<!\w){pattern}(?!\w)", _normalize_text(text)) is not None


def _normalize_text(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.casefold())


def _metrics(*, expected: int, predicted: int, true_positive: int) -> dict[str, float | int]:
    recall = true_positive / expected if expected else 1.0
    precision = true_positive / predicted if predicted else 1.0
    return {
        "expected": expected,
        "predicted": predicted,
        "true_positive": true_positive,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
    }


if __name__ == "__main__":
    raise SystemExit(main())
