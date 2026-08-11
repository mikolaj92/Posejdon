import pytest

from posejdon.detectors.gliner_detector import _DEFAULT_LABELS, GLiNERDetector


class _FakeModel:
    """Stand-in for a loaded GLiNER model so tests stay offline and fast."""

    def __init__(self, predictions):
        self._predictions = predictions
        self.calls: list[list[str]] = []

    def predict_entities(self, text, labels):
        self.calls.append(labels)
        return self._predictions


def _detector_with(model, *, threshold=0.45) -> GLiNERDetector:
    detector = GLiNERDetector.__new__(GLiNERDetector)
    detector.name = "gliner"
    detector.model_name = "fake"
    detector.local_files_only = True
    detector.threshold = threshold
    detector._model = model
    return detector


def test_detect_prompts_default_labels_when_caller_gives_none():
    model = _FakeModel([])
    detector = _detector_with(model)

    detector.detect("Kwiaciarnia Różyczka w Krakowie")

    assert model.calls == [list(_DEFAULT_LABELS)]


def test_detect_maps_gliner_label_to_canonical_entity_type():
    model = _FakeModel(
        [
            {
                "text": "Kwiaciarnia Różyczka",
                "label": "organization",
                "start": 0,
                "end": 20,
                "score": 0.9,
            },
            {"text": "Krakowie", "label": "location", "start": 24, "end": 32, "score": 0.9},
        ]
    )
    detector = _detector_with(model)

    entities = detector.detect("Kwiaciarnia Różyczka w Krakowie")

    assert [e.entity_type for e in entities] == ["ORG", "CITY"]


def test_detect_propagates_model_failure():
    class _FailingModel:
        def predict_entities(self, text, labels):
            raise RuntimeError("inference failed")

    detector = _detector_with(_FailingModel())

    with pytest.raises(RuntimeError, match="inference failed"):
        detector.detect("Anna")


def test_detect_drops_predictions_below_threshold():
    model = _FakeModel(
        [{"text": "Anna", "label": "person", "start": 0, "end": 4, "score": 0.3}]
    )
    detector = _detector_with(model, threshold=0.45)

    assert detector.detect("Anna") == []
