from __future__ import annotations
from pathlib import Path
import re
from datetime import datetime

FITS_EXTENSIONS = (".fit", ".fits", ".fts")

def safe_target_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[<>:\"/\\\\|?*]+", "_", value)
    value = re.sub(r"\s+", "_", value)
    return value.strip("._") or "UNKNOWN"

def is_fits(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(ext) for ext in FITS_EXTENSIONS) or name.endswith(".fits.fz")

def normalize_siril_path(path: Path) -> str:
    # Siril scripts handle forward slashes more consistently across platforms.
    return path.resolve().as_posix()

def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
