"""
fanout.py — Query Fan-Out Engine endpoint

POST /api/fanout/generate
Calls an LLM to generate 10-15 sub-queries across 6 types, then optionally
runs semantic gap analysis against provided content.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import (
    FanoutRequest, FanoutResponse, FanoutError, SubQuery, GapSummary,
)
from app.services.fanout_engine import generate_sub_queries
from app.services.gap_analyzer import analyze_gaps

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=FanoutResponse)
async def generate(request: FanoutRequest):
    # 1. Generate sub-queries via LLM
    try:
        raw_sub_queries, model_used = generate_sub_queries(request.target_query)
    except RuntimeError as exc:
        err = FanoutError(
            error="llm_unavailable",
            message="Fan-out generation failed. The LLM returned an invalid response after 3 retries.",
            detail=str(exc),
        )
        return JSONResponse(status_code=503, content=err.model_dump())
    except Exception as exc:
        logger.exception("Unexpected error in fan-out generation.")
        err = FanoutError(
            error="internal_error",
            message="An unexpected error occurred during fan-out generation.",
            detail=str(exc),
        )
        return JSONResponse(status_code=500, content=err.model_dump())

    # 2. Optional gap analysis
    gap_summary_model: GapSummary | None = None
    annotated_queries = raw_sub_queries

    if request.existing_content and request.existing_content.strip():
        try:
            annotated_queries, gap_summary_dict = analyze_gaps(
                raw_sub_queries, request.existing_content
            )
            gap_summary_model = GapSummary(**gap_summary_dict)
        except Exception as exc:
            logger.exception("Gap analysis failed — returning sub-queries without coverage data.")
            # Non-fatal: return results without gap analysis rather than failing entirely

    # 3. Build sub-query models
    sub_query_models: list[SubQuery] = []
    for sq in annotated_queries:
        sub_query_models.append(
            SubQuery(
                type=sq["type"],
                query=sq["query"],
                covered=sq.get("covered"),
                similarity_score=sq.get("similarity_score"),
            )
        )

    return FanoutResponse(
        target_query=request.target_query,
        model_used=model_used,
        total_sub_queries=len(sub_query_models),
        sub_queries=sub_query_models,
        gap_summary=gap_summary_model,
    )
