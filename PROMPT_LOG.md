# PROMPT_LOG — Fan-Out Engine Prompt Iteration

This document records the evolution of the LLM prompt used for `POST /api/fanout/generate`.

---

## Draft 1 — First Attempt (Too Minimal)

```
Given the query: "{target_query}"

Generate 10-15 sub-queries that an AI search engine would ask to build a comprehensive answer.
Include comparisons, features, use cases, trust signals, how-to questions, and definitions.

Return JSON.
```

**What went wrong:**

- The model returned JSON in different shapes on different calls: sometimes `{"queries": [...]}`,
  sometimes a bare array `[...]`, sometimes wrapped in markdown fences.
- The `type` field was inconsistently named: `"comparison"`, `"compare"`, `"vs"` instead
  of the canonical `"comparative"`.
- On ~30% of calls the model included extra fields like `"priority"`, `"intent"`, or
  `"rationale"` which were not requested.
- When the query was very specific, the model sometimes generated only 7–8 sub-queries
  rather than the required 10.
- No example in the prompt → the model invented its own output shape.

---

## Draft 2 — Added Structure, No Example

```
You are an AI search analyst. Decompose the following query into 10-15 sub-queries 
across exactly these 6 types:
- comparative: comparisons to alternatives
- feature_specific: specific capabilities
- use_case: real-world applications
- trust_signals: reviews and credibility
- how_to: procedural questions
- definitional: conceptual explanations

Generate at least 2 sub-queries per type.

Return ONLY a valid JSON object with this structure:
{
  "sub_queries": [
    {"type": "<type>", "query": "<query text>"}
  ]
}

Do not include markdown. Do not add extra fields.

Query: {target_query}
```

**What improved:**
- The `type` values became more consistent — the named enum stopped most hallucinated types.
- Markdown fence wrapping dropped to ~15% of calls.
- Extra fields dropped significantly.

**Remaining problems:**
- Still occasionally got fewer than 10 sub-queries on narrow/technical topics.
- The model occasionally added `"explanation"` fields alongside `"type"` and `"query"`.
- No concrete example = the model still invented edge-case structures.
- On one test with "best CRM for small business", the model returned 8 items and stopped.

---

## Draft 3 — Final Prompt (Production)

The final prompt (`_SYSTEM_PROMPT` in `fanout_engine.py`) adds:

1. **Role framing** — "You are an AI search engine analyst" gives the model a consistent
   persona that produces more structured, analyst-style output.
2. **Explicit count constraint** — "Generate between 10 and 15 sub-queries total"
   eliminates under-generation. The model takes hard bounds more seriously than soft ones.
3. **Numbered rules list** — LLMs follow numbered instruction lists more reliably than
   prose paragraphs. Rules state exactly what is forbidden (extra fields, invalid types,
   generic queries not tied to the topic).
4. **Concrete 12-item example** — The example is the single highest-leverage change.
   It shows the model the exact shape, the exact enum values, the exact level of
   specificity for queries, and that no other fields are present. Models are strong
   in-context learners; an example disambiguates ambiguity that text descriptions miss.
5. **`response_mime_type="application/json"`** — For Gemini, this parameter instructs the
   model at the API level to produce JSON. It is not a substitute for a good prompt but
   eliminates one class of output format failures.
6. **Defensive extraction** — Even with the final prompt, the model occasionally wraps
   the JSON in a ` ```json ``` ` fence when using certain API versions. `_extract_json()`
   handles this as a post-processing step so the validation layer receives clean JSON.

**What the final prompt does NOT do:**
- It does not use function calling / tool use (available in both Gemini and OpenAI APIs),
  which would enforce the JSON schema at the API level with zero prompt engineering.
  I chose to keep a text prompt to demonstrate prompt engineering skill, but in production
  I would use structured output / function calling as the primary mechanism.

---

## Lessons

1. **Examples outperform instructions.** A single concrete example with the correct
   output shape was more effective than two paragraphs of format instructions.
2. **Hard bounds beat soft ones.** "Generate between 10 and 15" worked; "generate around 12" did not.
3. **Named enums stop hallucination.** Listing the exact allowed string values for `type`
   eliminated type-field hallucination almost entirely.
4. **Always strip fences.** Even well-prompted models wrap JSON in fences ~10% of the
   time. `_extract_json()` is a cheap, necessary safety net.
5. **Retry temperature escalation helps.** When the model gets stuck in a degenerate
   pattern at temperature 0.3, a retry at 0.7 almost always produces valid output.
