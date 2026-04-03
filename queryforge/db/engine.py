"""
SQLite in-memory database engine for QueryForge.
Each episode gets a fresh in-memory database.
No external database required.
"""

import sqlite3
import time
from typing import Any, Dict, List, Optional


class QueryForgeDB:
    """
    In-memory SQLite database for one episode.
    Created fresh on each reset().
    """

    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA analysis_limit=1000")

    def setup_schema(self, schema_sql: str, data_sql: str) -> bool:
        try:
            if not self.conn:
                return False
            self.conn.executescript(schema_sql)
            self.conn.executescript(data_sql)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Schema setup error: {e}")
            return False

    def execute_query(self, query: str) -> Dict[str, Any]:
        start = time.perf_counter()
        if not self.conn:
            return {
                "success": False,
                "rows": [],
                "row_count": 0,
                "error": "Database connection is closed.",
                "execution_time_ms": 0.0,
            }

        try:
            normalized = query.strip().upper()
            if any(
                normalized.startswith(kw)
                for kw in ["DROP TABLE", "DELETE FROM", "TRUNCATE"]
            ):
                return {
                    "success": False,
                    "rows": [],
                    "row_count": 0,
                    "error": "Destructive operations not allowed. Use SELECT or CREATE INDEX.",
                    "execution_time_ms": 0.0,
                }

            cursor = self.conn.execute(query)
            rows = cursor.fetchall()
            elapsed = (time.perf_counter() - start) * 1000
            result_rows = [dict(r) for r in rows]
            return {
                "success": True,
                "rows": result_rows,
                "row_count": len(result_rows),
                "error": None,
                "execution_time_ms": round(elapsed, 3),
            }
        except sqlite3.Error as e:
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "success": False,
                "rows": [],
                "row_count": 0,
                "error": str(e),
                "execution_time_ms": round(elapsed, 3),
            }

    def execute_index(self, index_ddl: str) -> Dict[str, Any]:
        if not self.conn:
            return {"success": False, "error": "Database connection is closed."}

        normalized = index_ddl.strip().upper()
        if not normalized.startswith("CREATE INDEX") and not normalized.startswith(
            "CREATE UNIQUE INDEX"
        ):
            return {
                "success": False,
                "error": "Only CREATE INDEX statements allowed for add_index action.",
            }
        try:
            self.conn.execute(index_ddl)
            self.conn.commit()
            return {"success": True, "error": None}
        except sqlite3.Error as e:
            return {"success": False, "error": str(e)}

    def get_query_plan(self, query: str) -> str:
        if not self.conn:
            return "PLAN_UNAVAILABLE"
        try:
            cursor = self.conn.execute(f"EXPLAIN QUERY PLAN {query}")
            rows = cursor.fetchall()
            plan_lines = [f"{r[0]}|{r[1]}|{r[2]}|{r[3]}" for r in rows]
            return "\n".join(plan_lines)
        except Exception:
            return "PLAN_UNAVAILABLE"

    def uses_full_scan(self, query: str) -> bool:
        plan = self.get_query_plan(query)
        return "SCAN" in plan and "INDEX" not in plan

    def uses_index(self, query: str) -> bool:
        plan = self.get_query_plan(query)
        return "USING INDEX" in plan or "INDEX" in plan

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        if not self.conn:
            return {"table": table_name, "exists": False, "error": "Database closed."}
        try:
            cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not row["notnull"],
                    "primary_key": bool(row["pk"]),
                }
                for row in cursor.fetchall()
            ]
            count_row = self.conn.execute(
                f"SELECT COUNT(*) as cnt FROM {table_name}"
            ).fetchone()
            row_count = count_row["cnt"] if count_row else 0
            return {
                "table": table_name,
                "columns": columns,
                "row_count": row_count,
                "exists": True,
            }
        except Exception as e:
            return {"table": table_name, "exists": False, "error": str(e)}

    def get_all_tables(self) -> List[str]:
        if not self.conn:
            return []
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row["name"] for row in cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        self.close()
