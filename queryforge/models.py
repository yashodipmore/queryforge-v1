"""
Pydantic models for QueryForge-v1 OpenEnv environment.
All models are typed and validated.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False


class TableSchema(BaseModel):
    name: str
    columns: List[ColumnInfo]
    row_count: int = 0
    indexes: List[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    success: bool
    rows: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class QualityMetrics(BaseModel):
    syntax_valid: bool = False
    has_error: bool = True
    row_count: int = 0
    estimated_cost: float = 999.0
    uses_index: bool = False
    has_full_scan: bool = True
    correctness_score: float = 0.0


class QueryForgeObservation(BaseModel):
    schema: Dict[str, TableSchema] = Field(
        description="All tables in the database with their schemas"
    )
    current_query: str = Field(description="The SQL query agent is currently working on")
    execution_result: ExecutionResult = Field(description="Result of running the current query")
    quality_metrics: QualityMetrics = Field(description="Measurable quality metrics of current query")
    task_id: str = Field(description="Which task is being solved")
    task_description: str = Field(description="Human-readable objective")
    expected_row_count: Optional[int] = Field(
        default=None,
        description="Expected number of rows in correct answer (if known)",
    )
    step: int = Field(default=0, description="Current step number")
    max_steps: int = Field(default=10, description="Maximum steps allowed")
    done: bool = Field(default=False)
    hint: Optional[str] = Field(
        default=None,
        description="Optional hint for the agent (may be None)",
    )


class QueryForgeAction(BaseModel):
    action_type: Literal[
        "rewrite_query",
        "add_index",
        "analyze_table",
        "submit",
    ] = Field(description="Type of action to take")
    query: Optional[str] = Field(
        default=None,
        description="New SQL query text (required for rewrite_query)",
    )
    index_definition: Optional[str] = Field(
        default=None,
        description="Full CREATE INDEX statement (required for add_index)",
    )
    table_name: Optional[str] = Field(
        default=None,
        description="Name of table to analyze (required for analyze_table)",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent reasoning for this action (not used in grading)",
    )


class QueryForgeReward(BaseModel):
    total: float = Field(
        ge=0.0,
        le=1.0,
        description="Total reward for this step (0.0 to 1.0)",
    )
    syntax_score: float = Field(
        default=0.0,
        ge=0.0,
        le=0.3,
        description="Reward for syntactically valid query (max 0.3)",
    )
    correctness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=0.4,
        description="Reward for returning correct results (max 0.4)",
    )
    performance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=0.2,
        description="Reward for query efficiency (max 0.2)",
    )
    efficiency_bonus: float = Field(
        default=0.0,
        ge=0.0,
        le=0.1,
        description="Bonus for completing in fewer steps (max 0.1)",
    )
    penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty for destructive actions or loops",
    )
    is_final: bool = Field(
        default=False,
        description="True if this is the graded final submission",
    )
    feedback: str = Field(
        default="",
        description="Human-readable feedback on this step reward",
    )


class StepResult(BaseModel):
    observation: QueryForgeObservation
    reward: float = Field(ge=0.0, le=1.0)
    reward_detail: QueryForgeReward
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class QueryForgeState(BaseModel):
    task_id: str
    task_scenario_id: str
    current_query: str
    original_query: str
    step: int
    max_steps: int
    done: bool
    cumulative_reward: float
    reward_history: List[float]
    indexes_added: List[str]
    action_history: List[str]
