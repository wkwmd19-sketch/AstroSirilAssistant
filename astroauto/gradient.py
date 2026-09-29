from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl

DEFAULT_GRADIENT_PARAMS = {
    "method": "RBF",
    "samples": 20,
    "tolerance": 1.0,
    "smooth": 0.5,
    "dither": False,
}

def _validate_params(samples: int, tolerance: float, smooth: float):
    samples = int(samples)
    tolerance = float(tolerance)
    smooth = float(smooth)

    if samples < 2 or samples > 200:
        raise ValueError("Samples는 2~200 범위로 입력하세요.")
    if tolerance <= 0 or tolerance > 20:
        raise ValueError("Tolerance는 0보다 크고 20 이하로 입력하세요.")
    if smooth < 0 or smooth > 1:
        raise ValueError("Smooth는 0~1 범위로 입력하세요.")
    return samples, tolerance, smooth

def _current_linear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")

    if p.get("image_state", {}).get("linearity") != "LINEAR":
        raise ValueError("Gradient Correction은 Linear로 확인된 입력에서만 실행합니다.")
    if p.get("image_state", {}).get("stretched") is True:
        raise ValueError("이미 Stretch된 입력에는 이 초기 Gradient 경로를 실행하지 않습니다.")
    return current

def _subsky_command(samples: int, tolerance: float, smooth: float, dither: bool):
    cmd = (
        f"subsky -rbf -samples={samples} "
        f"-tolerance={tolerance:g} -smooth={smooth:g}"
    )
    if dither:
        cmd += " -dither"
    return cmd

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def preview_gradient(
    project_dir: Path,
    config: dict,
    *,
    samples: int = 20,
    tolerance: float = 1.0,
    smooth: float = 0.5,
    dither: bool = False,
):
    samples, tolerance, smooth = _validate_params(samples, tolerance, smooth)
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "gradient_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    linear_stem = temp_dir / f"{target}_gradient_preview_linear"
    jpg_stem = preview_dir / f"{target}_gradient_preview"

    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        _subsky_command(samples, tolerance, smooth, dither),
        f'save "{normalize_siril_path(linear_stem)}"',
        # For preview only. The saved working FITS above remains Linear.
        "autostretch -linked",
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Gradient 미리보기 생성 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    linear_preview = _find_saved(linear_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not linear_preview or not jpg.exists():
        raise SirilError(
            "Siril 명령은 종료되었지만 Gradient 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "linear_preview": str(linear_preview),
        "display_preview": str(jpg),
        "parameters": {
            "method": "RBF",
            "samples": samples,
            "tolerance": tolerance,
            "smooth": smooth,
            "dither": bool(dither),
        },
        "note": "JPEG는 확인용 AutoStretch 미리보기이며 실제 Gradient 결과 FITS는 Linear입니다.",
    }
    meta_path = pdir / "logs" / "gradient_preview.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    append_jsonl(pdir, {
        "event": "GRADIENT_PREVIEW",
        "status": "SUCCESS",
        **meta,
    })
    return jpg, linear_preview, meta

def apply_gradient(
    project_dir: Path,
    config: dict,
    *,
    samples: int = 20,
    tolerance: float = 1.0,
    smooth: float = 0.5,
    dither: bool = False,
    confirmed: bool = False,
):
    if not confirmed:
        raise PermissionError("실제 Gradient 적용에는 사용자 승인이 필요합니다.")

    samples, tolerance, smooth = _validate_params(samples, tolerance, smooth)
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "03_gradient"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_03_gradient"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        _subsky_command(samples, tolerance, smooth, dither),
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Gradient Correction 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 Gradient 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    params = {
        "method": "RBF",
        "samples": samples,
        "tolerance": tolerance,
        "smooth": smooth,
        "dither": bool(dither),
    }

    p["current_file"] = str(output)
    p["current_state"] = "GRADIENT_CORRECTED"
    p["image_state"]["gradient_corrected"] = True
    p["image_state"]["linearity"] = "LINEAR"
    p["image_state"]["stretched"] = False
    p["next_task"] = {
        "task_id": "COLOR_CALIBRATION_SPCC",
        "title": "SPCC Color Calibration",
        "summary": "Gradient Correction이 완료되었습니다. 다음 단계는 색 기준을 맞추는 SPCC입니다.",
        "purpose": "별의 측광 색 정보를 이용해 RGB 밸런스를 보정합니다.",
        "current_status": "GRADIENT_CORRECTED / LINEAR",
        "recommendations": {
            "engine": "Siril 1.4.4 SPCC",
            "catalog": "Gaia DR3",
            "white_reference": "Average Spiral Galaxy 기본 시작값",
        },
        "cautions": [
            "SPCC 전에 plate solving과 센서/필터 정보 확인이 필요합니다.",
        ],
        "completion_criteria": [
            "SPCC 성공",
            "색 균형 확인",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }
    save_project(pdir, project)

    log_payload = {
        "event": "GRADIENT_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, log_payload)

    report_path = pdir / "logs" / "gradient_apply.json"
    report_path.write_text(
        json.dumps(log_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )
    return project, output, log_payload
