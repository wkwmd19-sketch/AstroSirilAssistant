from __future__ import annotations
from pathlib import Path
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_app_config():
    return load_yaml(PACKAGE_ROOT / "config" / "app.yaml")

def save_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
