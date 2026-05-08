"""
aeo.py — AEO Content Scorer endpoint

POST /api/aeo/analyze
Accepts a URL or raw HTML/text, runs 3 NLP checks, and returns an
AEO Readiness Score (0–100) with per-check diagnostics.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import AEORequest, AEOResponse, AEOError, CheckResult
from app.services.content_parser import fetch_url, ensure_html
from app.services.aeo_checks.direct_answer import DirectAnswerCheck
from app.services.aeo_checks.htag_hierarchy import HtagHierarchyCheck
from app.services.aeo_checks.readability import ReadabilityCheck

logger = logging.getLogger(__name__)
router = APIRouter()

_CHECKS = [
    DirectAnswerCheck(),
    HtagHierarchyCheck(),
    ReadabilityCheck(),
]

_BAND_MAP = [
    (85, "AEO Optimized ✅"),
    (65, "Needs Improvement 🟡"),
    (40, "Significant Gaps 🔴"),
    (0,  "Not AEO Ready ⛔"),
]


def _score_to_band(score: float) -> str:
    for threshold, label in _BAND_MAP:
        if score >= threshold:
            return label
    return "Not AEO Ready ⛔"


@router.post("/analyze", response_model=AEOResponse)
async def analyze(request: AEORequest):
    # 1. Resolve content
    if request.input_type == "url":
        raw_html, error_detail = await fetch_url(request.input_value)
        if error_detail:
            err = AEOError(
                error="url_fetch_failed",
                message="Could not retrieve content from the provided URL.",
                detail=error_detail,
            )
            return JSONResponse(status_code=422, content=err.model_dump())
        content = raw_html
    else:
        content = ensure_html(request.input_value)

    if not content.strip():
        err = AEOError(
            error="empty_content",
            message="The provided content is empty or could not be parsed.",
        )
        return JSONResponse(status_code=422, content=err.model_dump())

    # 2. Run checks
    results: list[CheckResult] = []
    for check in _CHECKS:
        try:
            result = check.run(content)
            results.append(result)
        except Exception as exc:
            logger.exception("Check '%s' raised an unexpected error.", check.check_id)
            # Return a zero-score result rather than crashing the entire request
            results.append(
                CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    passed=False,
                    score=0,
                    max_score=check.max_score,
                    details={"error": str(exc)},
                    recommendation="Check failed due to an internal error.",
                )
            )

    # 3. Aggregate
    max_possible = sum(c.max_score for c in _CHECKS)
    raw_score = sum(r.score for r in results)
    aeo_score = round((raw_score / max_possible) * 100, 1)
    band = _score_to_band(aeo_score)

    return AEOResponse(aeo_score=aeo_score, band=band, checks=results)
