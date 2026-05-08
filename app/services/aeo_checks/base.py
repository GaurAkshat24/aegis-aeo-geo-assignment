from abc import ABC, abstractmethod
from app.models.schemas import CheckResult


class BaseCheck(ABC):
    """Abstract base class for all AEO checks."""

    check_id: str = ""
    name: str = ""
    max_score: int = 20

    @abstractmethod
    def run(self, content: str) -> CheckResult:
        """
        Execute the check against the provided content string.

        Args:
            content: Raw HTML or plain text to evaluate.

        Returns:
            CheckResult with score, details, and recommendation.
        """
        ...
