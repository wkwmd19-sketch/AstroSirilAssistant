from __future__ import annotations
from pathlib import Path
from datetime import date
import shutil
import yaml

from .utils import safe_target_name, is_fits, iso_now
from .config import save_yaml

PROJECT_DIRS = [
    "input",
    "working/01_gradient",
    "working/02_color",
    "working/03_denoise",
    "working/04_stretch",
    "working/05_starnet",
    "working/06_starless",
    "working/07_recombine",
    "working/08_final",
    "output/fits",
    "output/tiff",
    "output/png",
    "output/preview",
    "logs",
    "temp",
]

def project_name(target: str, capture_date: str) -> str:
    return f"{safe_target_name(target)}_{capture_date}_Auto"

def create_project(root: Path, target: str, capture_date: str, category: str, input_file: Path, copy_input: bool = True):
    input_file = Path(input_file)
    if not input_file.exists():
        raise FileNotFoundError(input_file)
    if not is_fits(input_file):
        raise ValueError("v0.3 MVP의 프로젝트 생성 입력은 FITS(.fit/.fits/.fts)만 지원합니다.")

    pdir = root / project_name(target, capture_date)
    if pdir.exists():
        raise FileExistsError(f"이미 프로젝트가 존재합니다: {pdir}")

    for rel in PROJECT_DIRS:
        (pdir / rel).mkdir(parents=True, exist_ok=True)

    target_clean = safe_target_name(target)
    ext = ".fits" if input_file.name.lower().endswith(".fits") else input_file.suffix.lower()
    dest = pdir / "input" / f"{target_clean}_00_input{ext}"

    if copy_input:
        shutil.copy2(input_file, dest)
        input_source_mode = "COPIED"
    else:
        # To keep project self-contained and Windows-friendly, v0.3 stores the source path
        # but still requires analyze to access it.
        dest = input_file.resolve()
        input_source_mode = "EXTERNAL_REFERENCE"

    project = {
        "schema_version": "0.3",
        "project": {
            "id": pdir.name,
            "target_name": target_clean,
            "root_path": str(pdir),
            "processing_mode": "SEMI_AUTO",
            "created_at": iso_now(),
            "target": {
                "category": category,
                "subtypes": [],
                "features": [],
                "classification_confidence": 1.0 if category != "UNKNOWN" else 0.0,
                "user_confirmed": category != "UNKNOWN",
            },
            "capture": {
                "date": capture_date,
                "camera_type": "UNKNOWN",
                "sensor": "UNKNOWN",
                "filter": {"type": "UNKNOWN", "name": "UNKNOWN"},
                "tracking": {"mode": "UNKNOWN", "confidence": None, "user_confirmed": False},
            },
            "current_state": "INPUT_IMPORTED",
            "image_state": {
                "linearity": "UNKNOWN",
                "linearity_confidence": 0.0,
                "stretched": None,
                "stars_removed": False,
                "color_calibrated": False,
                "gradient_corrected": False,
                "denoised": False,
                "deblurred": False,
                "recombined": False,
            },
            "input": {
                "source_mode": input_source_mode,
                "original_path": str(input_file.resolve()),
            },
            "current_file": str(dest),
            "paths": {rel.split("/")[0]: rel.split("/")[0] for rel in ["input", "working", "output", "logs", "temp"]},
            "runtime": {
                "siril_version": None,
                "siril_executable": None,
            },
            "next_task": None,
        }
    }
    save_yaml(pdir / "project.yaml", project)
    return pdir

def load_project(project_dir: Path):
    path = Path(project_dir) / "project.yaml"
    if not path.exists():
        raise FileNotFoundError(f"project.yaml을 찾지 못했습니다: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_project(project_dir: Path, data):
    save_yaml(Path(project_dir) / "project.yaml", data)

def find_project_fits(project_dir: Path) -> Path:
    data = load_project(project_dir)
    current = Path(data["project"]["current_file"])
    if current.exists() and is_fits(current):
        return current

    candidates = [p for p in (Path(project_dir) / "input").iterdir() if p.is_file() and is_fits(p)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError("프로젝트 input 폴더에서 FITS 파일을 찾지 못했습니다.")
    raise RuntimeError("input 폴더에 FITS가 여러 개 있습니다. current_file을 지정해야 합니다.")
