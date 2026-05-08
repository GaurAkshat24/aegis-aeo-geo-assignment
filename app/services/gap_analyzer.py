"""
gap_analyzer.py

Semantic gap analysis using sentence-transformers (all-MiniLM-L6-v2).

Model choice rationale:
  all-MiniLM-L6-v2 is ~5× faster than all-mpnet-base-v2 and uses ~3× less
  memory, making it more suitable for a latency-sensitive API. Its embedding
  quality is sufficient for intent-level similarity matching (we're comparing
  query types, not fine-grained paraphrase detection). In production we would
  A/B test thresholds with real click-through data to choose the best model.

Threshold (0.72):
  The 0.72 threshold is kept from the spec. It sits between "topically related"
  (~0.5–0.65) and "near-duplicate" (>0.85). It correctly filters out weak
  associations while accepting paraphrase-level coverage. In production this
  would be tuned using a labeled test set of (query, content) pairs.

Cosine similarity is computed with sklearn rather than raw dot product on
non-normalized vectors to avoid a common correctness bug.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_COVERAGE_THRESHOLD = 0.72
_MAX_CHUNK_WORDS = 60  # roughly one paragraph per embedding


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    logger.info("Loading sentence-transformer model '%s'...", _MODEL_NAME)
    return SentenceTransformer(_MODEL_NAME)


def _chunk_text(text: str, max_words: int = _MAX_CHUNK_WORDS) -> list[str]:
    """
    Split plain text into sentence-level chunks of at most max_words.
    Uses double-newlines then single newlines, then falls back to sliding window.
    """
    # Split on paragraph boundaries first
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        words = para.split()
        if len(words) <= max_words:
            chunks.append(para)
        else:
            # Sliding window for long paragraphs
            for i in range(0, len(words), max_words):
                chunk = " ".join(words[i : i + max_words])
                if chunk:
                    chunks.append(chunk)
    return chunks or [text.strip()]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two 1-D vectors.
    Explicitly normalises to avoid the raw-dot-product bug.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def analyze_gaps(
    sub_queries: list[dict[str, str]],
    content: str,
    threshold: float = _COVERAGE_THRESHOLD,
) -> tuple[list[dict], dict]:
    """
    For each sub-query, compute max cosine similarity against content chunks.
    Returns (annotated_sub_queries, gap_summary).
    """
    model = _get_model()

    from app.services.content_parser import ensure_html, html_to_text

    # Use plain text for embedding (strip HTML tags if any)
    plain = html_to_text(ensure_html(content)) if "<" in content else content
    chunks = _chunk_text(plain)

    # Encode content chunks
    chunk_embeddings: np.ndarray = model.encode(chunks, convert_to_numpy=True)

    # Encode all sub-queries in one batch for efficiency
    queries = [sq["query"] for sq in sub_queries]
    query_embeddings: np.ndarray = model.encode(queries, convert_to_numpy=True)

    annotated: list[dict] = []
    for sq, q_emb in zip(sub_queries, query_embeddings):
        similarities = [
            _cosine_similarity(q_emb, c_emb) for c_emb in chunk_embeddings
        ]
        max_sim = max(similarities) if similarities else 0.0
        covered = max_sim >= threshold
        annotated.append(
            {
                "type": sq["type"],
                "query": sq["query"],
                "covered": covered,
                "similarity_score": round(max_sim, 4),
            }
        )

    # Build gap summary
    covered_count = sum(1 for sq in annotated if sq["covered"])
    total = len(annotated)
    covered_types = sorted({sq["type"] for sq in annotated if sq["covered"]})
    missing_types = sorted({sq["type"] for sq in annotated if not sq["covered"]})

    gap_summary = {
        "covered": covered_count,
        "total": total,
        "coverage_percent": round(covered_count / total * 100, 1) if total else 0.0,
        "covered_types": covered_types,
        "missing_types": missing_types,
    }

    return annotated, gap_summary
