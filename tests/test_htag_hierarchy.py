"""
Tests for the H-tag Hierarchy check (Check B).
"""
import pytest
from app.services.aeo_checks.htag_hierarchy import HtagHierarchyCheck

check = HtagHierarchyCheck()


# ─── PASSING CASES ──────────────────────────────────────────────────────────

def test_perfect_hierarchy():
    """H1 → H2 → H3 with no violations → 20 pts."""
    html = """
    <html><body>
      <h1>Main Title</h1>
      <h2>Section One</h2>
      <h3>Subsection</h3>
      <h2>Section Two</h2>
    </body></html>
    """
    result = check.run(html)
    assert result.score == 20
    assert result.passed is True
    assert result.details["violations"] == []


def test_single_h1_only():
    """A page with just an H1 and no sub-headings is valid."""
    html = "<html><body><h1>Only Heading</h1><p>Content here.</p></body></html>"
    result = check.run(html)
    assert result.score == 20
    assert result.passed is True


# ─── FAILING CASES ──────────────────────────────────────────────────────────

def test_missing_h1_scores_zero():
    """No H1 present → 0 pts."""
    html = """
    <html><body>
      <h2>Section</h2>
      <h3>Sub-section</h3>
    </body></html>
    """
    result = check.run(html)
    assert result.score == 0
    assert result.passed is False
    assert any("Missing H1" in v for v in result.details["violations"])


def test_skipped_level_is_violation():
    """H1 → H3 without H2 is a violation."""
    html = """
    <html><body>
      <h1>Title</h1>
      <h3>Jumped level</h3>
    </body></html>
    """
    result = check.run(html)
    violations = result.details["violations"]
    assert any("Skipped" in v for v in violations)
    assert result.score <= 12


def test_multiple_h1_is_violation():
    """More than one H1 should be flagged."""
    html = """
    <html><body>
      <h1>First Title</h1>
      <h2>Section</h2>
      <h1>Second Title</h1>
    </body></html>
    """
    result = check.run(html)
    violations = result.details["violations"]
    assert any("Multiple H1" in v for v in violations)
    assert result.score < 20


def test_htag_before_h1_is_violation():
    """An H2 appearing before the H1 should be flagged."""
    html = """
    <html><body>
      <h2>Section before H1</h2>
      <h1>Title</h1>
    </body></html>
    """
    result = check.run(html)
    violations = result.details["violations"]
    assert any("before" in v.lower() for v in violations)


# ─── DETAIL FIELDS ──────────────────────────────────────────────────────────

def test_result_has_expected_fields():
    html = "<html><body><h1>Title</h1><h2>Sub</h2></body></html>"
    result = check.run(html)
    assert "violations" in result.details
    assert "h_tags_found" in result.details
    assert isinstance(result.details["h_tags_found"], list)
    assert isinstance(result.details["violations"], list)
