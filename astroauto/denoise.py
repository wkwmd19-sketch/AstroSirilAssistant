from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .ghs import make_ghs_task
from .syqon import (
    require_syqon_script,
    build_prism_command,
    assert_syqon_process_success,
)

def make_denoise_task() -> dict:
    return {
        "task_id": "DENOISE",
        "title": "Noise Reduction / Denoise",
        "summary": "수동 보정 흐름을 따라 Parallax 복원 다음 Linear 이미지에 Prism Denoise를 적용합니다.",
        "purpose": "복원된 미세 구조를 최대한 유지하면서 배경/색 노이즈를 줄여 Stretch 전 이미지를 정리합니다.",
        "current_status": "DEBLURRED / LINEAR",
        "recommendations": {
            "engine": "SyQon Prism Mini",
            "fallback": "Siril Native Denoise",
            "manual_inspired_order": "SPCC → Parallax → Prism → GHS",
        },
        "cautions": [
            "Prism은 Linear 데이터에서 임시 stretch/inverse stretch를 내부적으로 사용합니다.",
            "모델이 없거나 SyQon이 준비되지 않았으면 Siril Native 엔진으로 전환할 수 있습니다.",
            "과도한 Modulation은 미세 구조를 지나치게 부드럽게 만들 수 있습니다.",
        ],
        "completion_criteria": [
            "노이즈 감소",
            "미세 구조 보존",
            "Linear 상태 유지",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def make_post_denoise_task(skipped: bool = False) -> dict:
    return make_denoise_task()

def migrate_post_spcc_task(project_dir: Path):
    """v0.14 migration: COLOR_CALIBRATED now enters Restoration before Denoise."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    if p.get("current_state") == "COLOR_CALIBRATED":
        task = p.get("next_task") or {}
        if task.get("task_id") in (None, "POST_SPCC_REVIEW", "DENOISE", "POST_DENOISE_REVIEW"):
            from .deblur import make_deblur_task
            p["next_task"] = make_deblur_task()
            p.setdefault("processing_preset", "MANUAL_INSPIRED_SYQON")
            p.setdefault(
                "linear_processing_order",
                ["GRADIENT", "SPCC", "DEBLUR", "DENOISE", "GHS"],
            )
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
        raise ValueError("Denoise 경로는 SPCC 완료 이미지에서 시작합니다.")
    if p.get("current_state") not in ("DEBLURRED", "COLOR_CALIBRATED"):
        raise ValueError(
            "v0.14 Denoise는 Restoration 완료(DEBLURRED) 또는 "
            "이전 버전 호환 COLOR_CALIBRATED 상태에서 시작합니다."
        )
    return current

def _validate_native(modulation: float):
    modulation = float(modulation)
    if modulation < 0 or modulation > 1:
        raise ValueError("Native Modulation은 0~1 범위여야 합니다.")
    return modulation

def build_denoise_command(
    *,
    modulation: float = 1.0,
    cosmetic_correction: bool = True,
    da3d: bool = False,
    independent_channels: bool = False,
) -> str:
    modulation = _validate_native(modulation)
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

def _prism_command(config: dict, params: dict):
    script_path = require_syqon_script("PRISM", config)
    cmd = build_prism_command(
        script_path,
        tile_size=int(params.get("tile_size", 512)),
        overlap=int(params.get("overlap", 96)),
        pad=int(params.get("pad", 96)),
        modulation=float(params.get("modulation", 1.0)),
        model=params.get("model", "mini"),
        use_gpu=bool(params.get("use_gpu", True)),
        stretch_method=params.get("stretch_method", "statistical"),
        stretch_target=float(params.get("stretch_target", 0.25)),
    )
    return script_path, cmd

def preview_denoise(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]
    engine = str(params.get("engine", "SYQON_PRISM")).upper()

    temp_dir = pdir / "temp" / "denoise_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    linear_stem = temp_dir / f"{target}_denoise_preview_linear"
    jpg_stem = preview_dir / f"{target}_denoise_preview"
    script_path = None

    if engine == "SYQON_PRISM":
        script_path, cmd = _prism_command(config, params)
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
        proc = run_script(
            config, commands, cwd=current.parent,
            timeout_sec=int(config.get("syqon", {}).get("command_timeout_sec", 3600)),
        )
        assert_syqon_process_success(proc, "SyQon Prism")
    elif engine == "SIRIL_NATIVE":
        cmd = build_denoise_command(
            modulation=float(params.get("modulation", 1.0)),
            cosmetic_correction=bool(params.get("cosmetic_correction", True)),
            da3d=bool(params.get("da3d", False)),
            independent_channels=bool(params.get("independent_channels", False)),
        )
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
                "Siril Native Denoise 미리보기 생성 실패\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
    else:
        raise ValueError("Denoise Engine은 SYQON_PRISM / SIRIL_NATIVE 중 하나여야 합니다.")

    linear_preview = _find_saved(linear_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not linear_preview or not jpg.exists():
        raise SirilError(
            "Denoise 실행 후 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "engine": engine,
        "input_file": str(current),
        "display_preview": str(jpg),
        "linear_preview": str(linear_preview),
        "script_path": str(script_path) if script_path else None,
        "engine_command": cmd,
        "denoise_command": cmd,
        "parameters": params,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
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
    input_state = p.get("current_state")
    engine = str(params.get("engine", "SYQON_PRISM")).upper()

    if input_state == "DEBLURRED":
        out_dir = pdir / "working" / "06_denoise"
        stage_no = "06"
    else:
        # Legacy v0.6-v0.13 order.
        out_dir = pdir / "working" / "05_denoise"
        stage_no = "05"
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = "prism" if engine == "SYQON_PRISM" else "siril_denoise"
    out_stem = out_dir / f"{target}_{stage_no}_{suffix}"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    script_path = None
    if engine == "SYQON_PRISM":
        script_path, cmd = _prism_command(config, params)
        commands = [
            "set32bits",
            "setext fits",
            f'load "{normalize_siril_path(current)}"',
            cmd,
            f'save "{normalize_siril_path(out_stem)}"',
            "close",
        ]
        proc = run_script(
            config, commands, cwd=current.parent,
            timeout_sec=int(config.get("syqon", {}).get("command_timeout_sec", 3600)),
        )
        assert_syqon_process_success(proc, "SyQon Prism")
    elif engine == "SIRIL_NATIVE":
        cmd = build_denoise_command(
            modulation=float(params.get("modulation", 1.0)),
            cosmetic_correction=bool(params.get("cosmetic_correction", True)),
            da3d=bool(params.get("da3d", False)),
            independent_channels=bool(params.get("independent_channels", False)),
        )
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
                "Siril Native Denoise 실행 실패\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
    else:
        raise ValueError("Denoise Engine은 SYQON_PRISM / SIRIL_NATIVE 중 하나여야 합니다.")

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Denoise 실행 후 결과 FITS를 찾지 못했습니다.\n"
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
    p["denoise"] = {
        "engine": engine,
        "input_file": str(current),
        "output_file": str(output),
        "parameters": params,
        "command": cmd,
        "script_path": str(script_path) if script_path else None,
        "timestamp": iso_now(),
    }

    if input_state == "DEBLURRED":
        # New v0.14 manual-inspired order.
        p["next_task"] = make_ghs_task(additional=False)
    else:
        # Legacy order needs restoration next.
        from .deblur import make_deblur_task
        t = make_deblur_task()
        t["current_status"] = "DENOISED / LINEAR / LEGACY_ORDER"
        p["next_task"] = t

    save_project(pdir, project)

    payload = {
        "event": "DENOISE_APPLY",
        "status": "SUCCESS",
        "engine": engine,
        "input_state": input_state,
        "input_file": str(current),
        "output_file": str(output),
        "script_path": str(script_path) if script_path else None,
        "engine_command": cmd,
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
    state = p.get("current_state")

    if state not in ("DEBLURRED", "COLOR_CALIBRATED"):
        raise ValueError(
            "Denoise 건너뛰기는 DEBLURRED 또는 legacy COLOR_CALIBRATED 상태에서만 사용합니다."
        )

    if state == "DEBLURRED":
        p["next_task"] = make_ghs_task(additional=False)
        p["next_task"]["current_status"] = "DEBLURRED / LINEAR / DENOISE_SKIPPED"
    else:
        from .deblur import make_deblur_task
        t = make_deblur_task()
        t["current_status"] = "COLOR_CALIBRATED / LINEAR / DENOISE_SKIPPED / LEGACY_ORDER"
        p["next_task"] = t

    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "DENOISE_SKIP",
        "status": "SKIPPED",
        "input_state": state,
        "current_file": p.get("current_file"),
    })
    return project
