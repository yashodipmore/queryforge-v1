"""
QueryForge-v1 main environment.

Implements reset(), step(), state().
"""

import random
from typing import Any, Dict, List, Optional

from queryforge.db.engine import QueryForgeDB
from queryforge.graders.fix_broken import FixBrokenGrader
from queryforge.graders.optimize_slow import OptimizeSlowGrader
from queryforge.graders.schema_redesign import SchemaRedesignGrader
from queryforge.models import (
    ColumnInfo,
    ExecutionResult,
    QualityMetrics,
    QueryForgeAction,
    QueryForgeObservation,
    QueryForgeReward,
    QueryForgeState,
    StepResult,
    TableSchema,
)
from queryforge.tasks.loader import TaskLoader

TASK_MAP = {
    "fix_broken_query": "easy_tasks.json",
    "optimize_slow_query": "medium_tasks.json",
    "schema_redesign": "hard_tasks.json",
}

GRADER_MAP = {
    "fix_broken_query": FixBrokenGrader,
    "optimize_slow_query": OptimizeSlowGrader,
    "schema_redesign": SchemaRedesignGrader,
}

MAX_STEPS_MAP = {
    "fix_broken_query": 8,
    "optimize_slow_query": 10,
    "schema_redesign": 12,
}


class QueryForgeEnv:
    """Main QueryForge environment class."""

    def __init__(self):
        self.db: Optional[QueryForgeDB] = None
        self.task_id: Optional[str] = None
        self.scenario: Optional[Dict[str, Any]] = None
        self.current_query: str = ""
        self.step_count: int = 0
        self.max_steps: int = 10
        self.done: bool = False
        self.cumulative_reward: float = 0.0
        self.reward_history: List[float] = []
        self.action_history: List[str] = []
        self.indexes_added: List[str] = []
        self.grader: Any = None
        self._loader = TaskLoader()
        self._prev_query: str = ""
        self._repeated_action_count: int = 0

    def reset(
        self,
        task_id: str = "fix_broken_query",
        scenario_id: Optional[str] = None,
    ) -> QueryForgeObservation:
        if task_id not in TASK_MAP:
            task_id = "fix_broken_query"

        self.task_id = task_id
        self.step_count = 0
        self.done = False
        self.cumulative_reward = 0.0
        self.reward_history = []
        self.action_history = []
        self.indexes_added = []
        self._repeated_action_count = 0
        self.max_steps = MAX_STEPS_MAP[task_id]

        task_data = self._loader.load(TASK_MAP[task_id])
        scenarios = task_data["scenarios"]

        if scenario_id:
            self.scenario = next((s for s in scenarios if s["id"] == scenario_id), scenarios[0])
        else:
            self.scenario = random.choice(scenarios)

        if task_id == "fix_broken_query":
            self.current_query = self.scenario["broken_query"]
        elif task_id == "optimize_slow_query":
            self.current_query = self.scenario["slow_query"]
        else:
            self.current_query = "SELECT * FROM all_orders LIMIT 5"

        self._prev_query = self.current_query

        if self.db:
            self.db.close()
        self.db = QueryForgeDB()
        setup_ok = self.db.setup_schema(self.scenario["schema_sql"], self.scenario["data_sql"])
        if not setup_ok:
            raise RuntimeError("Failed to initialize scenario schema/data")

        self.grader = GRADER_MAP[task_id]()
        return self._build_observation()

    def step(self, action: QueryForgeAction) -> StepResult:
        if self.done:
            obs = self._build_observation()
            obs.done = True
            reward_detail = QueryForgeReward(total=0.0, feedback="Episode already done.")
            return StepResult(
                observation=obs,
                reward=0.0,
                reward_detail=reward_detail,
                done=True,
                info={"warning": "Episode is already done. Call reset()."},
            )

        if not self.db or not self.scenario or not self.grader:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        self.step_count += 1
        penalty = 0.0
        exploration_bonus = 0.0
        info: Dict[str, Any] = {}

        if action.action_type == "rewrite_query":
            if not action.query or not action.query.strip():
                info["error"] = "rewrite_query requires a non-empty 'query' field."
                penalty = 0.05
            else:
                if action.query.strip() == self._prev_query.strip():
                    self._repeated_action_count += 1
                    penalty = 0.05 * self._repeated_action_count
                    info["warning"] = "Same query submitted again. Penalty applied."
                else:
                    self._repeated_action_count = 0
                    self._prev_query = self.current_query
                    self.current_query = action.query.strip()

        elif action.action_type == "add_index":
            if not action.index_definition or not action.index_definition.strip():
                info["error"] = "add_index requires 'index_definition' field."
                penalty = 0.05
            else:
                idx_result = self.db.execute_index(action.index_definition.strip())
                if idx_result["success"]:
                    self.indexes_added.append(action.index_definition.strip())
                    info["index_created"] = True
                else:
                    info["error"] = idx_result["error"]
                    penalty = 0.02

        elif action.action_type == "analyze_table":
            table = action.table_name or ""
            table_info = self.db.get_table_info(table)
            info["table_analysis"] = table_info
            exploration_bonus = 0.02

        elif action.action_type == "submit":
            self.done = True

        self.action_history.append(action.action_type)

        grade = self.grader.grade_step(
            db=self.db,
            current_query=self.current_query,
            scenario=self.scenario,
            action_type=action.action_type,
            step=self.step_count,
            max_steps=self.max_steps,
        )

        raw_reward = max(0.0, grade["total"] - penalty + exploration_bonus)
        reward = round(min(1.0, raw_reward), 4)

        self.reward_history.append(reward)
        self.cumulative_reward += reward

        if self.step_count >= self.max_steps:
            self.done = True

        reward_detail = QueryForgeReward(
            total=reward,
            syntax_score=grade.get("syntax_score", 0.0),
            correctness_score=grade.get("correctness_score", 0.0),
            performance_score=grade.get("performance_score", 0.0),
            efficiency_bonus=grade.get("efficiency_bonus", 0.0),
            penalty=penalty,
            is_final=self.done,
            feedback=grade.get("feedback", ""),
        )

        obs = self._build_observation()
        obs.done = self.done

        return StepResult(
            observation=obs,
            reward=reward,
            reward_detail=reward_detail,
            done=self.done,
            info=info,
        )

    def state(self) -> QueryForgeState:
        original_query = ""
        if self.scenario:
            original_query = (
                self.scenario.get("broken_query")
                or self.scenario.get("slow_query")
                or "SELECT * FROM all_orders LIMIT 5"
            )

        return QueryForgeState(
            task_id=self.task_id or "none",
            task_scenario_id=self.scenario.get("id", "none") if self.scenario else "none",
            current_query=self.current_query,
            original_query=original_query,
            step=self.step_count,
            max_steps=self.max_steps,
            done=self.done,
            cumulative_reward=round(self.cumulative_reward, 4),
            reward_history=self.reward_history,
            indexes_added=self.indexes_added,
            action_history=self.action_history,
        )

    def _build_observation(self) -> QueryForgeObservation:
        schema_dict: Dict[str, TableSchema] = {}
        if self.db:
            for table_name in self.db.get_all_tables():
                info = self.db.get_table_info(table_name)
                if info.get("exists"):
                    schema_dict[table_name] = TableSchema(
                        name=table_name,
                        columns=[
                            ColumnInfo(
                                name=c["name"],
                                type=c["type"],
                                nullable=c["nullable"],
                                primary_key=c["primary_key"],
                            )
                            for c in info.get("columns", [])
                        ],
                        row_count=info.get("row_count", 0),
                        indexes=self.indexes_added,
                    )

        exec_result_raw: Dict[str, Any] = {
            "success": False,
            "rows": [],
            "row_count": 0,
            "error": "Not executed",
            "execution_time_ms": 0.0,
        }
        if self.db and self.current_query:
            exec_result_raw = self.db.execute_query(self.current_query)

        exec_result = ExecutionResult(
            success=exec_result_raw["success"],
            rows=exec_result_raw.get("rows", [])[:10],
            row_count=exec_result_raw.get("row_count", 0),
            error=exec_result_raw.get("error"),
            execution_time_ms=exec_result_raw.get("execution_time_ms", 0.0),
        )

        uses_index = self.db.uses_index(self.current_query) if self.db and exec_result.success else False
        has_full_scan = self.db.uses_full_scan(self.current_query) if self.db and exec_result.success else True

        quality = QualityMetrics(
            syntax_valid=exec_result.success,
            has_error=not exec_result.success,
            row_count=exec_result.row_count,
            estimated_cost=999.0 if has_full_scan else 100.0,
            uses_index=uses_index,
            has_full_scan=has_full_scan,
        )

        hint = self.scenario.get("hint") if self.scenario else None

        return QueryForgeObservation(
            schema=schema_dict,
            current_query=self.current_query,
            execution_result=exec_result,
            quality_metrics=quality,
            task_id=self.task_id or "none",
            task_description=self.scenario.get("description", "") if self.scenario else "",
            expected_row_count=self.scenario.get("expected_row_count") if self.scenario else None,
            step=self.step_count,
            max_steps=self.max_steps,
            done=self.done,
            hint=hint if self.step_count >= 3 else None,
        )
