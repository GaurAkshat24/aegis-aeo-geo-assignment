"""
readability.py
Check C — Flesch-Kincaid Grade Level target: 7–9

Scoring (max 20 pts):
  FK 7–9   → 20
  FK 6/10  → 14
  FK 5/11  → 8
  ≤4/≥12   → 0

Also surfaces the 3 most complex sentences (by syllable-count ÷ word-count).
"""
from __future__ import annotations

import re
import textstat
from app.models.schemas import CheckResult
from app.services.aeo_checks.base import BaseCheck
from app.services.content_parser import html_to_text, ensure_html


def _syllable_density(sentence: str) -> float:
    """Ratio of syllables to words — proxy for per-sentence complexity."""
    words = sentence.split()
    if not words:
        return 0.0
    syllables = textstat.syllable_count(sentence)
    return syllables / len(words)


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter on . ! ? boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if len(s.split()) >= 5]


def _top_complex_sentences(text: str, n: int = 3) -> list[str]:
    sentences = _split_sentences(text)
    ranked = sorted(sentences, key=_syllable_density, reverse=True)
    top = ranked[:n]
    # Truncate long sentences for readability in the response
    return [s if len(s) <= 120 else s[:117] + "..." for s in top]


def _fk_score(score: float) -> int:
    """Map an FK grade level to a check score."""
    if 7 <= score <= 9:
        return 20
    if score in {6, 10} or 6 <= score <= 7 or 9 <= score <= 10:
        return 14
    if score in {5, 11} or 5 <= score <= 6 or 10 <= score <= 11:
        return 8
    return 0


class ReadabilityCheck(BaseCheck):
    check_id = "readability"
    name = "Snippet Readability"
    max_score = 20

    def run(self, content: str) -> CheckResult:
        html = ensure_html(content)
        plain_text = html_to_text(html)

        if not plain_text.strip():
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                passed=False,
                score=0,
                max_score=self.max_score,
                details={
                    "fk_grade_level": None,
                    "target_range": "7-9",
                    "complex_sentences": [],
                },
                recommendation="No readable text found in the content.",
            )

        fk_grade = round(textstat.flesch_kincaid_grade(plain_text), 1)
        score = _fk_score(fk_grade)
        passed = score >= 20
        complex_sentences = _top_complex_sentences(plain_text)

        if passed:
            recommendation = None
        elif fk_grade < 7:
            recommendation = (
                f"Content reads at Grade {fk_grade}, which is below the target range of 7–9. "
                "Add more nuance and technical depth to increase credibility with AI systems."
            )
        else:
            recommendation = (
                f"Content reads at Grade {fk_grade}. Shorten sentences and replace technical "
                "jargon with plain language to reach Grade 7–9."
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            passed=passed,
            score=score,
            max_score=self.max_score,
            details={
                "fk_grade_level": fk_grade,
                "target_range": "7-9",
                "complex_sentences": complex_sentences,
            },
            recommendation=recommendation,
        )
