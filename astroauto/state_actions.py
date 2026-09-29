from __future__ import annotations
from pathlib import Path

from .project import load_project, save_project
from .workflow import next_task_after_analysis
from .logging_utils import append_jsonl

VALID_INPUT_STAGES = {
    "LIGHT_SEQUENCE",
    "SINGLE_LIGHT",
    "REGISTERED_SEQUENCE",
    "STACKED_LINEAR",
    "STACKED_NONLINEAR",
    "UNKNOWN",
}

VALID_CALIBRATION_STATUS = {
    "RAW_UNCALIBRATED",
    "PRECALIBRATED",
    "UNKNOWN",
}

VALID_STAR_TRAIL_MODES = {
    "STAR_TRAIL_SKY",
    "STAR_TRAIL_LANDSCAPE",
    "UNKNOWN",
}

def confirm_input_stage(project_dir: Path, stage: str):
    stage = stage.upper()
    if stage not in VALID_INPUT_STAGES:
        raise ValueError(f"지원하지 않는 입력 단계: {stage}")

    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    p.setdefault("input_stage", {})
    p["input_stage"]["source_stage"] = stage
    p["input_stage"]["user_confirmed"] = stage != "UNKNOWN"
    p["current_state"] = "INPUT_STAGE_CONFIRMED" if stage != "UNKNOWN" else "REVIEW_REQUIRED"

    if stage == "STACKED_LINEAR":
        p["image_state"]["linearity"] = "LINEAR"
        p["image_state"]["linearity_confidence"] = 1.0
        p["image_state"]["stretched"] = False
        # A stacked image is not to be calibrated/registered again.
        p.setdefault("calibration", {})
        p["calibration"]["input_status"] = "PRECALIBRATED"
        p["calibration"]["user_confirmed"] = True

    elif stage == "STACKED_NONLINEAR":
        p["image_state"]["linearity"] = "NONLINEAR"
        p["image_state"]["linearity_confidence"] = 1.0
        p["image_state"]["stretched"] = True
        p.setdefault("calibration", {})
        p["calibration"]["input_status"] = "PRECALIBRATED"
        p["calibration"]["user_confirmed"] = True

    p["next_task"] = next_task_after_analysis(project)
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "USER_CONFIRM_INPUT_STAGE",
        "value": stage,
        "status": "SUCCESS",
    })
    return project

def confirm_calibration_status(project_dir: Path, status: str):
    status = status.upper()
    if status not in VALID_CALIBRATION_STATUS:
        raise ValueError(f"지원하지 않는 캘리브레이션 상태: {status}")

    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    p.setdefault("calibration", {})
    p["calibration"]["input_status"] = status
    p["calibration"]["user_confirmed"] = status != "UNKNOWN"

    if status == "PRECALIBRATED":
        p["current_state"] = "PRECALIBRATED_CONFIRMED"

    p["next_task"] = next_task_after_analysis(project)
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "USER_CONFIRM_CALIBRATION_STATUS",
        "value": status,
        "status": "SUCCESS",
    })
    return project

def confirm_star_trail_mode(project_dir: Path, mode: str):
    mode = mode.upper()
    if mode not in VALID_STAR_TRAIL_MODES:
        raise ValueError(f"지원하지 않는 별 일주 모드: {mode}")

    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    if p["target"]["category"] != "STAR_TRAIL":
        raise ValueError("STAR_TRAIL 프로젝트가 아닙니다.")

    p.setdefault("star_trail", {})
    p["star_trail"]["mode"] = mode
    p["star_trail"]["user_confirmed"] = mode != "UNKNOWN"
    p["current_state"] = "STAR_TRAIL_MODE_CONFIRMED" if mode != "UNKNOWN" else "REVIEW_REQUIRED"
    p["next_task"] = next_task_after_analysis(project)

    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "USER_CONFIRM_STAR_TRAIL_MODE",
        "value": mode,
        "status": "SUCCESS",
    })
    return project
