from __future__ import annotations
from pathlib import Path
from statistics import median
from typing import Any

from astropy.io import fits

from .project import load_project, save_project
from .utils import is_fits
from .logging_utils import append_jsonl

FRAME_FOLDERS = {
    "dark": "calibration/dark",
    "bias": "calibration/bias",
    "flat": "calibration/flat",
    "dark_flat": "calibration/dark_flat",
}

GAIN_KEYS = ("GAIN", "EGAIN", "CCDGAIN")
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
    with fits.open(path, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), hdul[0])
        hdr = hdu.header
        data = getattr(hdu, "data", None)
        shape = list(data.shape) if data is not None else None

        exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
        return {
            "file": str(path),
            "shape": shape,
            "exposure_sec": _float_or_none(exposure),
            "gain": _float_or_none(_first(hdr, GAIN_KEYS)),
            "temperature_c": _float_or_none(_first(hdr, TEMP_KEYS)),
            "filter": str(_first(hdr, FILTER_KEYS)) if _first(hdr, FILTER_KEYS) is not None else None,
            "bayer_pattern": str(_first(hdr, BAYER_KEYS)) if _first(hdr, BAYER_KEYS) is not None else None,
            "instrume": str(hdr.get("INSTRUME")) if hdr.get("INSTRUME") is not None else None,
        }

def _med(values):
    vals = [x for x in values if x is not None]
    return float(median(vals)) if vals else None

def summarize_folder(path: Path) -> dict:
    files = sorted([p for p in path.rglob("*") if p.is_file() and is_fits(p)])
    metas = []
    errors = []
    for f in files:
        try:
            metas.append(read_frame_metadata(f))
        except Exception as e:
            errors.append({"file": str(f), "error": str(e)})

    return {
        "available": len(metas) > 0,
        "count": len(metas),
        "path": str(path),
        "summary": {
            "exposure_sec_median": _med([m["exposure_sec"] for m in metas]),
            "gain_median": _med([m["gain"] for m in metas]),
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

def compare_to_light(light_meta: dict, scans: dict, cfg: dict) -> dict:
    ccfg = cfg.get("calibration", {}).get("compatibility", {})
    result = {}

    dark = scans["dark"]
    dcfg = ccfg.get("dark", {})
    if dark["available"]:
        ds = dark["summary"]
        checks = {
            "dimensions": _shape_ok(light_meta.get("shape"), ds.get("shapes")),
            "exposure": _near(
                light_meta.get("exposure_sec"), ds.get("exposure_sec_median"),
                float(dcfg.get("exposure_relative_tolerance", 0.05)),
                float(dcfg.get("exposure_absolute_tolerance_sec", 0.5))
            ),
            "gain": _near(
                light_meta.get("gain"), ds.get("gain_median"),
                0.0, float(dcfg.get("gain_tolerance", 0.0))
            ),
            "temperature": _near(
                light_meta.get("temperature_c"), ds.get("temperature_c_median"),
                0.0, float(dcfg.get("temperature_tolerance_c", 3.0))
            ),
        }
        result["dark"] = _decision(checks, optional_unknown={"temperature"})
        result["dark"]["checks"] = checks
    else:
        result["dark"] = {"status": "MISSING", "checks": {}}

    flat = scans["flat"]
    if flat["available"]:
        fs = flat["summary"]
        filter_matches = None
        if light_meta.get("filter") and fs.get("filters"):
            filter_matches = all(str(x).lower() == str(light_meta["filter"]).lower() for x in fs["filters"])
        bayer_matches = None
        if light_meta.get("bayer_pattern") and fs.get("bayer_patterns"):
            bayer_matches = all(str(x).lower() == str(light_meta["bayer_pattern"]).lower() for x in fs["bayer_patterns"])
        checks = {
            "dimensions": _shape_ok(light_meta.get("shape"), fs.get("shapes")),
            "filter": filter_matches,
            "bayer_pattern": bayer_matches,
        }
        result["flat"] = _decision(checks, optional_unknown={"filter", "bayer_pattern"})
        result["flat"]["checks"] = checks
    else:
        result["flat"] = {"status": "MISSING", "checks": {}}

    bias = scans["bias"]
    if bias["available"]:
        bs = bias["summary"]
        bcfg = ccfg.get("bias", {})
        checks = {
            "dimensions": _shape_ok(light_meta.get("shape"), bs.get("shapes")),
            "gain": _near(light_meta.get("gain"), bs.get("gain_median"), 0.0, float(bcfg.get("gain_tolerance", 0.0))),
        }
        result["bias"] = _decision(checks, optional_unknown={"gain"})
        result["bias"]["checks"] = checks
    else:
        result["bias"] = {"status": "MISSING", "checks": {}}

    dark_flat = scans["dark_flat"]
    if dark_flat["available"]:
        dfs = dark_flat["summary"]
        dcfg = ccfg.get("dark_flat", {})
        flat_exp = scans["flat"]["summary"].get("exposure_sec_median") if scans["flat"]["available"] else None
        checks = {
            "dimensions": _shape_ok(light_meta.get("shape"), dfs.get("shapes")),
            "flat_exposure": _near(
                flat_exp, dfs.get("exposure_sec_median"),
                float(dcfg.get("exposure_relative_tolerance", 0.05)),
                float(dcfg.get("exposure_absolute_tolerance_sec", 0.2))
            ),
            "gain": _near(
                light_meta.get("gain"), dfs.get("gain_median"),
                0.0, float(dcfg.get("gain_tolerance", 0.0))
            ),
        }
        result["dark_flat"] = _decision(checks, optional_unknown={"gain", "flat_exposure"})
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
    current = Path(project["project"]["current_file"])
    light_meta = read_frame_metadata(current)

    scans = {
        key: summarize_folder(project_dir / rel)
        for key, rel in FRAME_FOLDERS.items()
    }
    compatibility = compare_to_light(light_meta, scans, cfg)
    input_status = project["project"]["calibration"].get("input_status", "UNKNOWN")
    recommendation = recommend_calibration(scans, compatibility, input_status)

    cal = project["project"]["calibration"]
    cal["checked"] = True
    cal["frames"] = {
        k: {
            "available": v["available"],
            "path": str(Path(v["path"]).relative_to(project_dir)),
            "count": v["count"],
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

    save_project(project_dir, project)

    report = {
        "light_reference": light_meta,
        "frames": scans,
        "compatibility": compatibility,
        "recommendation": recommendation,
    }

    report_path = project_dir / "logs" / "calibration_report.json"
    import json
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    append_jsonl(project_dir, {
        "event": "CALIBRATION_CHECK",
        "status": "SUCCESS",
        "report": str(report_path),
        "recommendation": recommendation,
    })

    return project, report
