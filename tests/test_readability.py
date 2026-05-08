"""
Tests for the Snippet Readability check (Check C).
"""
import pytest
from app.services.aeo_checks.readability import ReadabilityCheck, _fk_score

check = ReadabilityCheck()


# ─── UNIT TESTS: SCORE MAPPING ───────────────────────────────────────────────

def test_fk_grade_7_9_maps_to_20():
    assert _fk_score(7.0) == 20
    assert _fk_score(8.5) == 20
    assert _fk_score(9.0) == 20


def test_fk_grade_6_or_10_maps_to_14():
    assert _fk_score(6.0) == 14
    assert _fk_score(10.0) == 14
    assert _fk_score(6.5) == 14


def test_fk_grade_5_or_11_maps_to_8():
    assert _fk_score(5.0) == 8
    assert _fk_score(11.0) == 8
    assert _fk_score(5.5) == 8


def test_fk_grade_extreme_maps_to_0():
    assert _fk_score(3.0) == 0
    assert _fk_score(13.0) == 0
    assert _fk_score(1.0) == 0


# ─── INTEGRATION TESTS: FULL CHECK RUN ───────────────────────────────────────

def test_simple_content_runs_without_error():
    """The check should return a valid CheckResult for any non-empty content."""
    html = """
    <html><body>
      <h1>What is SEO?</h1>
      <p>SEO stands for Search Engine Optimization. It helps websites rank higher in search results.
      Good SEO involves using the right keywords and building quality links.</p>
    </body></html>
    """
    result = check.run(html)
    assert result.check_id == "readability"
    assert result.max_score == 20
    assert isinstance(result.details["fk_grade_level"], float)
    assert result.details["target_range"] == "7-9"
    assert isinstance(result.details["complex_sentences"], list)


def test_empty_content_returns_zero():
    """Empty content should return a zero score without crashing."""
    result = check.run("<html><body></body></html>")
    assert result.score == 0
    assert result.passed is False


def test_plain_text_is_accepted():
    """Plain text without HTML tags should be handled."""
    text = "The cat sat on the mat. The dog ran to the park. Simple words are best."
    result = check.run(text)
    assert result.check_id == "readability"
    assert result.details["fk_grade_level"] is not None


def test_complex_academic_text_has_high_fk():
    """
    Highly academic text should produce a high FK grade level and score 0 or low.
    """
    html = """
    <html><body>
    <p>
    The epistemological implications of poststructuralist deconstruction necessitate
    a comprehensive reassessment of hermeneutical methodologies in contemporary
    philosophical discourse. Phenomenological investigations into intersubjective
    consciousness presuppose ontological commitments that are antithetical to
    empiricist epistemologies. The circumlocutory obfuscation perpetuated by
    academicians constitutes an impediment to the dissemination of substantive
    intellectual contributions.
    </p>
    </body></html>
    """
    result = check.run(html)
    assert result.details["fk_grade_level"] > 10


# ─── DETAIL FIELDS ──────────────────────────────────────────────────────────

def test_result_has_expected_fields():
    html = "<html><body><p>This is a simple test sentence for readability scoring.</p></body></html>"
    result = check.run(html)
    assert "fk_grade_level" in result.details
    assert "target_range" in result.details
    assert "complex_sentences" in result.details
    assert len(result.details["complex_sentences"]) <= 3
