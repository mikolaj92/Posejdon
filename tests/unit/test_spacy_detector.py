from posejdon.detectors.fusion import DetectorFusion
from posejdon.detectors.spacy_detector import SpacyDetector


def test_spacy_detector_degrades_gracefully_without_model() -> None:
    detector = SpacyDetector(model_name="__definitely_not_a_real_spacy_model__")
    assert detector.name == "spacy"
    assert detector.available is False
    # When the model cannot be loaded, detection is a no-op rather than an error.
    assert detector.detect("Jan Kowalski podpisał umowę.") == []


def test_fusion_prefers_spacy_below_core_detectors() -> None:
    order = DetectorFusion().prefer_detectors
    assert "spacy" in order
    # spaCy is a fallback NER source: ranked after regex/presidio/gliner.
    assert order.index("spacy") > order.index("gliner")
    assert order.index("spacy") > order.index("regex")
