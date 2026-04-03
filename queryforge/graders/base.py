"""Base grader class that all task graders inherit from."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from queryforge.db.engine import QueryForgeDB


class BaseGrader(ABC):
    """
    Abstract base class for all QueryForge task graders.
    Each grader knows how to score an agent current query state.
    """

    @abstractmethod
    def grade_step(
        self,
        db: QueryForgeDB,
        current_query: str,
        scenario: Dict[str, Any],
        action_type: str,
        step: int,
        max_steps: int,
    ) -> Dict[str, Any]:
        """
        Grade the current step.

        Returns dict with:
          - total: float in [0.0, 1.0]
          - syntax_score: float
          - correctness_score: float
          - performance_score: float
          - efficiency_bonus: float
          - penalty: float
          - feedback: str
          - is_final: bool
        """
        raise NotImplementedError

    def _clamp(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        return max(min_val, min(max_val, value))

    def _efficiency_bonus(self, step: int, max_steps: int, base: float = 0.1) -> float:
        if step <= 1:
            return base
        ratio = 1.0 - (step / max_steps)
        return round(base * max(ratio, 0.0), 4)
