from __future__ import annotations
from pathlib import Path
import shutil
from typing import Optional

from .project import PROJECT_DIRS, project_name
from .config import save_yaml
from .utils import safe_target_name, is_fits, iso_now

SUPPORTED_SEQUENCE_EXTS = (".fit", ".fits", ".fts", ".fits.fz")

def _files(folder: Path | None):
    if folder is None:
        return []
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted([p for p in folder.rglob("*") if p.is_file() and is_fits(p)])

def _copy_files(files, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, target_dir / p.name)

def _source_record(folder: Path | None, count: int):
    return {
        "path": str(Path(folder).resolve()) if folder else None,
        "count": int(count),
    }

def create_sequence_project(
    root: Path,
    target: str,
    capture_date: str,
    category: str,
    lights_dir: Path,
    darks_dir: Optional[Path] = None,
    flats_dir: Optional[Path] = None,
    bias_dir: Optional[Path] = None,
    dark_flats_dir: Optional[Path] = None,
    camera_mode: str = "AUTO",
    input_status: str = "RAW_UNCALIBRATED",
    copy_inputs: bool = False,
):
    root = Path(root)
    lights_dir = Path(lights_dir)
    if not lights_dir.exists():
        raise FileNotFoundError(f"Lights 폴더가 없습니다: {lights_dir}")

    lights = _files(lights_dir)
    if len(lights) < 2:
        raise ValueError("실제 sequence 전처리는 최소 2장의 FITS Light가 필요합니다.")

    sources = {
        "lights": _files(lights_dir),
        "dark": _files(darks_dir),
        "flat": _files(flats_dir),
        "bias": _files(bias_dir),
        "dark_flat": _files(dark_flats_dir),
    }

    pdir = root / project_name(target, capture_date)
    if pdir.exists():
        raise FileExistsError(f"이미 프로젝트가 존재합니다: {pdir}")

    for rel in PROJECT_DIRS:
        (pdir / rel).mkdir(parents=True, exist_ok=True)

    if copy_inputs:
        _copy_files(sources["lights"], pdir / "input" / "lights")
        _copy_files(sources["dark"], pdir / "calibration" / "dark")
        _copy_files(sources["flat"], pdir / "calibration" / "flat")
        _copy_files(sources["bias"], pdir / "calibration" / "bias")
        _copy_files(sources["dark_flat"], pdir / "calibration" / "dark_flat")
        source_folders = {
            "lights": _source_record(pdir / "input" / "lights", len(sources["lights"])),
            "dark": _source_record(pdir / "calibration" / "dark", len(sources["dark"])),
            "flat": _source_record(pdir / "calibration" / "flat", len(sources["flat"])),
            "bias": _source_record(pdir / "calibration" / "bias", len(sources["bias"])),
            "dark_flat": _source_record(pdir / "calibration" / "dark_flat", len(sources["dark_flat"])),
        }
    else:
        source_folders = {
            "lights": _source_record(lights_dir, len(sources["lights"])),
            "dark": _source_record(darks_dir, len(sources["dark"])),
            "flat": _source_record(flats_dir, len(sources["flat"])),
            "bias": _source_record(bias_dir, len(sources["bias"])),
            "dark_flat": _source_record(dark_flats_dir, len(sources["dark_flat"])),
        }

    target_clean = safe_target_name(target)
    project = {
        "schema_version": "0.4.0",
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
                "camera_type": camera_mode.upper(),
                "sensor": "UNKNOWN",
                "filter": {"type": "UNKNOWN", "name": "UNKNOWN"},
                "tracking": {"mode": "TRACKED", "confidence": None, "user_confirmed": False},
                "binning": "UNKNOWN",
                "roi": "UNKNOWN",
                "sensor_mode": "UNKNOWN",
            },

            "sources": {
                "copy_inputs": bool(copy_inputs),
                "folders": source_folders,
            },

            "sessions": {
                "multi_session": False,
                "count": 1,
                "items": [],
                "classified": False,
            },

            "filter_groups": {
                "is_multifilter": False,
                "items": [],
                "classified": False,
            },

            "input_stage": {
                "source_stage": "LIGHT_SEQUENCE",
                "user_confirmed": True,
            },

            "star_trail": {
                "mode": "UNKNOWN",
                "user_confirmed": False,
                "frame_quality_checked": False,
                "frame_quality_report": None,
                "composition": {
                    "engine": "UNKNOWN",
                    "mode": "MAX_OR_LIGHTEN_PENDING",
                    "gap_check": "PENDING",
                    "artifact_candidates": [],
                },
            },

            "calibration": {
                "input_status": input_status.upper(),
                "user_confirmed": True,
                "checked": False,
                "recommended_action": "CHECK",
                "used_shared_library": False,
                "library_candidates": [],
                "frames": {
                    k: {
                        "available": source_folders[k]["count"] > 0,
                        "path": source_folders[k]["path"],
                        "count": source_folders[k]["count"],
                    }
                    for k in ("dark", "bias", "flat", "dark_flat")
                },
                "masters": {},
                "compatibility": {},
            },

            "quality": {
                "checked": False,
                "metrics": {},
                "candidate_rejects": [],
            },

            "tracking_events": {
                "classified": False,
                "events": [],
            },

            "current_state": "INPUT_STAGE_CONFIRMED",

            "image_state": {
                "linearity": "LINEAR",
                "linearity_confidence": 1.0,
                "stretched": False,
                "stars_removed": False,
                "color_calibrated": False,
                "gradient_corrected": False,
                "denoised": False,
                "deblurred": False,
                "recombined": False,
            },

            "current_file": None,

            "paths": {
                "input": "input",
                "calibration": "calibration",
                "working": "working",
                "output": "output",
                "logs": "logs",
                "temp": "temp",
            },

            "runtime": {
                "siril_version": None,
                "siril_executable": None,
            },

            "next_task": {
                "task_id": "PREPROCESS_PLAN",
                "title": "Calibration / Registration / Stack 계획 생성",
                "summary": "현재 Light와 보유 Calibration 프레임에 맞는 Siril 실행 계획을 만듭니다.",
                "purpose": "실행 전에 어떤 Master와 어떤 Siril 명령이 사용되는지 사용자에게 보여줍니다.",
                "current_status": "LIGHT_SEQUENCE / READY_TO_PLAN",
                "recommendations": {
                    "mode": "SEMI_AUTO",
                    "approval": "실제 실행 전 사용자 승인 필요",
                },
                "cautions": [
                    "v0.4.0 실제 실행 엔진은 FITS sequence를 우선 지원합니다.",
                    "일주사진/달·행성/혜성은 이 딥스카이 실행 경로를 사용하지 않습니다.",
                ],
                "completion_criteria": ["preprocess_plan.json 생성"],
                "actions": ["PREVIEW", "RUN", "EDIT"],
            },
        },
    }
    save_yaml(pdir / "project.yaml", project)
    return pdir
