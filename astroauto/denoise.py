from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .deblur import make_deblur_task

def make_denoise_task() -> dict:
    return {
        "task_id": "DENOISE",
        "title": "Noise Reduction / Denoise",
        "summary": "SPCC가 끝난 Linear 이미지의 노이즈를 줄입니다.",
        "purpose": "은하/성운의 미세 구조를 보존하면서 배경과 색 노이즈를 줄여 Stretch 전에 이미지를 정리합니다.",
        "current_status": "COLOR_CALIBRATED / LINEAR",
        "recommendations": {
            "engine": "Siril 1.4.4 denoise",
            "modulation": 1.0,
            "cosmetic_correction": "ON",
            "da3d": "OFF",
            "independent_channels": "OFF",
        },
        "cautions": [
            "스택 이미지에서는 VST를 기본으로 사용하지 않습니다.",
            "미세 구조와 별이 과도하게 부드러워지지 않는지 미리보기로 확인하세요.",
        ],
        "completion_criteria": [
            "노이즈 감소",
            "미세 구조 보존",
            "Linear 상태 유지",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def make_post_denoise_task(skipped: bool = False) -> dict:
    return {
        "task_id": "POST_DENOISE_REVIEW",
        "title": "Denoise 완료 / 다음 처리 준비" if not skipped else "Denoise 건너뜀 / 다음 처리 준비",
        "summary": (
            "Denoise가 완료되었습니다. 다음 구현 단계는 Deblur 또는 GHS Stretch입니다."
            if not skipped else
            "Denoise를 건너뛰었습니다. 다음 구현 단계는 Deblur 또는 GHS Stretch입니다."
        ),
        "purpose": "Linear 상태에서 디테일 복원 또는 초기 Stretch로 이어갈 준비를 합니다.",
        "current_status": "DENOISED / LINEAR" if not skipped else "COLOR_CALIBRATED / LINEAR",
        "recommendations": {
            "next": "Deblur (Richardson-Lucy) 또는 GHS Stretch",
            "status": "다음 구현 단계",
        },
        "cautions": [
            "아직 실제 Stretch를 적용하지 않았습니다.",
            "Deblur는 PSF와 반복 횟수에 따라 링잉/과샤픈이 생길 수 있어 별도 미리보기가 필요합니다.",
        ],
        "completion_criteria": ["다음 처리 선택"],
        "actions": ["CONFIRM"],
    }

def migrate_post_spcc_task(project_dir: Path):
    """Migrate an existing v0.5.x COLOR_CALIBRATED project to the v0.6 Denoise task."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    if p.get("current_state") == "COLOR_CALIBRATED":
        task = p.get("next_task") or {}
        if task.get("task_id") in (None, "POST_SPCC_REVIEW"):
            p["next_task"] = make_denoise_task()
            save_project(pdir, project)
    return project

def _current_linear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")
    if p.get("image_state", {}).get("linearity") != "LINEAR":
        raise ValueError("Denoise는 현재 Linear 처리 경로에서만 실행합니다.")
    if p.get("image_state", {}).get("stretched") is True:
        raise ValueError("이미 Stretch된 입력에는 이 Linear Denoise 경로를 실행하지 않습니다.")
    if not p.get("image_state", {}).get("color_calibrated", False):
        raise ValueError("v0.6.0 Denoise 경로는 SPCC 완료 이미지에서 시작합니다.")
    return current

def _validate(modulation: float):
    modulation = float(modulation)
    if modulation < 0 or modulation > 1:
        raise ValueError("Modulation은 0~1 범위여야 합니다.")
    return modulation

def build_denoise_command(
    *,
    modulation: float = 1.0,
    cosmetic_correction: bool = True,
    da3d: bool = False,
    independent_channels: bool = False,
) -> str:
    modulation = _validate(modulation)
    args = [f"-mod={modulation:g}"]
    if not cosmetic_correction:
        args.append("-nocosmetic")
    if da3d:
        args.append("-da3d")
    if independent_channels:
        args.append("-indep")
    return "denoise " + " ".join(args)

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def preview_denoise(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "denoise_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    linear_stem = temp_dir / f"{target}_denoise_preview_linear"
    jpg_stem = preview_dir / f"{target}_denoise_preview"

    cmd = build_denoise_command(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        cmd,
        f'save "{normalize_siril_path(linear_stem)}"',
        "autostretch -linked",
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Denoise 미리보기 생성 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    linear_preview = _find_saved(linear_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not linear_preview or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Denoise 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "display_preview": str(jpg),
        "linear_preview": str(linear_preview),
        "denoise_command": cmd,
        "parameters": params,
    }
    (pdir / "logs" / "denoise_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "DENOISE_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, linear_preview, meta

def apply_denoise(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 Denoise 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "05_denoise"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_05_denoise"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    cmd = build_denoise_command(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        cmd,
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Denoise 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 Denoise 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["current_file"] = str(output)
    p["current_state"] = "DENOISED"
    p["image_state"]["denoised"] = True
    p["image_state"]["linearity"] = "LINEAR"
    p["image_state"]["stretched"] = False
    p["next_task"] = make_deblur_task()
    save_project(pdir, project)

    payload = {
        "event": "DENOISE_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "denoise_command": cmd,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "denoise_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload

def skip_denoise(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    if p.get("current_state") != "COLOR_CALIBRATED":
        raise ValueError("Denoise 건너뛰기는 COLOR_CALIBRATED 상태에서만 사용합니다.")
    p["next_task"] = make_deblur_task()
    p["next_task"]["current_status"] = "COLOR_CALIBRATED / LINEAR / DENOISE_SKIPPED"
    p["next_task"]["summary"] = "Denoise를 건너뛴 Linear 이미지에서 선택적으로 Deblur를 수행합니다."
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "DENOISE_SKIP",
        "status": "SKIPPED",
        "current_file": p.get("current_file"),
    })
    return project
