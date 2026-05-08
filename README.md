# AEGIS — Submission README

A Python/FastAPI content intelligence service implementing AEO scoring and query fan-out
gap analysis. Built as a take-home assignment for the AI Engineer role.

---

## 🎥 Walkthrough Video

A short video walkthrough covering the approach, technical decisions, and relevant experience has been submitted via Google Drive:

[▶ Watch Walkthrough Video](https://drive.google.com/file/d/1kxaU6P_yOFMqQrMTKewe0bXpULKzfRCh/view?usp=sharing)

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Set environment variables

```bash
# At least one of these is required for Feature 2 (Fan-Out Engine):
export GOOGLE_API_KEY=your_gemini_api_key        # Preferred — Gemini 2.5 Flash
export OPENAI_API_KEY=your_openai_api_key       # Fallback — GPT-4o-mini

# Feature 1 (AEO Scorer) works with no API key.
```

### 3. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### 4. Open the interactive docs

Navigate to `http://localhost:5000/docs` for the Swagger UI.

### 5. Run tests

```bash
pytest tests/ -v
```

---

## API Reference

### `POST /api/aeo/analyze`

Accepts a URL or raw HTML/text and returns an AEO Readiness Score (0–100) with
per-check diagnostics.

```bash
curl -X POST http://localhost:5000/api/aeo/analyze \
  -H "Content-Type: application/json" \
  -d '{"input_type": "url", "input_value": "https://example.com/article"}'
```

```bash
curl -X POST http://localhost:5000/api/aeo/analyze \
  -H "Content-Type: application/json" \
  -d '{"input_type": "text", "input_value": "<html><body><h1>Title</h1><p>Short answer here.</p></body></html>"}'
```

### `POST /api/fanout/generate`

Generates 10–15 sub-queries across 6 types via LLM. Add `existing_content` to
trigger semantic gap analysis.

```bash
curl -X POST http://localhost:5000/api/fanout/generate \
  -H "Content-Type: application/json" \
  -d '{"target_query": "best AI writing tool for SEO"}'
```

---

## What I Completed vs. Skipped

### Completed

- **Feature 1 — AEO Content Scorer** (all 3 checks)
  - Check A (Direct Answer Detection): spaCy dependency parsing for declarative
    structure, word count, hedge phrase detection
  - Check B (H-tag Hierarchy): BeautifulSoup DOM-order H-tag validation, 3 rules
  - Check C (Snippet Readability): textstat FK grade level, top-3 complex sentences
    by syllable density
  - Score aggregation and band labelling
- **Feature 2 — Query Fan-Out Engine**
  - LLM prompt with embedded JSON schema + concrete example
  - 3-retry logic with escalating temperature (0.3 → 0.5 → 0.7)
  - `_extract_json()` strips markdown fences and prose preambles
  - Pydantic-equivalent validation of response structure
  - Supports Gemini 2.5 Flash (primary) and GPT-4o-mini (fallback)
- **Semantic Gap Analysis**
  - sentence-transformers `all-MiniLM-L6-v2` embeddings
  - Batch encoding of content chunks and sub-queries
  - Explicit normalised cosine similarity (avoids raw dot-product bug)
  - Gap summary by type (covered/missing)
- **Tests** — all three AEO check functions, plus LLM JSON parsing/validation tests
  with mocked LLM calls
- **PROMPT_LOG.md** — prompt iteration log with three drafts

### Simplified / Noted Gaps

- **CPU-bound blocking**: spaCy and sentence-transformers calls run synchronously
  inside `async def` endpoint handlers. This is acceptable at interview scale but
  would block the event loop under concurrent load. Fix: `run_in_executor`.
- **Model warm-up**: The embedding model loads on the first `/fanout/generate` request
  (adds ~5–15 s cold-start latency). Production fix: load model in a FastAPI
  `@app.on_event("startup")` handler.
- **`en_core_web_sm` not `en_core_web_lg`**: Smaller model used for installation speed.
  The larger model has better dependency parse accuracy for short sentences.

---

## Engineering Decisions

### 1. LLM JSON Reliability

Three defensive layers:

1. **Prompt level** — System prompt specifies exact JSON schema, bans markdown fences,
   lists all valid `type` values, requires at least 2 per type, and includes a
   complete concrete 12-item example. Gemini's `response_mime_type="application/json"`
   is used to constrain output at the model level.
2. **Extraction level** — `_extract_json()` strips ` ```json ` / ` ``` ` fences and
   extracts the first `{…}` block even when the model wraps output in prose.
3. **Validation level** — `_validate_sub_queries()` checks: root is a dict, key is
   `sub_queries`, it's a list, length ≥ 10, each item has exactly the allowed type
   values, and every `query` is a non-empty string.

Retry strategy: up to 3 attempts. Temperature starts at 0.3 (deterministic) and
escalates to 0.5 then 0.7 — low temperature first for consistency; higher temperature
if the model is stuck in a degenerate output. Network errors use exponential backoff.

### 2. Embedding Model: `all-MiniLM-L6-v2`

| Attribute | MiniLM-L6-v2 | mpnet-base-v2 |
|---|---|---|
| Inference speed | ~5× faster | Baseline |
| Model size | 80 MB | 420 MB |
| STSB Spearman r | 0.8954 | 0.9057 |

For intent-level coverage detection (are these queries topically related?) the ~1%
accuracy difference is not meaningful, and the latency/memory savings are significant
in a web API context. In production I would benchmark both on a labeled dataset of
(sub-query, content) pairs before committing.

### 3. Similarity Threshold (0.72)

Kept at 0.72. The threshold sits between "topically adjacent" (~0.5–0.65) and
"near-paraphrase" (>0.85), capturing "strong semantic overlap" which is the right bar
for content coverage.

To tune in production:
1. Label a sample of (sub-query, content excerpt) pairs as covered/not covered.
2. Sweep thresholds 0.55–0.85, compute F1 (or precision@k).
3. Pick the threshold that maximises F1, biasing toward recall if false negatives
   (missed gaps) are costlier than false positives.

### 4. Content Parsing Robustness

| Failure mode | Handling |
|---|---|
| No `<p>` tags | Falls back to first text block in DOM |
| JS-heavy / empty HTML | Checks run on available text; minimal score returned |
| Login wall / HTTP error | `fetch_url` returns `AEOError` with status code |
| Connection timeout | 10 s timeout; `detail` field surfaces the error message |
| Plain text input | `ensure_html()` wraps in `<p>` tags before parsing |

### 5. Failure Modes

| Failure | Response |
|---|---|
| URL fetch fails | HTTP 422 `url_fetch_failed` |
| Empty content | HTTP 422 `empty_content` |
| Individual check crashes | Score 0 for that check; other checks still run |
| LLM bad JSON × 3 retries | HTTP 503 `llm_unavailable` + last error detail |
| Gap analysis fails | Sub-queries returned without coverage data (non-fatal) |
| No API key configured | HTTP 503 with descriptive message |

### 6. Sync vs. Async

Endpoints use `async def`. spaCy and textstat calls are synchronous inside the async
handler — acceptable at single-request scale but would block the event loop under
concurrency. LLM calls use the synchronous `google-generativeai` SDK; the async
variant (`generate_content_async`) would be preferable in production. The sentence-
transformers encode call is also blocking and should be wrapped in
`asyncio.get_event_loop().run_in_executor(None, ...)` for production workloads.

---

## What I'd Improve with More Time

1. **Async executor** for all CPU-bound operations (spaCy, textstat, sentence-transformers)
2. **Model warm-up** at startup so the first request doesn't pay the cold-start penalty
3. **`en_core_web_lg`** for better dependency parse quality on short/ambiguous sentences
4. **Threshold calibration** with a labeled test set of (sub-query, content) pairs
5. **LLM response caching** with Redis to avoid repeated calls during rate-limited testing
6. **Async LLM calls** using `generate_content_async` + `asyncio.gather` for fanout
7. **Frontend dashboard** showing score gauges, violations, and recommendations visually
