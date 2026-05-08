"""
Tests for the Direct Answer Detection check (Check A).
"""
import pytest
from app.services.aeo_checks.direct_answer import DirectAnswerCheck

check = DirectAnswerCheck()


# ─── PASSING CASES ──────────────────────────────────────────────────────────

def test_perfect_short_declarative():
    """Short declarative paragraph with no hedges → 20 pts."""
    html = "<html><body><p>Python is a high-level programming language designed for readability and rapid development.</p></body></html>"
    result = check.run(html)
    assert result.score == 20
    assert result.passed is True
    assert result.details["has_hedge_phrase"] is False
    assert result.details["is_declarative"] is True


def test_plain_text_input():
    """Plain text (no HTML tags) should be wrapped and scored correctly."""
    text = "FastAPI is a modern web framework for building APIs with Python 3.11+."
    result = check.run(text)
    assert result.score == 20
    assert result.details["word_count"] <= 60


# ─── FAILING CASES ──────────────────────────────────────────────────────────

def test_over_ninety_words_scores_zero():
    """A first paragraph over 90 words should score 0."""
    long_para = " ".join(["word"] * 95)
    html = f"<html><body><p>{long_para}</p></body></html>"
    result = check.run(html)
    assert result.score == 0
    assert result.passed is False
    assert result.details["word_count"] > 90


def test_hedge_phrase_reduces_score():
    """A paragraph with a hedge phrase should score 12, not 20."""
    html = (
        "<html><body><p>"
        "It depends on your specific situation and requirements for this task."
        "</p></body></html>"
    )
    result = check.run(html)
    assert result.details["has_hedge_phrase"] is True
    assert result.score <= 12


def test_sixty_one_to_ninety_words_scores_eight():
    """61–90 words should score 8."""
    medium_para = " ".join(["word"] * 70)
    html = f"<html><body><p>{medium_para}</p></body></html>"
    result = check.run(html)
    assert result.score == 8


# ─── DETAIL FIELDS ──────────────────────────────────────────────────────────

def test_result_has_expected_fields():
    html = "<html><body><p>AEGIS is a content intelligence platform for AEO and GEO optimization.</p></body></html>"
    result = check.run(html)
    assert "word_count" in result.details
    assert "threshold" in result.details
    assert "is_declarative" in result.details
    assert "has_hedge_phrase" in result.details
    assert result.details["threshold"] == 60
