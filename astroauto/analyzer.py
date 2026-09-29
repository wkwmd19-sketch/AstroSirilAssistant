from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project, find_project_fits
from .siril import get_siril_info, write_jsonmetadata
from .fits_analysis import analyze_pixels, read_header_summary, infer_linearity, load_siril_metadata
from .workflow import next_task_after_analysis
from .logging_utils import append_jsonl

def analyze_project(project_dir: Path, config: dict):
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    fits_path = find_project_fits(project_dir)

    info = get_siril_info(config)
    metadata_path = project_dir / "logs" / "siril_metadata.json"
    proc = write_jsonmetadata(config, fits_path, metadata_path)

    analysis_cfg = config.get("analysis", {})
    pixel_stats = analyze_pixels(
        fits_path,
        max_samples=int(analysis_cfg.get("max_samples_per_channel", 1500000)),
        bins=int(analysis_cfg.get("histogram_bins", 2048)),
        clip_fraction=float(analysis_cfg.get("clip_fraction", 0.0001)),
    )
    header_summary, history = read_header_summary(fits_path)
    linearity = infer_linearity(history)
    siril_meta = load_siril_metadata(metadata_path)

    report = {
        "input_file": str(fits_path),
        "siril": {
            "version": info.version,
            "executable": str(info.executable),
        },
        "header": header_summary,
        "history": history,
        "linearity_assessment": linearity,
        "pixel_statistics": pixel_stats,
        "siril_metadata": siril_meta,
    }
    report_path = project_dir / "logs" / "analysis_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    p = project["project"]
    p["runtime"]["siril_version"] = info.version
    p["runtime"]["siril_executable"] = str(info.executable)
    p["current_state"] = "INPUT_ANALYZED"
    # v0.3.1 migration safety: older projects may not yet have these fields.
    p.setdefault("input_stage", {"source_stage": "UNKNOWN", "user_confirmed": False})
    p.setdefault("calibration", {
        "input_status": "UNKNOWN",
        "user_confirmed": False,
        "checked": False,
        "recommended_action": "CHECK",
        "frames": {},
        "masters": {},
        "compatibility": {},
    })
    p["image_state"]["linearity"] = linearity["status"]
    p["image_state"]["linearity_confidence"] = linearity["confidence"]
    p["image_state"]["stretched"] = (
        True if linearity["status"] == "NONLINEAR"
        else False if linearity["status"] == "LINEAR"
        else None
    )

    # Fill capture hints when available, but never overwrite confirmed user data blindly.
    hdr = header_summary
    if hdr.get("INSTRUME") and p["capture"].get("sensor", "UNKNOWN") == "UNKNOWN":
        p["capture"]["sensor"] = str(hdr["INSTRUME"])
    if hdr.get("FILTER") and p["capture"]["filter"].get("name", "UNKNOWN") == "UNKNOWN":
        p["capture"]["filter"]["name"] = str(hdr["FILTER"])
    if hdr.get("EXPTIME") is not None:
        p["capture"].setdefault("exposure", {})["single_sec"] = hdr["EXPTIME"]
    elif hdr.get("EXPOSURE") is not None:
        p["capture"].setdefault("exposure", {})["single_sec"] = hdr["EXPOSURE"]

    task = next_task_after_analysis(project)
    p["next_task"] = task
    save_project(project_dir, project)

    append_jsonl(project_dir, {
        "event": "ANALYZE_INPUT",
        "status": "SUCCESS",
        "input_file": str(fits_path),
        "siril_version": info.version,
        "linearity": linearity,
        "analysis_report": str(report_path),
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    })
    return project, report, task

def confirm_linearity(project_dir: Path, value: str):
    value = value.upper()
    if value not in ("LINEAR", "NONLINEAR"):
        raise ValueError("value는 LINEAR 또는 NONLINEAR이어야 합니다.")
    project = load_project(project_dir)
    p = project["project"]
    p["image_state"]["linearity"] = value
    p["image_state"]["linearity_confidence"] = 1.0
    p["image_state"]["stretched"] = value == "NONLINEAR"
    p["next_task"] = next_task_after_analysis(project)
    save_project(project_dir, project)
    append_jsonl(Path(project_dir), {
        "event": "USER_CONFIRM_LINEARITY",
        "value": value,
        "status": "SUCCESS",
    })
    return project
