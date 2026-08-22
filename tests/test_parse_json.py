import pytest

from app.agent import _parse_json_loose


def test_pure_json():
    text = '{"company": "TCS", "confidence": {"level": "high"}}'
    assert _parse_json_loose(text) == {"company": "TCS", "confidence": {"level": "high"}}


def test_markdown_fenced_json():
    text = 'Here is the forecast:\n```json\n{"company": "TCS"}\n```\nDone.'
    assert _parse_json_loose(text) == {"company": "TCS"}


def test_bare_fence():
    text = '```\n{"a": 1}\n```'
    assert _parse_json_loose(text) == {"a": 1}


def test_json_with_surrounding_prose():
    text = 'Sure! The answer is: {"a": [1, 2], "b": "x"} hope that helps.'
    assert _parse_json_loose(text) == {"a": [1, 2], "b": "x"}


def test_invalid_raises():
    with pytest.raises(ValueError):
        _parse_json_loose("no json here at all")
