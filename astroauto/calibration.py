from __future__ import annotations
from pathlib import Path
from statistics import median
from typing import Any
import json
import shutil
import tempfile

from astropy.io import fits

from .project import load_project, save_project
from .utils import is_fits
from .logging_utils import append_jsonl
from .input_formats import RAW_EXTENSIONS, describe_input, normalize_to_fits
from .execution import check_cancelled, emit_log
from .workflow import next_task_after_analysis

FRAME_FOLDERS = {
    "dark": "calibration/dark",
    "bias": "calibration/bias",
    "flat": "calibration/flat",
    "dark_flat": "calibration/dark_flat",
}

GAIN_KEYS = ("GAIN", "EGAIN", "CCDGAIN")
ISO_KEYS = ("ISOSPEED", "ISO", "ISOSPEEDRATINGS")
TEMP_KEYS = ("CCD-TEMP", "CCDTEMP", "SENSOR_TEMP", "TEMP")
FILTER_KEYS = ("FILTER", "FILTERID")
BAYER_KEYS = ("BAYERPAT", "BAYERPATTERN")

def _first(header, keys):
    for key in keys:
        if key in header and header.get(key) not in (None, ""):
            return header.get(key)
    return None

def _float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None

def read_frame_metadata(path: Path) -> dict[str, Any]:
    # Header-only inspection: never allocate a 26MP x 3 pixel array simply
    # to compare dimensions. A 16-bit unsigned Siril FITS may have BZERO.
    with fits.open(path, memmap=False, do_not_scale_image_data=True) as hdul:
        hdu = next((h for h in hdul if h.header.get("NAXIS", 0) >= 2), None)
        if hdu is None:
            raise ValueError(f"이미지 HDU가 없습니다: {path}")
        hdr = hdul[0].header.copy()
        hdr.update(hdu.header)
        naxis = int(hdu.header["NAXIS"])
        shape = [int(hdu.header[f"NAXIS{i}"]) for i in range(naxis, 0, -1)]

        exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
        return {
            "file": str(path),
            "shape": shape,
            "exposure_sec": _float_or_none(exposure),
            "gain": _float_or_none(_first(hdr, GAIN_KEYS)),
            "iso": _float_or_none(_first(hdr, ISO_KEYS)),
            "temperature_c": _float_or_none(_first(hdr, TEMP_KEYS)),
            "filter": str(_first(hdr, FILTER_KEYS)) if _first(hdr, FILTER_KEYS) is not None else None,
            "bayer_pattern": str(_first(hdr, BAYER_KEYS)) if _first(hdr, BAYER_KEYS) is not None else None,
            "instrume": str(hdr.get("INSTRUME")) if hdr.get("INSTRUME") is not None else None,
            "binning": [hdr.get("XBINNING"), hdr.get("YBINNING")] if hdr.get("XBINNING") is not None and hdr.get("YBINNING") is not None else None,
            "telescope": str(hdr.get("TELESCOP")) if hdr.get("TELESCOP") is not None else None,
        }


def import_calibration_folder(project_dir: Path, frame_type: str, source_dir: Path) -> dict:
    """Copy original FITS/camera RAW frames without changing source or overwriting.

    Import is deliberately separate from analysis: users may also populate
    calibration/{type} themselves before pressing [프레임 검사].
    """
    if frame_type not in FRAME_FOLDERS:
        raise ValueError(f"지원하지 않는 프레임 종류: {frame_type}")
    project_dir, source_dir = Path(project_dir), Path(source_dir)
    project = load_project(project_dir)
    current_task = (project["project"].get("next_task") or {}).get("task_id")
    if current_task not in ("CHECK_CALIBRATION_FRAMES", "REVIEW_CALIBRATION_FRAMES"):
        raise ValueError("캘리브레이션 검사 단계에서만 프레임을 등록할 수 있습니다. 후처리 중인 프로젝트는 변경하지 않습니다.")
    if not source_dir.is_dir():
        raise NotADirectoryError(source_dir)
    dest = project_dir / FRAME_FOLDERS[frame_type]
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in source_dir.rglob("*") if p.is_file() and (is_fits(p) or p.suffix.lower() in RAW_EXTENSIONS))
    imported, existing = 0, 0
    for source in files:
        check_cancelled()
        if source.resolve() == dest.resolve() or dest.resolve() in source.resolve().parents:
            existing += 1
            continue
        target = dest / source.name
        if target.exists():
            # Identical source is not imported again. A different file with the
            # same name is renamed, never overwritten.
            if target.stat().st_size == source.stat().st_size and _same_content(source, target):
                existing += 1
                continue
            counter = 2
            suffix = ".fits.fz" if source.name.lower().endswith(".fits.fz") else source.suffix
            stem = source.name[:-len(suffix)]
            while target.exists():
                target = dest / f"{stem}_{counter:02d}{suffix}"
                counter += 1
        shutil.copy2(source, target)
        imported += 1
    check_cancelled()
    if imported:
        project = load_project(project_dir)
        cal = project["project"].setdefault("calibration", {})
        cal["checked"] = False
        cal["resolution"] = "PENDING"
        project["project"]["next_task"] = next_task_after_analysis(project)
        save_project(project_dir, project)
    append_jsonl(project_dir, {"event": "CALIBRATION_IMPORT", "frame_type": frame_type,
                               "imported": imported, "existing": existing, "status": "SUCCESS"})
    return {"frame_type": frame_type, "imported": imported, "existing": existing, "path": str(dest)}


def _same_content(first: Path, second: Path) -> bool:
    with first.open("rb") as a, second.open("rb") as b:
        while True:
            aa, bb = a.read(1024 * 1024), b.read(1024 * 1024)
            if aa != bb:
                return False
            if not aa:
                return True

def _med(values):
    vals = [x for x in values if x is not None]
    return float(median(vals)) if vals else None

def summarize_folder(path: Path, cfg: dict | None = None, temp_root: Path | None = None) -> dict:
    files = sorted([p for p in path.rglob("*") if p.is_file() and (is_fits(p) or p.suffix.lower() in RAW_EXTENSIONS)])
    metas = []
    errors = []
    for f in files:
        check_cancelled()
        try:
            if f.suffix.lower() in RAW_EXTENSIONS:
                if cfg is None:
                    raise ValueError("카메라 RAW 프레임 검사는 Siril 설정이 필요합니다.")
                with tempfile.TemporaryDirectory(prefix="cal_check_", dir=str(temp_root) if temp_root else None) as td:
                    normalized = Path(td) / "inspection.fits"
                    emit_log(f"{path.name}: {f.name} RAW 정보 읽는 중")
                    result = normalize_to_fits(f, cfg, destination=normalized)
                    meta = read_frame_metadata(Path(result["analysis_file"]))
                    meta["file"] = str(f)
                    meta["source_family"] = "RAW"
                    meta["inspection_method"] = "SIRIL_RAW_DEBAYER_TEMPORARY"
            else:
                meta = read_frame_metadata(f)
                meta["source_family"] = "FITS"
                meta["inspection_method"] = "FITS_HEADER"
            metas.append(meta)
        except Exception as e:
            errors.append({"file": str(f), "error": str(e)})

    return {
        "available": len(metas) > 0,
        "count": len(metas),
        "candidate_count": len(files),
        "path": str(path),
        "summary": {
            "exposure_sec_median": _med([m["exposure_sec"] for m in metas]),
            "gain_median": _med([m["gain"] for m in metas]),
            "iso_median": _med([m.get("iso") for m in metas]),
            "temperature_c_median": _med([m["temperature_c"] for m in metas]),
            "filters": sorted({m["filter"] for m in metas if m["filter"]}),
            "bayer_patterns": sorted({m["bayer_pattern"] for m in metas if m["bayer_pattern"]}),
            "shapes": [list(x) for x in sorted({tuple(m["shape"]) for m in metas if m["shape"]})],
            "instruments": sorted({m["instrume"] for m in metas if m["instrume"]}),
        },
        "files": metas,
        "errors": errors,
    }

def _near(a, b, rel_tol, abs_tol):
    if a is None or b is None:
        return None
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b), 1e-12))

def _same_or_unknown(a, b):
    if a is None or b is None:
        return None
    return str(a).strip().lower() == str(b).strip().lower()

def _shape_ok(light_shape, frame_shapes):
    if not light_shape or not frame_shapes:
        return None
    return all(list(s) == list(light_shape) for s in frame_shapes)


def _all_checks(results: list[bool | None]) -> bool | None:
    if False in results:
        return False
    if None in results or not results:
        return None
    return True


def _values_equal(light: dict, files: list[dict], key: str) -> bool | None:
    return _all_checks([_same_or_unknown(light.get(key), m.get(key)) for m in files])


def _numeric_matches(light: dict, files: list[dict], key: str, rel: float, abs_tol: float) -> bool | None:
    return _all_checks([_near(light.get(key), m.get(key), rel, abs_tol) for m in files])


def _identity_checks(light: dict, frames: dict) -> dict:
    files = frames["files"]
    return {
        "dimensions": _shape_ok(light.get("shape"), frames["summary"].get("shapes")),
        "camera": _values_equal(light, files, "instrume"),
        "binning": _all_checks([_same_or_unknown(light.get("binning"), m.get("binning")) for m in files]),
    }


def _gain_iso_checks(light: dict, frames: dict, gain_tolerance: float) -> dict:
    # ISO and FITS Gain are distinct properties, not interchangeable numbers.
    files = frames["files"]
    return {
        "gain": _numeric_matches(light, files, "gain", 0.0, gain_tolerance),
        "iso": _numeric_matches(light, files, "iso", 0.0, 0.0),
    }

def compare_to_light(light_meta: dict, scans: dict, cfg: dict) -> dict:
    ccfg = cfg.get("calibration", {}).get("compatibility", {})
    result = {}

    dark = scans["dark"]
    dcfg = ccfg.get("dark", {})
    if dark["available"]:
        checks = {
            **_identity_checks(light_meta, dark),
            **_gain_iso_checks(light_meta, dark, float(dcfg.get("gain_tolerance", 0.0))),
            "exposure": _numeric_matches(
                light_meta, dark["files"], "exposure_sec",
                float(dcfg.get("exposure_relative_tolerance", 0.05)),
                float(dcfg.get("exposure_absolute_tolerance_sec", 0.5))
            ),
            "temperature": _numeric_matches(
                light_meta, dark["files"], "temperature_c",
                0.0, float(dcfg.get("temperature_tolerance_c", 3.0))
            ),
        }
        result["dark"] = _decision(checks, optional_unknown={"temperature", "gain", "iso", "camera", "binning"})
        result["dark"]["checks"] = checks
    else:
        result["dark"] = {"status": "MISSING", "checks": {}}

    flat = scans["flat"]
    if flat["available"]:
        checks = {
            **_identity_checks(light_meta, flat),
            "filter": _values_equal(light_meta, flat["files"], "filter"),
            "bayer_pattern": _values_equal(light_meta, flat["files"], "bayer_pattern"),
            "telescope": _values_equal(light_meta, flat["files"], "telescope"),
        }
        result["flat"] = _decision(checks, optional_unknown={"filter", "bayer_pattern", "camera", "binning", "telescope"})
        result["flat"]["checks"] = checks
    else:
        result["flat"] = {"status": "MISSING", "checks": {}}

    bias = scans["bias"]
    if bias["available"]:
        bcfg = ccfg.get("bias", {})
        checks = {
            **_identity_checks(light_meta, bias),
            **_gain_iso_checks(light_meta, bias, float(bcfg.get("gain_tolerance", 0.0))),
        }
        result["bias"] = _decision(checks, optional_unknown={"gain", "iso", "camera", "binning"})
        result["bias"]["checks"] = checks
    else:
        result["bias"] = {"status": "MISSING", "checks": {}}

    dark_flat = scans["dark_flat"]
    if dark_flat["available"]:
        dcfg = ccfg.get("dark_flat", {})
        flat_exp = scans["flat"]["summary"].get("exposure_sec_median") if scans["flat"]["available"] else None
        checks = {
            **_identity_checks(light_meta, dark_flat),
            **_gain_iso_checks(light_meta, dark_flat, float(dcfg.get("gain_tolerance", 0.0))),
            "flat_exposure": _all_checks([_near(flat_exp, m.get("exposure_sec"),
                    float(dcfg.get("exposure_relative_tolerance", 0.05)),
                    float(dcfg.get("exposure_absolute_tolerance_sec", 0.2))) for m in dark_flat["files"]]),
            "temperature": _numeric_matches(light_meta, dark_flat["files"], "temperature_c", 0.0,
                    float(dcfg.get("temperature_tolerance_c", 3.0))),
        }
        result["dark_flat"] = _decision(checks, optional_unknown={"gain", "iso", "camera", "binning", "temperature", "flat_exposure"})
        result["dark_flat"]["checks"] = checks
    else:
        result["dark_flat"] = {"status": "MISSING", "checks": {}}

    return result

def _decision(checks: dict, optional_unknown: set[str]) -> dict:
    failures = [k for k, v in checks.items() if v is False]
    if failures:
        return {"status": "INCOMPATIBLE", "failures": failures}
    unknown_required = [k for k, v in checks.items() if v is None and k not in optional_unknown]
    if unknown_required:
        return {"status": "REVIEW", "unknown_required": unknown_required}
    if any(v is None for v in checks.values()):
        return {"status": "COMPATIBLE_WITH_UNKNOWNS"}
    return {"status": "COMPATIBLE"}

def recommend_calibration(scans: dict, compatibility: dict, input_status: str) -> dict:
    if input_status == "PRECALIBRATED":
        return {
            "action": "DO_NOT_APPLY",
            "summary": "이미 캘리브레이션된 입력으로 확인되었습니다. Dark/Flat/Bias/Dark-flat을 다시 적용하지 않습니다.",
            "use": [],
        }

    available = {k for k, v in scans.items() if v["available"]}
    use = []
    warnings = []

    if "dark" in available and compatibility["dark"]["status"].startswith("COMPATIBLE"):
        use.append("dark")
    elif "dark" not in available:
        warnings.append("Dark 없음: 열신호/고정 패턴 보정 효과가 제한될 수 있습니다.")

    if "flat" in available and compatibility["flat"]["status"].startswith("COMPATIBLE"):
        use.append("flat")
        if "dark_flat" in available and compatibility["dark_flat"]["status"].startswith("COMPATIBLE"):
            use.append("dark_flat")
        elif "bias" in available and compatibility["bias"]["status"].startswith("COMPATIBLE"):
            use.append("bias")
        else:
            warnings.append("Flat은 있으나 호환되는 Bias/Dark-flat 조합이 확인되지 않았습니다. 센서/워크플로에 따라 사용자 확인이 필요합니다.")
    elif "flat" not in available:
        warnings.append("Flat 없음: 비네팅/먼지 그림자 보정이 제한될 수 있습니다.")
        if "bias" in available:
            warnings.append("Bias만 단독으로 있다고 해서 자동 적용하지 않습니다.")

    incompatible = [k for k, v in compatibility.items() if v["status"] == "INCOMPATIBLE"]
    if incompatible:
        warnings.append("호환성 불일치: " + ", ".join(incompatible))

    return {
        "action": "APPLY_SELECTED" if use else "REVIEW_OR_SKIP",
        "summary": "감지된 캘리브레이션 프레임을 Light 조건과 비교했습니다.",
        "use": use,
        "warnings": warnings,
    }

def scan_project_calibration(project_dir: Path, cfg: dict):
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    current_task = (project["project"].get("next_task") or {}).get("task_id")
    if current_task not in ("CHECK_CALIBRATION_FRAMES", "REVIEW_CALIBRATION_FRAMES"):
        raise ValueError("현재 프로젝트는 캘리브레이션 검사 단계가 아닙니다. 기존 처리 결과를 되돌리지 않습니다.")
    current = Path(project["project"]["current_file"])
    light_meta = read_frame_metadata(current)
    light_meta["source_family"] = project["project"].get("input", {}).get("source_family") or "FITS"
    light_meta["debayered"] = bool(project["project"].get("input", {}).get("normalization", {}).get("debayered"))

    temp_root = project_dir / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    scans = {
        key: summarize_folder(project_dir / rel, cfg, temp_root=temp_root)
        for key, rel in FRAME_FOLDERS.items()
    }
    check_cancelled()
    compatibility = compare_to_light(light_meta, scans, cfg)
    # Failed inspections must not masquerade as missing calibration frames.
    for key, scan in scans.items():
        if scan["errors"]:
            compatibility[key] = {
                "status": "REVIEW", "checks": {}, "unknown_required": ["unreadable_frames"],
            }
    input_status = project["project"]["calibration"].get("input_status", "UNKNOWN")
    recommendation = recommend_calibration(scans, compatibility, input_status)
    recommendation["warnings"] = list(recommendation.get("warnings", []))
    if light_meta["debayered"] and light_meta["source_family"] == "RAW":
        recommendation["warnings"].append(
            "원본 RAW는 이미 Debayer된 RGB FITS로 변환되었습니다. 원본 CFA용 Dark/Flat을 "
            "검사만 하며 이 파일에 자동 보정하지 않습니다. 정확한 원본 RAW 보정은 Debayer 이전에 해야 합니다."
        )
    if any(s["errors"] for s in scans.values()):
        recommendation["warnings"].append("읽지 못한 프레임이 있습니다. 상세 보고서를 확인하고 재검사하세요.")
    recommendation["action"] = "REVIEW_ONLY"

    cal = project["project"]["calibration"]
    cal["checked"] = True
    cal["resolution"] = "PENDING"
    cal["frames"] = {
        k: {
            "available": v["available"],
            "path": str(Path(v["path"]).relative_to(project_dir)),
            "count": v["count"],
            "candidate_count": v["candidate_count"],
            "summary": v["summary"],
            "errors": v["errors"],
        }
        for k, v in scans.items()
    }
    cal["compatibility"] = compatibility
    cal["recommended_action"] = recommendation["action"]
    cal["recommendation"] = recommendation

    if project["project"]["current_state"] in ("INPUT_STAGE_CONFIRMED", "INPUT_ANALYZED"):
        project["project"]["current_state"] = "CALIBRATION_CHECKED"

    project["project"]["next_task"] = next_task_after_analysis(project)

    save_project(project_dir, project)

    report = {
        "light_reference": light_meta,
        "frames": scans,
        "compatibility": compatibility,
        "recommendation": recommendation,
    }

    report_path = project_dir / "logs" / "calibration_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    append_jsonl(project_dir, {
        "event": "CALIBRATION_CHECK",
        "status": "SUCCESS",
        "report": str(report_path),
        "recommendation": recommendation,
    })

    return project, report


def skip_project_calibration(project_dir: Path):
    """Explicit user choice. No pixel or source file is modified."""
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    p = project["project"]
    current_task = (p.get("next_task") or {}).get("task_id")
    if current_task not in ("CHECK_CALIBRATION_FRAMES", "REVIEW_CALIBRATION_FRAMES"):
        raise ValueError("현재 단계에서는 캘리브레이션을 생략할 수 없습니다.")
    if p.get("input_stage", {}).get("source_stage") != "SINGLE_LIGHT":
        raise ValueError("이 경로는 단일 이미지 전용입니다. 시퀀스는 별도 전처리가 필요합니다.")
    p.setdefault("calibration", {})
    p["calibration"]["checked"] = bool(p["calibration"].get("checked", False))
    p["calibration"]["resolution"] = "SKIPPED"
    p["calibration"]["recommended_action"] = "USER_APPROVED_SKIP"
    p["current_state"] = "CALIBRATION_SKIPPED"
    p["next_task"] = next_task_after_analysis(project)
    save_project(project_dir, project)
    append_jsonl(project_dir, {"event": "CALIBRATION_SKIP", "status": "USER_APPROVED",
                               "from_task": current_task,
                               "reason": "Single Light calibration deferred to original RAW/CFA workflow"})
    return project
