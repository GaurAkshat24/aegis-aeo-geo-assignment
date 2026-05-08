"""
direct_answer.py
Check A — Does the first paragraph answer the query directly?

Scoring (max 20 pts):
  ≤60 words + declarative + no hedge → 20
  ≤60 words but hedging/incomplete   → 12
  61–90 words                         → 8
  >90 words                           → 0
"""
from __future__ import annotations

import spacy
from app.models.schemas import CheckResult
from app.services.aeo_checks.base import BaseCheck
from app.services.content_parser import extract_first_paragraph, ensure_html

_HEDGE_PHRASES = {
    "it depends",
    "may vary",
    "in some cases",
    "this varies",
    "generally speaking",
}

_nlp: spacy.language.Language | None = None


def _get_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _has_subject_and_root_verb(text: str) -> bool:
    """
    Use spaCy dependency parser to check that a sentence has at least one
    subject (nsubj / nsubjpass / expl) and a root token.

    Accepts ROOT tokens with POS VERB or AUX — the latter covers linking verbs
    like "is / are / was / were" which spaCy correctly tags as AUX, not VERB.
    A sentence like "Python is a programming language." has ROOT=is (AUX) and
    should be considered declarative.
    """
    nlp = _get_nlp()
    doc = nlp(text[:512])  # cap for performance
    for sent in doc.sents:
        has_root_predicate = any(
            t.dep_ == "ROOT" and t.pos_ in {"VERB", "AUX"} for t in sent
        )
        has_subj = any(t.dep_ in {"nsubj", "nsubjpass", "expl"} for t in sent)
        if has_root_predicate and has_subj:
            return True
    return False


def _has_hedge(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _HEDGE_PHRASES)


class DirectAnswerCheck(BaseCheck):
    check_id = "direct_answer"
    name = "Direct Answer Detection"
    max_score = 20

    def run(self, content: str) -> CheckResult:
        html = ensure_html(content)
        first_para = extract_first_paragraph(html)

        word_count = len(first_para.split())
        has_hedge = _has_hedge(first_para)
        is_declarative = _has_subject_and_root_verb(first_para)

        # Scoring logic
        if word_count <= 60 and is_declarative and not has_hedge:
            score = 20
        elif word_count <= 60:
            score = 12
        elif word_count <= 90:
            score = 8
        else:
            score = 0

        passed = score >= 20

        if score == 20:
            recommendation = None
        elif word_count > 90:
            recommendation = (
                f"Your opening paragraph is {word_count} words. "
                "Trim it to under 60 words with a direct, declarative answer."
            )
        elif word_count > 60:
            recommendation = (
                f"Your opening paragraph is {word_count} words. "
                "Aim for 60 words or fewer so AI systems can extract a clean direct answer."
            )
        elif has_hedge:
            recommendation = (
                "Your opening paragraph contains hedge language (e.g. 'it depends', "
                "'may vary'). Replace it with a confident, declarative statement."
            )
        else:
            recommendation = (
                "Your opening paragraph lacks a clear declarative structure. "
                "Make sure it contains an explicit subject and main verb."
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            passed=passed,
            score=score,
            max_score=self.max_score,
            details={
                "word_count": word_count,
                "threshold": 60,
                "is_declarative": is_declarative,
                "has_hedge_phrase": has_hedge,
                "first_paragraph_preview": first_para[:200],
            },
            recommendation=recommendation,
        )
