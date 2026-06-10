from __future__ import annotations

import hashlib

from posejdon.domain.entities import SensitiveEntity


class GLiNERDetector:
    name = "gliner"

    def __init__(
        self,
        model_name: str = "urchade/gliner_small-v2.1",
        *,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.local_files_only = local_files_only
        self._model = None
        try:
            from gliner import GLiNER

            self._model = GLiNER.from_pretrained(
                model_name,
                local_files_only=local_files_only,
            )
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect(self, text: str, labels: list[str] | None = None) -> list[SensitiveEntity]:
        if self._model is None:
            return []
        try:
            predictions = self._model.predict_entities(text, labels=labels or [])
        except Exception:
            return []

        entities: list[SensitiveEntity] = []
        for item in predictions:
            raw = item["text"]
            start = int(item["start"])
            end = int(item["end"])
            digest = hashlib.sha1(
                f"gliner|{item['label']}|{start}|{end}|{raw}".encode(),
                usedforsecurity=False,
            ).hexdigest()[:12]
            entities.append(
                SensitiveEntity(
                    entity_id=f"ENT_{digest}",
                    entity_type=str(item["label"]).upper(),
                    raw_text=raw,
                    normalized_text=raw.strip(),
                    confidence=float(item.get("score", 0.65)),
                    source_detector=self.name,
                    start_offset=start,
                    end_offset=end,
                    metadata={"model_name": self.model_name},
                )
            )
        return entities
