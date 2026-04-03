"""
QueryForge-v1 Baseline Inference Script

Uses OpenAI client to run an LLM agent against all 3 QueryForge tasks.

Environment variables:
  API_BASE_URL   LLM API endpoint (default: HF router)
  MODEL_NAME     Model identifier
  HF_TOKEN       Hugging Face API key
  QUERYFORGE_URL QueryForge server URL (default: http://localhost:7860)

Stdout format (must not change):
  [START] task=<task> env=queryforge-v1 model=<model>
  [STEP]  step=<n> action=<action> reward=<0.00> done=<true|false> error=<msg|null>
  [END]   success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...>
"""

import os
import textwrap
import time
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
QUERYFORGE_URL = os.getenv("QUERYFORGE_URL", "http://localhost:7860")
BENCHMARK = "queryforge-v1"

TASKS = [
    {"id": "fix_broken_query", "name": "fix_broken_query", "max_steps": 8},
    {"id": "optimize_slow_query", "name": "optimize_slow_query", "max_steps": 10},
    {"id": "schema_redesign", "name": "schema_redesign", "max_steps": 12},
]

SUCCESS_THRESHOLD = 0.5
TEMPERATURE = 0.2
MAX_TOKENS = 512


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    action_clean = action.replace("\n", " ").replace("\r", "")[:100]
    print(
        f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def env_reset(task_id: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{QUERYFORGE_URL}/reset",
        json={"task_id": task_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_step(action: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(
        f"{QUERYFORGE_URL}/step",
        json=action,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


SYSTEM_PROMPT = textwrap.dedent(
    """
You are an expert SQL agent. You will be given a SQL task and must fix or optimize queries.

Available actions (respond with exactly one JSON object):
1. Rewrite query:
   {"action_type": "rewrite_query", "query": "SELECT ..."}

2. Add index:
   {"action_type": "add_index", "index_definition": "CREATE INDEX idx_name ON table(col)"}

3. Analyze table:
   {"action_type": "analyze_table", "table_name": "table_name"}

4. Submit final answer (when done):
   {"action_type": "submit"}

Rules:
- Respond only with valid JSON, no explanation text
- For rewrite_query, write complete valid SQL
- Fix syntax errors first, then optimize
- Use submit when you are confident the query is correct
"""
).strip()


def build_user_prompt(obs: Dict[str, Any], step: int, history: List[str]) -> str:
    schema_str = ""
    for tname, tinfo in obs.get("schema", {}).items():
        cols = ", ".join(f"{c['name']} {c['type']}" for c in tinfo.get("columns", []))
        schema_str += f"  Table {tname} ({cols}) - {tinfo.get('row_count', '?')} rows\n"

    exec_r = obs.get("execution_result", {})
    error_str = exec_r.get("error") or "None"
    rows_preview = str(exec_r.get("rows", [])[:3])
    history_str = "\n".join(history[-5:]) if history else "None yet"

    hint_str = ""
    if obs.get("hint"):
        hint_str = f"\nHint: {obs['hint']}"

    return textwrap.dedent(
        f"""
Task: {obs.get('task_description', '')}
Step: {step} / {obs.get('max_steps', 10)}

Database Schema:
{schema_str}
Current Query:
{obs.get('current_query', '')}

Execution Result:
  - Success: {exec_r.get('success', False)}
  - Error: {error_str}
  - Row count: {exec_r.get('row_count', 0)}
  - Preview: {rows_preview}

Quality Metrics:
  - Syntax valid: {obs.get('quality_metrics', {}).get('syntax_valid', False)}
  - Uses index: {obs.get('quality_metrics', {}).get('uses_index', False)}
  - Full table scan: {obs.get('quality_metrics', {}).get('has_full_scan', True)}
{hint_str}

Recent actions:
{history_str}

Respond with one JSON action.
        """
    ).strip()


def get_agent_action(
    client: OpenAI,
    obs: Dict[str, Any],
    step: int,
    history: List[str],
) -> Dict[str, Any]:
    import json

    user_prompt = build_user_prompt(obs, step, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        text = (completion.choices[0].message.content or "").strip()

        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        action = json.loads(text)
        return action

    except json.JSONDecodeError:
        print("[DEBUG] JSON parse failed, using fallback action", flush=True)
        if "submit" in text.lower():
            return {"action_type": "submit"}
        return {"action_type": "analyze_table", "table_name": "orders"}

    except Exception as e:
        print(f"[DEBUG] LLM call failed: {e}", flush=True)
        return {"action_type": "submit"}


def run_task(client: OpenAI, task: Dict[str, Any]) -> Dict[str, Any]:
    task_id = task["id"]
    max_steps = task["max_steps"]
    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0
    history: List[str] = []

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        obs = env_reset(task_id)
        done = obs.get("done", False)

        for step in range(1, max_steps + 1):
            if done:
                break

            action = get_agent_action(client, obs, step, history)
            action_str = action.get("action_type", "unknown")
            if "query" in action:
                action_display = f"{action_str}({repr(action['query'][:50])})"
            else:
                action_display = action_str

            error_msg = None
            try:
                result = env_step(action)
                reward = result.get("reward", 0.0)
                done = result.get("done", False)
                obs = result.get("observation", obs)
                info = result.get("info", {})
                error_msg = info.get("error") if info else None
                feedback = result.get("reward_detail", {}).get("feedback", "")
            except Exception as e:
                reward = 0.0
                done = True
                error_msg = str(e)
                feedback = ""

            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step,
                action=action_display,
                reward=reward,
                done=done,
                error=error_msg,
            )

            history.append(f"Step {step}: {action_display} -> reward={reward:.2f} | {feedback}")

            if done:
                break

        if rewards:
            score = sum(rewards) / len(rewards)
        score = round(min(max(score, 0.0), 1.0), 4)
        success = score >= SUCCESS_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Task {task_id} failed with exception: {e}", flush=True)
        success = False
        score = 0.0

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task_id": task_id,
        "success": success,
        "score": score,
        "steps": steps_taken,
        "rewards": rewards,
    }


def main() -> None:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN environment variable is required.")

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

    print("[DEBUG] QueryForge-v1 Baseline Inference", flush=True)
    print(f"[DEBUG] Model: {MODEL_NAME}", flush=True)
    print(f"[DEBUG] API: {API_BASE_URL}", flush=True)
    print(f"[DEBUG] Server: {QUERYFORGE_URL}", flush=True)
    print(f"[DEBUG] Tasks: {[t['id'] for t in TASKS]}", flush=True)
    print("", flush=True)

    all_results = []
    for task in TASKS:
        result = run_task(client, task)
        all_results.append(result)
        time.sleep(1)

    print("\n" + "=" * 50, flush=True)
    print("[DEBUG] SUMMARY", flush=True)
    for r in all_results:
        status = "PASS" if r["success"] else "FAIL"
        print(
            f"[DEBUG] {status:<4} | {r['task_id']:<25} | score={r['score']:.3f} | steps={r['steps']}",
            flush=True,
        )
    avg_score = sum(r["score"] for r in all_results) / len(all_results)
    print(f"[DEBUG] Average score: {avg_score:.3f}", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    main()
