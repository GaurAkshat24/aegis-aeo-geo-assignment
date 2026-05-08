from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── AEO Request / Response ───────────────────────────────────────────────────

class AEORequest(BaseModel):
    input_type: str = Field(..., pattern="^(url|text)$", description="'url' or 'text'")
    input_value: str = Field(..., min_length=1)


class CheckDetails(BaseModel):
    model_config = {"extra": "allow"}


class CheckResult(BaseModel):
    check_id: str
    name: str
    passed: bool
    score: int
    max_score: int
    details: dict[str, Any]
    recommendation: Optional[str] = None


class AEOResponse(BaseModel):
    aeo_score: float
    band: str
    checks: list[CheckResult]


class AEOError(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None


# ─── Fan-Out Request / Response ───────────────────────────────────────────────

class FanoutRequest(BaseModel):
    target_query: str = Field(..., min_length=1)
    existing_content: Optional[str] = Field(
        None,
        description="Paste article text here to enable gap analysis",
    )


class SubQuery(BaseModel):
    type: str
    query: str
    covered: Optional[bool] = None
    similarity_score: Optional[float] = None


class GapSummary(BaseModel):
    covered: int
    total: int
    coverage_percent: float
    covered_types: list[str]
    missing_types: list[str]


class FanoutResponse(BaseModel):
    target_query: str
    model_used: str
    total_sub_queries: int
    sub_queries: list[SubQuery]
    gap_summary: Optional[GapSummary] = None


class FanoutError(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None
