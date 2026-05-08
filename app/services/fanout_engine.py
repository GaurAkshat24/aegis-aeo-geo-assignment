"""
fanout_engine.py

Calls an LLM (Gemini 1.5 Flash via google-generativeai) to decompose a
user query into 10-15 sub-queries across 6 types.

Prompt design choices:
  - JSON schema embedded in the system prompt with a concrete example.
  - Explicit constraint: at least 2 from each type, no extra fields.
  - Model is instructed to return ONLY the JSON object — no markdown fences.
  - Response is parsed + validated with Pydantic; bad output triggers retries.
  - Up to 3 retries with increasing temperature to escape degenerate outputs.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_VALID_TYPES = {
    "comparative",
    "feature_specific",
    "use_case",
    "trust_signals",
    "how_to",
    "definitional",
}

_SYSTEM_PROMPT = """\
You are an AI search engine analyst. Your job is to decompose a user-provided \
query into 10–15 diverse sub-queries that simulate how an AI answer engine \
(e.g. Perplexity, Google AI Mode) would break it apart to build a comprehensive answer.

REQUIRED OUTPUT FORMAT
Return ONLY a valid JSON object — no markdown, no commentary, no code fences.
The JSON must have exactly one key: "sub_queries", whose value is an array of objects.
Each object must have exactly two keys: "type" (string) and "query" (string).

REQUIRED SUB-QUERY TYPES (at least 2 from each):
  - comparative      : How the topic compares to alternatives
  - feature_specific : A specific capability or attribute of the topic
  - use_case         : A real-world application or scenario
  - trust_signals    : Reviews, case studies, credibility, social proof
  - how_to           : Step-by-step or procedural questions
  - definitional     : Conceptual or "what is" questions

RULES
  1. Generate between 10 and 15 sub-queries total.
  2. At least 2 sub-queries per type listed above.
  3. The "type" field must be one of the six values above — no other values.
  4. Do NOT include any field other than "type" and "query".
  5. Sub-queries must be natural search queries, not sentences.
  6. Sub-queries must be relevant to the exact topic provided — not generic.

EXAMPLE (for target_query = "best project management software for startups"):
{
  "sub_queries": [
    {"type": "comparative",      "query": "Asana vs Monday.com for early-stage startups"},
    {"type": "comparative",      "query": "Notion vs Linear for startup project tracking"},
    {"type": "feature_specific", "query": "project management software with OKR tracking"},
    {"type": "feature_specific", "query": "best PM tool with built-in time tracking for small teams"},
    {"type": "use_case",         "query": "project management software for remote startup teams"},
    {"type": "use_case",         "query": "how startups manage product roadmaps with PM tools"},
    {"type": "trust_signals",    "query": "project management software reviews from startup founders 2025"},
    {"type": "trust_signals",    "query": "Y Combinator recommended project management tools"},
    {"type": "how_to",           "query": "how to set up sprint planning in Jira for a small team"},
    {"type": "how_to",           "query": "how to migrate from spreadsheets to PM software"},
    {"type": "definitional",     "query": "what is agile project management for software startups"},
    {"type": "definitional",     "query": "what is a project management tool and why startups need one"}
  ]
}

Now generate sub-queries for the target query below. Return ONLY the JSON object.\
"""


def _extract_json(text: str) -> str:
    """
    Strip markdown code fences and extract the first {...} block.
    """
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _validate_sub_queries(data: Any) -> list[dict[str, str]]:
    """
    Validate the parsed JSON and return a clean list of sub-query dicts.
    Raises ValueError on structural problems.
    """
    if not isinstance(data, dict):
        raise ValueError("Root element must be a JSON object.")
    raw = data.get("sub_queries")
    if not isinstance(raw, list):
        raise ValueError("Missing or non-array 'sub_queries' key.")
    if len(raw) < 10:
        raise ValueError(f"Too few sub-queries: got {len(raw)}, need at least 10.")

    cleaned: list[dict[str, str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} is not an object.")
        t = item.get("type")
        q = item.get("query")
        if not isinstance(t, str) or t not in _VALID_TYPES:
            raise ValueError(f"Item {i} has invalid type '{t}'.")
        if not isinstance(q, str) or not q.strip():
            raise ValueError(f"Item {i} has empty or missing query.")
        cleaned.append({"type": t, "query": q.strip()})
    return cleaned


def _ensure_min_per_type(sub_queries: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Pad any type that has fewer than 1 entry with a synthetic placeholder.
    Used as a last-resort guard; ideally the LLM covers all types.
    """
    from collections import Counter
    counts = Counter(sq["type"] for sq in sub_queries)
    for vtype in _VALID_TYPES:
        if counts[vtype] < 1:
            logger.warning("Type '%s' missing from LLM output — skipping pad.", vtype)
    return sub_queries


def generate_sub_queries(
    target_query: str,
    model_name: str = "gemini-2.5-flash",
    max_retries: int = 3,
) -> tuple[list[dict[str, str]], str]:
    """
    Call the LLM and return (sub_queries, model_used).
    Raises RuntimeError after max_retries failed attempts.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        return _call_gemini(target_query, api_key, model_name, max_retries)
    elif openai_key:
        return _call_openai(target_query, openai_key, max_retries)
    else:
        raise RuntimeError(
            "No LLM API key configured. Set GEMINI_API_KEY or OPENAI_API_KEY."
        )


def _call_gemini(
    target_query: str,
    api_key: str,
    model_name: str,
    max_retries: int,
) -> tuple[list[dict[str, str]], str]:
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key)

    last_error = ""
    temperatures = [0.3, 0.5, 0.7]

    for attempt in range(max_retries):
        temp = temperatures[min(attempt, len(temperatures) - 1)]
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=f"Target query: {target_query}",
                config=genai_types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=temp,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text
            json_str = _extract_json(raw_text)
            data = json.loads(json_str)
            sub_queries = _validate_sub_queries(data)
            sub_queries = _ensure_min_per_type(sub_queries)
            return sub_queries, model_name
        except json.JSONDecodeError as exc:
            last_error = f"JSONDecodeError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
        except ValueError as exc:
            last_error = f"ValidationError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
        except Exception as exc:
            last_error = f"LLMError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(last_error)


def _call_openai(
    target_query: str,
    api_key: str,
    max_retries: int,
) -> tuple[list[dict[str, str]], str]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model_name = "gpt-4o-mini"
    last_error = ""
    temperatures = [0.3, 0.5, 0.7]

    for attempt in range(max_retries):
        temp = temperatures[min(attempt, len(temperatures) - 1)]
        try:
            completion = client.chat.completions.create(
                model=model_name,
                temperature=temp,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Target query: {target_query}"},
                ],
            )
            raw_text = completion.choices[0].message.content or ""
            json_str = _extract_json(raw_text)
            data = json.loads(json_str)
            sub_queries = _validate_sub_queries(data)
            sub_queries = _ensure_min_per_type(sub_queries)
            return sub_queries, model_name
        except json.JSONDecodeError as exc:
            last_error = f"JSONDecodeError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
        except ValueError as exc:
            last_error = f"ValidationError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
        except Exception as exc:
            last_error = f"LLMError on attempt {attempt + 1}: {exc}"
            logger.warning(last_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(last_error)
