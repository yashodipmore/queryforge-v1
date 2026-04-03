"""
Grader for Task 3: Schema Redesign (Hard)
"""

from typing import Any, Dict

from queryforge.db.engine import QueryForgeDB
from queryforge.graders.base import BaseGrader


class SchemaRedesignGrader(BaseGrader):
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

        all_tables = db.get_all_tables()
        original_table = "all_orders"

        original_count_result = db.execute_query(
            f"SELECT COUNT(*) as cnt FROM {original_table}"
        )
        original_count = 0
        if original_count_result["success"] and original_count_result["rows"]:
            original_count = original_count_result["rows"][0].get("cnt", 0)

        has_customer_table = any(
            "customer" in t.lower() or "user" in t.lower()
            for t in all_tables
            if t != original_table
        )
        has_product_table = any(
            "product" in t.lower() or "item" in t.lower()
            for t in all_tables
            if t != original_table
        )
        has_order_table = any(
            "order" in t.lower()
            for t in all_tables
            if t != original_table
        )

        norm_score = 0.0
        if has_customer_table:
            norm_score += 0.25
            result["feedback"] += "Customer table created. "
        else:
            result["feedback"] += "No separate customer table found. "

        if has_product_table:
            norm_score += 0.25
            result["feedback"] += "Product table created. "
        else:
            result["feedback"] += "No separate product table found. "

        result["correctness_score"] = norm_score

        if has_customer_table and has_order_table:
            test_query = """
                SELECT COUNT(*) as cnt FROM orders o
                JOIN customers c ON o.customer_id = c.id
            """
            test_result = db.execute_query(test_query)
            if test_result["success"] and test_result["rows"]:
                joined_count = test_result["rows"][0].get("cnt", 0)
                if joined_count >= original_count:
                    result["performance_score"] = 0.30
                    result["feedback"] += f"Data integrity OK ({joined_count} rows accessible). "
                elif joined_count > 0:
                    ratio = joined_count / max(original_count, 1)
                    result["performance_score"] = round(0.30 * ratio, 4)
                    result["feedback"] += (
                        f"Partial data: {joined_count}/{original_count} rows. "
                    )

        q_upper = current_query.strip().upper()
        if "REFERENCES" in q_upper or "FOREIGN KEY" in q_upper:
            result["syntax_score"] = 0.10
            result["feedback"] += "Foreign keys used. "

        if result["correctness_score"] >= 0.4:
            result["efficiency_bonus"] = self._efficiency_bonus(step, max_steps, base=0.1)

        total = (
            result["syntax_score"]
            + result["correctness_score"]
            + result["performance_score"]
            + result["efficiency_bonus"]
            - result["penalty"]
        )
        result["total"] = self._clamp(total)
        return result
