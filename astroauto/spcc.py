from __future__ import annotations
from pathlib import Path
import json
import re

from astropy.io import fits

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .deblur import make_deblur_task

def make_spcc_task(*, gradient_skipped: bool = False) -> dict:
    return {
        "task_id": "COLOR_CALIBRATION_SPCC",
        "title": "SPCC Color Calibration",
        "summary": (
            "Gradient를 생략했습니다. Linear 원본의 색을 SPCC로 보정하거나 다음 단계로 넘어갈 수 있습니다."
            if gradient_skipped else
            "Gradient Correction이 완료되었습니다. 다음 단계는 색 기준을 맞추는 SPCC입니다."
        ),
        "purpose": "별의 측광 색 정보를 이용해 RGB 밸런스를 보정합니다.",
        "current_status": "GRADIENT_SKIPPED / LINEAR" if gradient_skipped else "GRADIENT_CORRECTED / LINEAR",
        "recommendations": {
            "engine": "Siril 1.4.4 SPCC",
            "catalog": "Gaia DR3",
            "white_reference": "Average Spiral Galaxy 기본 시작값",
        },
        "cautions": [
            "SPCC 전에 plate solving과 센서/필터 정보 확인이 필요합니다.",
            "SPCC를 생략하면 측광 색상 보정은 수행되지 않습니다.",
        ],
        "completion_criteria": ["SPCC 적용 또는 명시적 생략", "색 균형 확인"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }


SPCC_LIST_TYPES = (
    "oscsensor", "monosensor", "redfilter", "greenfilter",
    "bluefilter", "oscfilter", "osclpf", "whiteref",
)

_SKIP_LOG_TEXT = (
    "welcome to siril",
    "supported file types",
    "setting cwd",
    "parallel processing",
    "color management",
    "jpeg icc",
    "the 'requires' command",
    "script execution finished",
    "total execution time",
    "closing pipes",
    "reading script",
    "executing script",
)

def _quote_arg(name: str, value: str) -> str:
    return f'"-{name}={value}"'

def _strip_log_prefix(line: str) -> str:
    line = line.replace("\x00", "").strip()
    if not line:
        return ""

    if line.lower().startswith("log:"):
        line = line.split(":", 1)[1].strip()

        # Some Siril builds/log formats prepend timestamps or numeric ticks.
        # Examples:
        #   2026:01:01: Sony IMX678
        #   1790699243: running command ...
        line = re.sub(r"^\d{4}:\d{2}:\d{2}:\s*", "", line)
        line = re.sub(r"^\d{8,}:\s*", "", line)

    return line

def _parse_spcc_list_stdout(stdout: str) -> list[str]:
    items = []
    for raw in stdout.splitlines():
        low = raw.lower()
        if any(token in low for token in _SKIP_LOG_TEXT):
            continue
        line = _strip_log_prefix(raw)
        if not line:
            continue
        if line.lower().startswith(("requires ", "spcc_list ", "close")):
            continue
        if line.startswith("-----"):
            continue
        # Avoid generic CLI lines that may remain after prefix stripping.
        low2 = line.lower()
        if any(token in low2 for token in ("siril 1.", "x86_64", "current working directory")):
            continue
        items.append(line)

    # Preserve order, drop duplicates.
    unique = []
    seen = set()
    for item in items:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique

def fetch_spcc_list(config: dict, list_type: str) -> tuple[list[str], str]:
    if list_type not in SPCC_LIST_TYPES:
        raise ValueError(f"지원하지 않는 SPCC list type: {list_type}")
    proc = run_script(config, [f"spcc_list {list_type}"])
    if proc.returncode != 0:
        raise SirilError(f"SPCC 목록 읽기 실패 ({list_type})\n{proc.stdout}\n{proc.stderr}")
    return _parse_spcc_list_stdout(proc.stdout or ""), proc.stdout or ""

def fetch_spcc_lists(config: dict, mode: str = "OSC") -> dict:
    mode = mode.upper()
    types = ["whiteref"]
    if mode == "OSC":
        types += ["oscsensor", "oscfilter", "osclpf"]
    else:
        types += ["monosensor", "redfilter", "greenfilter", "bluefilter"]

    result = {}
    raw_logs = {}
    for t in types:
        items, raw = fetch_spcc_list(config, t)
        result[t] = items
        raw_logs[t] = raw
    return {"lists": result, "raw_logs": raw_logs}

def inspect_wcs(path: Path) -> dict:
    path = Path(path)
    with fits.open(path, memmap=True) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), hdul[0])
        hdr = hdu.header

        ctype1 = hdr.get("CTYPE1")
        ctype2 = hdr.get("CTYPE2")
        crval1 = hdr.get("CRVAL1")
        crval2 = hdr.get("CRVAL2")
        has_scale = (
            hdr.get("CDELT1") is not None
            or hdr.get("CD1_1") is not None
            or hdr.get("PC1_1") is not None
        )
        solved = all(v is not None for v in (ctype1, ctype2, crval1, crval2)) and has_scale

        hints = {
            "ra": hdr.get("OBJCTRA", hdr.get("RA", crval1)),
            "dec": hdr.get("OBJCTDEC", hdr.get("DEC", crval2)),
            "focal_mm": hdr.get("FOCALLEN", hdr.get("FOCAL")),
            "pixel_um": hdr.get("XPIXSZ", hdr.get("PIXSIZE")),
        }
        return {
            "plate_solved": bool(solved),
            "ctype1": ctype1,
            "ctype2": ctype2,
            "crval1": crval1,
            "crval2": crval2,
            "hints": hints,
        }

def _current_linear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")
    if p.get("image_state", {}).get("linearity") != "LINEAR":
        raise ValueError("SPCC는 Linear 이미지에서만 실행합니다.")
    if p.get("image_state", {}).get("stretched") is True:
        raise ValueError("이미 Stretch된 입력에는 SPCC를 실행하지 않습니다.")
    return current

def _catalog_arg(catalog: str) -> str | None:
    c = str(catalog).upper()
    if c == "AUTO":
        return None
    if c == "GAIA_ONLINE":
        return "-catalog=gaia"
    if c == "LOCAL_GAIA":
        return "-catalog=localgaia"
    raise ValueError(f"지원하지 않는 SPCC catalog: {catalog}")

def bgtol_uses_siril_default(lower: float, upper: float) -> bool:
    return abs(float(lower) - (-2.8)) < 1e-12 and abs(float(upper) - 2.0) < 1e-12

def build_spcc_command(
    *,
    mode: str,
    sensor: str,
    osc_filter: str = "",
    osc_lpf: str = "",
    white_reference: str = "Average Spiral Galaxy",
    catalog: str = "AUTO",
    bgtol_lower: float = -2.8,
    bgtol_upper: float = 2.0,
    r_filter: str = "",
    g_filter: str = "",
    b_filter: str = "",
) -> str:
    mode = mode.upper()
    if not sensor.strip():
        raise ValueError("SPCC Sensor를 선택하세요.")
    if not white_reference.strip():
        raise ValueError("White Reference를 선택하세요.")

    args = []
    if mode == "OSC":
        args.append(_quote_arg("oscsensor", sensor.strip()))
        if osc_filter.strip():
            args.append(_quote_arg("oscfilter", osc_filter.strip()))
        if osc_lpf.strip():
            args.append(_quote_arg("osclpf", osc_lpf.strip()))
    elif mode == "MONO":
        args.append(_quote_arg("monosensor", sensor.strip()))
        if r_filter.strip():
            args.append(_quote_arg("rfilter", r_filter.strip()))
        if g_filter.strip():
            args.append(_quote_arg("gfilter", g_filter.strip()))
        if b_filter.strip():
            args.append(_quote_arg("bfilter", b_filter.strip()))
    else:
        raise ValueError("SPCC mode는 OSC 또는 MONO여야 합니다.")

    args.append(_quote_arg("whiteref", white_reference.strip()))

    cat = _catalog_arg(catalog)
    if cat:
        args.append(cat)

    lo = float(bgtol_lower)
    hi = float(bgtol_upper)
    if lo >= hi:
        raise ValueError("Background Tolerance lower는 upper보다 작아야 합니다.")

    # Siril 1.4.4 documents the defaults as -2.8 / +2.0.
    # On the tested Windows 1.4.4 CLI, explicitly passing
    #   -bgtol=-2.8,2
    # is rejected even though the documented syntax is valid.
    # For the default pair we therefore omit the option entirely and let
    # Siril use its own defaults. This is equivalent and avoids the parser issue.
    #
    # For custom values keep the documented syntax, but quote the whole argument
    # so it is passed as one token.
    if not (abs(lo - (-2.8)) < 1e-12 and abs(hi - 2.0) < 1e-12):
        args.append(f'"-bgtol={lo:g},{hi:g}"')

    return "spcc " + " ".join(args)

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def _platesolve_command_from_header(path: Path) -> str:
    wcs = inspect_wcs(path)
    if wcs["plate_solved"]:
        return "platesolve"

    hints = wcs["hints"]
    ra = hints.get("ra")
    dec = hints.get("dec")
    focal = hints.get("focal_mm")
    pix = hints.get("pixel_um")

    parts = ["platesolve"]
    if ra is not None and dec is not None:
        parts.append(f'"{ra},{dec}"')
    if focal is not None:
        try:
            parts.append(f"-focal={float(focal):g}")
        except Exception:
            pass
    if pix is not None:
        try:
            parts.append(f"-pixelsize={float(pix):g}")
        except Exception:
            pass
    return " ".join(parts)

def preview_spcc(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "spcc_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    linear_stem = temp_dir / f"{target}_spcc_preview_linear"
    jpg_stem = preview_dir / f"{target}_spcc_preview"

    spcc_cmd = build_spcc_command(**params)
    plate_cmd = _platesolve_command_from_header(current)

    commands = [
        "online",
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        plate_cmd,
        spcc_cmd,
        f'save "{normalize_siril_path(linear_stem)}"',
        "autostretch -linked",
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "SPCC 미리보기 생성 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    linear_preview = _find_saved(linear_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not linear_preview or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 SPCC 미리보기 파일을 찾지 못했습니다.\n"
            "Plate Solve 또는 SPCC가 실패했을 가능성이 있습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "display_preview": str(jpg),
        "linear_preview": str(linear_preview),
        "plate_solve_command": plate_cmd,
        "spcc_command": spcc_cmd,
        "parameters": params,
        "wcs_before": inspect_wcs(current),
    }
    (pdir / "logs" / "spcc_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    append_jsonl(pdir, {"event": "SPCC_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, linear_preview, meta

def apply_spcc(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 SPCC 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "04_color"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_04_spcc"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    spcc_cmd = build_spcc_command(**params)
    plate_cmd = _platesolve_command_from_header(current)

    commands = [
        "online",
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        plate_cmd,
        spcc_cmd,
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "SPCC 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 SPCC 결과 FITS를 찾지 못했습니다.\n"
            "Plate Solve 또는 SPCC가 실패했을 가능성이 있습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["current_file"] = str(output)
    p["current_state"] = "COLOR_CALIBRATED"
    p["image_state"]["color_calibrated"] = True
    p["image_state"]["linearity"] = "LINEAR"
    p["image_state"]["stretched"] = False
    p.setdefault("capture", {})["camera_type"] = str(params.get("mode", "UNKNOWN")).upper()
    p["capture"]["spcc"] = {
        "sensor": params.get("sensor"),
        "osc_filter": params.get("osc_filter"),
        "osc_lpf": params.get("osc_lpf"),
        "white_reference": params.get("white_reference"),
        "catalog": params.get("catalog"),
        "bgtol_lower": params.get("bgtol_lower"),
        "bgtol_upper": params.get("bgtol_upper"),
    }

    p["next_task"] = make_deblur_task()
    save_project(pdir, project)

    payload = {
        "event": "SPCC_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "plate_solve_command": plate_cmd,
        "spcc_command": spcc_cmd,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "spcc_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    return project, output, payload


def skip_spcc(project_dir: Path):
    """User-approved SPCC bypass. The image is not mislabeled color-calibrated."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    if (p.get("next_task") or {}).get("task_id") != "COLOR_CALIBRATION_SPCC":
        raise ValueError("현재 SPCC 단계에서만 생략할 수 있습니다.")
    current = _current_linear_file(project)
    p.setdefault("image_state", {})["color_calibrated"] = False
    p.setdefault("color_calibration", {})["skipped"] = True
    p["current_state"] = "COLOR_CALIBRATED"
    task = make_deblur_task()
    task["current_status"] = "SPCC_SKIPPED / LINEAR"
    task["summary"] = "SPCC를 적용하지 않은 Linear 이미지로 Restoration을 시작합니다."
    task["cautions"].append("SPCC 미적용: 색은 원본 센서/변환 상태 그대로입니다.")
    p["next_task"] = task
    save_project(pdir, project)
    append_jsonl(pdir, {"event": "SPCC_SKIP", "status": "USER_APPROVED",
                            "input_file": str(current)})
    return project
