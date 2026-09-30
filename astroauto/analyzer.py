from __future__ import annotations
from pathlib import Path
import copy
import json
import tempfile

from .project import load_project, save_project, find_project_fits
from .siril import get_siril_info, write_jsonmetadata
from .fits_analysis import analyze_pixels, read_header_summary, infer_linearity, load_siril_metadata
from .workflow import next_task_after_analysis
from .logging_utils import append_jsonl


def analyze_input_file(fits_path: Path, config: dict):
    """Analyze a FITS before a project exists.

    This is the intake analysis used by the GUI's separate [이미지 분석] step.
    It does not create or mutate a project.
    """
    fits_path = Path(fits_path)
    if not fits_path.exists():
        raise FileNotFoundError(fits_path)

    info = get_siril_info(config)
    with tempfile.TemporaryDirectory(prefix="astroauto_analysis_") as tmp:
        metadata_path = Path(tmp) / "siril_metadata.json"
        proc = write_jsonmetadata(config, fits_path, metadata_path)
        siril_meta = load_siril_metadata(metadata_path)

    analysis_cfg = config.get("analysis", {})
    pixel_stats = analyze_pixels(
        fits_path,
        max_samples=int(analysis_cfg.get("max_samples_per_channel", 1500000)),
        bins=int(analysis_cfg.get("histogram_bins", 2048)),
        clip_fraction=float(analysis_cfg.get("clip_fraction", 0.0001)),
    )
    header_summary, history = read_header_summary(fits_path)
    linearity = infer_linearity(history)

    report = {
        "input_file": str(fits_path.resolve()),
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
    diagnostics = {
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
        "siril_returncode": proc.returncode,
    }
    return report, diagnostics


def _ensure_project_structures(p: dict):
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
    p.setdefault("star_trail", {
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
    })
    p.setdefault("sessions", {
        "multi_session": False,
        "count": 1,
        "items": [],
        "classified": False,
    })
    p.setdefault("filter_groups", {
        "is_multifilter": False,
        "items": [],
        "classified": False,
    })
    p.setdefault("quality", {
        "checked": False,
        "metrics": {},
        "candidate_rejects": [],
    })
    p.setdefault("tracking_events", {
        "classified": False,
        "events": [],
    })
    p.setdefault("metadata", {"copyright": ""})


def apply_analysis_to_project(
    project_dir: Path,
    report: dict,
    diagnostics: dict | None = None,
):
    """Attach a previously completed intake analysis to a newly created project."""
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    p = project["project"]
    _ensure_project_structures(p)

    report_copy = copy.deepcopy(report)
    report_copy["project_input_file"] = str(find_project_fits(project_dir))
    report_path = project_dir / "logs" / "analysis_report.json"
    report_path.write_text(
        json.dumps(report_copy, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    p["runtime"]["siril_version"] = report.get("siril", {}).get("version")
    p["runtime"]["siril_executable"] = report.get("siril", {}).get("executable")
    p["current_state"] = "INPUT_ANALYZED"

    linearity = report.get("linearity_assessment") or {
        "status": "UNKNOWN", "confidence": 0.0
    }
    status = linearity.get("status", "UNKNOWN")
    p["image_state"]["linearity"] = status
    p["image_state"]["linearity_confidence"] = float(linearity.get("confidence", 0.0) or 0.0)
    p["image_state"]["stretched"] = (
        True if status == "NONLINEAR"
        else False if status == "LINEAR"
        else None
    )

    # Capture hints from FITS metadata. User-entered project identity fields stay authoritative.
    hdr = report.get("header") or {}
    if hdr.get("INSTRUME") and p["capture"].get("sensor", "UNKNOWN") == "UNKNOWN":
        p["capture"]["sensor"] = str(hdr["INSTRUME"])
    if hdr.get("FILTER") and p["capture"]["filter"].get("name", "UNKNOWN") == "UNKNOWN":
        p["capture"]["filter"]["name"] = str(hdr["FILTER"])
    if hdr.get("EXPTIME") is not None:
        p["capture"].setdefault("exposure", {})["single_sec"] = hdr["EXPTIME"]
    elif hdr.get("EXPOSURE") is not None:
        p["capture"].setdefault("exposure", {})["single_sec"] = hdr["EXPOSURE"]
    if hdr.get("GAIN") is not None:
        p["capture"]["gain"] = hdr["GAIN"]
    if hdr.get("TELESCOP"):
        p["capture"]["telescope"] = str(hdr["TELESCOP"])

    task = next_task_after_analysis(project)
    p["next_task"] = task
    save_project(project_dir, project)

    diagnostics = diagnostics or {}
    append_jsonl(project_dir, {
        "event": "ANALYZE_INPUT",
        "status": "SUCCESS",
        "input_file": report.get("input_file"),
        "project_input_file": report_copy.get("project_input_file"),
        "siril_version": report.get("siril", {}).get("version"),
        "linearity": linearity,
        "analysis_report": str(report_path),
        "siril_stdout": diagnostics.get("siril_stdout", ""),
        "siril_stderr": diagnostics.get("siril_stderr", ""),
    })
    return project, report_copy, task


def analyze_project(project_dir: Path, config: dict):
    """Backward-compatible project-first analysis path used by CLI/older flows."""
    project_dir = Path(project_dir)
    fits_path = find_project_fits(project_dir)
    report, diagnostics = analyze_input_file(fits_path, config)
    return apply_analysis_to_project(project_dir, report, diagnostics)


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
