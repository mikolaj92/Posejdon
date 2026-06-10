"""Structured JSON logging baseline test for posejdon/."""

from __future__ import annotations

import io
import json
import logging


def test_import_and_emit_json() -> None:
    from posejdon.core.structured_logging import get_structured_logger

    logger = logging.getLogger("temida.test.posejdon")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(get_structured_logger("_").handlers[0].formatter)
    logger.handlers.clear()
    logger.addHandler(handler)

    logger.info("subsystem smoke")
    handler.flush()
    raw = stream.getvalue().strip()
    assert raw
    parsed = json.loads(raw)
    assert parsed["message"] == "subsystem smoke"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed
