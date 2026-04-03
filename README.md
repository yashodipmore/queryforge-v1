---
title: QueryForge-v1
emoji: "mag"
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - sql
  - database
  - agent
  - reinforcement-learning
---

# QueryForge-v1

A real-world SQL query optimization and debugging environment for AI agents.

QueryForge trains and evaluates agents on tasks that database engineers do every day:
fixing broken queries, optimizing slow ones, and redesigning inefficient schemas.

## Environment Overview

| Property | Value |
|----------|-------|
| Backend | SQLite in-memory |
| Tasks | 3 (Easy to Hard) |
| Max steps | 8 / 10 / 12 per task |
| Reward range | 0.0 to 1.0 (partial, per step) |
| Action space | 4 action types |
| Observation space | Schema + Query + Execution Result + Metrics |

## Tasks

### Task 1: Fix Broken SQL Query (Easy)
Agent receives a query with syntax or logic errors. Goal: fix the query so it executes and returns the correct rows.

### Task 2: Optimize Slow Query (Medium)
Agent receives a syntactically correct but slow query. Goal: add indexes and/or rewrite the query to eliminate expensive operations.

### Task 3: Redesign Inefficient Schema (Hard)
Agent receives a denormalized table. Goal: propose a normalized schema, write migration queries, and verify data integrity.

## Action Space

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| rewrite_query | Replace current query with new SQL | query |
| add_index | Add an index to the schema | index_definition |
| analyze_table | Inspect a table columns and statistics | table_name |
| submit | Submit current query as final answer | none |

## Reward Function

```
reward = syntax_score (0.3)
       + correctness_score (0.4)
       + performance_score (0.2)
       + efficiency_bonus (0.1)
       - penalties
```

Reward is computed at every step to provide continuous signal.

## Setup

### Local Development

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

### Docker

```bash
docker build -t queryforge-v1 .
docker run -p 7860:7860 queryforge-v1
```

### API Usage

```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "fix_broken_query"}'

curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "rewrite_query", "query": "SELECT customer_id, SUM(amount) FROM orders WHERE status = '\''paid'\'' GROUP BY customer_id"}'

curl http://localhost:7860/state
```

### Run Baseline Inference

```bash
export HF_TOKEN=your_token_here
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export QUERYFORGE_URL=http://localhost:7860

python inference.py
```

## OpenEnv Validation

```bash
pip install openenv-core
openenv validate
```

## License

MIT
