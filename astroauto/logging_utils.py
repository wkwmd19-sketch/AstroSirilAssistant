from __future__ import annotations
from pathlib import Path
import json
from .utils import iso_now

def append_jsonl(project_dir: Path, event: dict):
    path = Path(project_dir) / "logs" / "events.jsonl"
    payload = {"timestamp": iso_now(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
