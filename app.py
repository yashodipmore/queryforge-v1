"""
FastAPI server for QueryForge-v1.
Exposes /reset, /step, /state, /health endpoints.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from queryforge.env import QueryForgeEnv
from queryforge.models import QueryForgeAction

env = QueryForgeEnv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    env.reset(task_id="fix_broken_query")
    yield
    if env.db:
        env.db.close()


app = FastAPI(
    title="QueryForge-v1",
    description="SQL Query Optimization and Debugging OpenEnv Environment",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResetRequest(BaseModel):
    task_id: str = "fix_broken_query"
    scenario_id: Optional[str] = None


class StepRequest(BaseModel):
    action_type: str
    query: Optional[str] = None
    index_definition: Optional[str] = None
    table_name: Optional[str] = None
    reasoning: Optional[str] = None


@app.get("/")
async def root():
    return {
        "name": "queryforge-v1",
        "status": "ok",
        "message": "QueryForge-v1 is running. Use /health, /reset, /step, /state, and /tasks.",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "environment": "queryforge-v1", "version": "1.0.0"}


@app.post("/reset")
async def reset(request: ResetRequest = ResetRequest()):
    try:
        obs = env.reset(task_id=request.task_id, scenario_id=request.scenario_id)
        return obs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/step")
async def step(request: StepRequest):
    try:
        action = QueryForgeAction(
            action_type=request.action_type,
            query=request.query,
            index_definition=request.index_definition,
            table_name=request.table_name,
            reasoning=request.reasoning,
        )
        result = env.step(action)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/state")
async def state():
    try:
        return env.state().model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/tasks")
async def list_tasks():
    return {
        "tasks": [
            {
                "id": "fix_broken_query",
                "name": "Fix Broken SQL Query",
                "difficulty": "easy",
                "max_steps": 8,
            },
            {
                "id": "optimize_slow_query",
                "name": "Optimize Slow Query",
                "difficulty": "medium",
                "max_steps": 10,
            },
            {
                "id": "schema_redesign",
                "name": "Redesign Inefficient Schema",
                "difficulty": "hard",
                "max_steps": 12,
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
