"""
Grader for Task 2: Optimize Slow Query (Medium)
"""

from typing import Any, Dict

from queryforge.db.engine import QueryForgeDB
from queryforge.graders.base import BaseGrader


class OptimizeSlowGrader(BaseGrader):
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
            result["feedback"] = f"Query error: {exec_result['error']}"
            return result

        expected_range = scenario.get("expected_row_count_range")
        expected_exact = scenario.get("expected_row_count")
        actual = exec_result["row_count"]

        if expected_exact and actual == expected_exact:
            result["correctness_score"] = 0.3
        elif expected_range:
            lo, hi = expected_range
            if lo <= actual <= hi:
                result["correctness_score"] = 0.3
            elif actual > 0:
                result["correctness_score"] = 0.1
        elif actual > 0:
            result["correctness_score"] = 0.2

        uses_index = db.uses_index(current_query)
        has_full_scan = db.uses_full_scan(current_query)

        perf = 0.0
        if uses_index:
            perf += 0.25
            result["feedback"] += "Uses index. "
        else:
            result["feedback"] += "No index usage detected. "

        if not has_full_scan:
            perf += 0.15
            result["feedback"] += "No full table scan. "
        else:
            result["feedback"] += "Full table scan detected. "

        q_upper = current_query.strip().upper()
        slow_q_upper = scenario.get("slow_query", "").strip().upper()
        if "SELECT" in slow_q_upper and "JOIN" not in slow_q_upper:
            if "JOIN" in q_upper:
                perf += 0.05
                result["feedback"] += "Replaced subquery with JOIN. "

        result["performance_score"] = min(perf, 0.4)

        if result["performance_score"] >= 0.3 and result["correctness_score"] >= 0.2:
            result["efficiency_bonus"] = self._efficiency_bonus(step, max_steps)

        total = (
            result["syntax_score"]
            + result["correctness_score"]
            + result["performance_score"]
            + result["efficiency_bonus"]
        )

        result["syntax_score"] = 0.0
        result["total"] = self._clamp(total)
        return result
