import json
import os
from typing import Any, Dict

TASKS_DIR = os.path.join(os.path.dirname(__file__))


class TaskLoader:
    def load(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(TASKS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
