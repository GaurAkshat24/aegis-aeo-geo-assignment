"""
tests/test_fanout_parsing.py

Tests for JSON parsing and validation logic in the fan-out engine.
These tests mock the LLM call and validate the full parsing + validation pipeline.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.fanout_engine import (
    _extract_json,
    _validate_sub_queries,
    generate_sub_queries,
)


# ─── _extract_json ────────────────────────────────────────────────────────────

def test_extract_json_from_clean_object():
    raw = '{"sub_queries": []}'
    assert _extract_json(raw) == '{"sub_queries": []}'


def test_extract_json_strips_markdown_fences():
    raw = '```json\n{"sub_queries": []}\n```'
    extracted = _extract_json(raw)
    data = json.loads(extracted)
    assert "sub_queries" in data


def test_extract_json_strips_plain_fences():
    raw = '```\n{"sub_queries": []}\n```'
    extracted = _extract_json(raw)
    data = json.loads(extracted)
    assert "sub_queries" in data


def test_extract_json_handles_preamble():
    raw = 'Here are the sub-queries:\n{"sub_queries": []}'
    extracted = _extract_json(raw)
    data = json.loads(extracted)
    assert "sub_queries" in data


# ─── _validate_sub_queries ───────────────────────────────────────────────────

def _make_valid_sub_queries(n: int = 12) -> dict:
    types = ["comparative", "feature_specific", "use_case", "trust_signals", "how_to", "definitional"]
    items = []
    for i in range(n):
        items.append({"type": types[i % len(types)], "query": f"Test query number {i}"})
    return {"sub_queries": items}


def test_validate_accepts_valid_input():
    data = _make_valid_sub_queries(12)
    result = _validate_sub_queries(data)
    assert len(result) == 12
    for item in result:
        assert "type" in item
        assert "query" in item


def test_validate_rejects_non_dict_root():
    with pytest.raises(ValueError, match="Root element"):
        _validate_sub_queries([{"type": "comparative", "query": "x"}])


def test_validate_rejects_missing_sub_queries_key():
    with pytest.raises(ValueError, match="Missing or non-array"):
        _validate_sub_queries({"queries": []})


def test_validate_rejects_too_few_sub_queries():
    data = {"sub_queries": [{"type": "comparative", "query": "q"}] * 5}
    with pytest.raises(ValueError, match="Too few"):
        _validate_sub_queries(data)


def test_validate_rejects_invalid_type():
    data = {"sub_queries": [{"type": "invalid_type", "query": "x"}] * 10}
    with pytest.raises(ValueError, match="invalid type"):
        _validate_sub_queries(data)


def test_validate_rejects_empty_query():
    items = [{"type": "comparative", "query": "   "} for _ in range(10)]
    data = {"sub_queries": items}
    with pytest.raises(ValueError, match="empty or missing query"):
        _validate_sub_queries(data)


# ─── generate_sub_queries (mocked) ───────────────────────────────────────────

def _mock_gemini_response(content: str):
    """Create a mock Gemini response object."""
    mock_resp = MagicMock()
    mock_resp.text = content
    return mock_resp


def test_generate_sub_queries_success_gemini(monkeypatch):
    """Full success path: Gemini returns valid JSON — _call_gemini is mocked."""
    valid_data = _make_valid_sub_queries(12)

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    import app.services.fanout_engine as fe

    def fake_call_gemini(target_query, api_key, model_name, max_retries):
        return fe._validate_sub_queries(valid_data), model_name

    with patch.object(fe, "_call_gemini", side_effect=fake_call_gemini):
        sub_queries, model_used = generate_sub_queries("test query")
        assert len(sub_queries) >= 10
        assert all("type" in sq and "query" in sq for sq in sub_queries)
        assert model_used == "gemini-1.5-flash"


def test_generate_sub_queries_raises_on_no_api_key(monkeypatch):
    """Should raise RuntimeError when no API key is set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="No LLM API key"):
        generate_sub_queries("test query")


def test_generate_sub_queries_retries_on_bad_json(monkeypatch):
    """Should raise RuntimeError after all retries exhausted with bad JSON."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    import app.services.fanout_engine as fe

    call_count = {"n": 0}

    def always_fail(target_query, api_key, model_name, max_retries):
        call_count["n"] += max_retries
        raise RuntimeError("JSONDecodeError on attempt 3: ...")

    with patch.object(fe, "_call_gemini", side_effect=always_fail):
        with pytest.raises(RuntimeError):
            generate_sub_queries("bad query", max_retries=3)
