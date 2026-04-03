"""
Grader for Task 1: Fix Broken SQL Query (Easy)
"""

from typing import Any, Dict

from queryforge.db.engine import QueryForgeDB
from queryforge.graders.base import BaseGrader


class FixBrokenGrader(BaseGrader):
    def grade_step(
        self,
        db: QueryForgeDB,
        current_query: str,
        scenario: Dict[str, Any],
        action_type: str,
        step: int,
        max_steps: int,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "total": 0.0,
            "syntax_score": 0.0,
            "correctness_score": 0.0,
            "performance_score": 0.0,
            "efficiency_bonus": 0.0,
            "penalty": 0.0,
            "feedback": "",
            "is_final": action_type == "submit",
        }

        exec_result = db.execute_query(current_query)
        if not exec_result["success"]:
            result["feedback"] = f"Syntax error: {exec_result['error']}"
            result["total"] = 0.0
            return result

        result["syntax_score"] = 0.3

        expected_count = scenario.get("expected_row_count")
        actual_count = exec_result["row_count"]

        if expected_count is not None:
            if actual_count == expected_count:
                result["correctness_score"] = 0.4
                result["feedback"] = f"Correct. Returns {actual_count} rows as expected."
            elif actual_count > 0:
                ratio = min(actual_count, expected_count) / max(actual_count, expected_count)
                result["correctness_score"] = round(0.4 * ratio, 4)
                result["feedback"] = f"Partial: got {actual_count} rows, expected {expected_count}."
            else:
                result["feedback"] = "Query returns 0 rows."
        else:
            if actual_count > 0:
                result["correctness_score"] = 0.3
            result["feedback"] = f"Query runs, returns {actual_count} rows."

        q_upper = current_query.strip().upper()
        if "SELECT *" not in q_upper:
            result["performance_score"] = 0.1

        if "JOIN" in q_upper and "ON" in q_upper:
            result["performance_score"] += 0.1

        if "JOIN" not in q_upper:
            result["performance_score"] = 0.2

        if result["correctness_score"] >= 0.4:
            result["efficiency_bonus"] = self._efficiency_bonus(step, max_steps)

        if action_type in ["DROP", "DELETE"]:
            result["penalty"] = 0.2

        total = (
            result["syntax_score"]
            + result["correctness_score"]
            + result["performance_score"]
            + result["efficiency_bonus"]
            - result["penalty"]
        )
        result["total"] = self._clamp(total)
        return result
