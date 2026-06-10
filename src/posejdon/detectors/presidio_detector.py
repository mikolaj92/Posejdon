from __future__ import annotations

import hashlib
import importlib.util

from posejdon.domain.entities import SensitiveEntity


class PresidioDetector:
    name = "presidio"

    def __init__(self, language: str = "pl") -> None:
        self.language = language
        self._engine = None
        if importlib.util.find_spec("pip") is None:
            return
        try:
            from presidio_analyzer import AnalyzerEngine

            self._engine = AnalyzerEngine()
        except BaseException:
            self._engine = None

    @property
    def available(self) -> bool:
        return self._engine is not None

    def detect(self, text: str) -> list[SensitiveEntity]:
        if self._engine is None:
            return []
        try:
            results = self._engine.analyze(text=text, language=self.language)
        except BaseException:
            return []

        entities: list[SensitiveEntity] = []
        for result in results:
            raw = text[result.start : result.end]
            digest = hashlib.sha1(
                f"presidio|{result.entity_type}|{result.start}|{result.end}|{raw}".encode(),
                usedforsecurity=False,
            ).hexdigest()[:12]
            entities.append(
                SensitiveEntity(
                    entity_id=f"ENT_{digest}",
                    entity_type=result.entity_type.upper(),
                    raw_text=raw,
                    normalized_text=raw.strip(),
                    confidence=float(result.score),
                    source_detector=self.name,
                    start_offset=result.start,
                    end_offset=result.end,
                    metadata={"language": self.language},
                )
            )
        return entities
