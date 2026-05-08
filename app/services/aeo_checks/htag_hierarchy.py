"""
htag_hierarchy.py
Check B — Is there a valid, logical H-tag hierarchy?

Rules:
  1. Exactly one <h1>
  2. No heading level skipped (H1 → H3 without H2 is a violation)
  3. No H-tag before the H1

Scoring (max 20 pts):
  0 violations         → 20
  1–2 violations       → 12
  3+ OR missing H1     → 0
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from app.models.schemas import CheckResult
from app.services.aeo_checks.base import BaseCheck
from app.services.content_parser import strip_boilerplate, ensure_html


class HtagHierarchyCheck(BaseCheck):
    check_id = "htag_hierarchy"
    name = "H-tag Hierarchy"
    max_score = 20

    def run(self, content: str) -> CheckResult:
        html = ensure_html(content)
        soup = strip_boilerplate(html)

        h_tags_found: list[str] = [
            tag.name for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        ]

        violations: list[str] = []

        # Rule 1 — exactly one H1
        h1_count = h_tags_found.count("h1")
        if h1_count == 0:
            violations.append("Missing H1: no <h1> tag found in the content.")
        elif h1_count > 1:
            violations.append(
                f"Multiple H1 tags: found {h1_count} <h1> tags; only one is allowed."
            )

        # Rule 2 — no skipped heading levels
        if h1_count >= 1:
            level_sequence = [int(h[1]) for h in h_tags_found]
            current_max = 0
            for level in level_sequence:
                if level > current_max + 1:
                    violations.append(
                        f"Skipped heading level: jumped from H{current_max} to H{level} "
                        f"without an intermediate heading."
                    )
                current_max = max(current_max, level)

        # Rule 3 — no H-tag before the H1
        if h_tags_found and h_tags_found[0] != "h1" and h1_count >= 1:
            violations.append(
                f"Heading before H1: the first heading found is <{h_tags_found[0]}>, "
                "which appears before any <h1>."
            )

        # Scoring
        v_count = len(violations)
        if h1_count == 0:
            score = 0
        elif v_count == 0:
            score = 20
        elif v_count <= 2:
            score = 12
        else:
            score = 0

        passed = score >= 20

        if passed:
            recommendation = None
        elif h1_count == 0:
            recommendation = "Add a single <h1> tag to define the primary topic of your content."
        elif v_count >= 3:
            recommendation = (
                "Your heading structure has multiple violations. "
                "Restructure to a clean H1 → H2 → H3 hierarchy with no skipped levels."
            )
        else:
            recommendation = (
                "Fix heading hierarchy: "
                + " | ".join(violations)
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            passed=passed,
            score=score,
            max_score=self.max_score,
            details={
                "violations": violations,
                "h_tags_found": h_tags_found,
            },
            recommendation=recommendation,
        )
