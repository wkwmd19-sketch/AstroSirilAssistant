from __future__ import annotations
from pathlib import Path
import json
import shutil
import uuid

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .execution import ExecutionCancelled
from .preview_utils import make_center_crop_fits
from .ghs import make_ghs_task
from .syqon import (
    require_syqon_script,
    build_parallax_command,
    assert_syqon_process_success,
)

def make_deblur_task() -> dict:
    return {
        "task_id": "DEBLUR",
        "title": "Restoration / Deblur",
        "summary": "수동 보정 흐름을 따라 Linear 이미지에서 먼저 Parallax 복원/별 보정을 수행합니다.",
        "purpose": "Stretch와 Denoise 전에 별 수차, 별 존재감, 미세 구조를 보수적으로 복원합니다.",
        "current_status": "COLOR_CALIBRATED / LINEAR",
        "recommendations": {
            "engine": "SyQon Parallax Nano",
            "fallback": "Siril PSF + Richardson-Lucy",
            "manual_inspired_order": "SPCC → Parallax → Prism → GHS",
        },
        "cautions": [
            "Parallax는 Linear 단계에서 사용합니다.",
            "SyQon 모델이 설치되지 않았으면 Siril Native RL로 전환할 수 있습니다.",
            "강한 Sharpen/Star Reduction은 별 형태나 미세 구조를 과도하게 바꿀 수 있으므로 미리보기를 확인하세요.",
        ],
        "completion_criteria": [
            "별/세부 구조 복원",
            "링잉/과샤픈 없음",
            "Linear 상태 유지",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def migrate_post_denoise_task(project_dir: Path):
    """Keep v0.6-v0.13 legacy projects usable after the v0.14 order change."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    # Legacy order: COLOR -> DENOISE -> DEBLUR.
    if p.get("current_state") == "DENOISED" and task.get("task_id") in (
        None, "POST_DENOISE_REVIEW", "DEBLUR"
    ):
        t = make_deblur_task()
        t["current_status"] = "DENOISED / LINEAR / LEGACY_ORDER"
        t["summary"] = (
            "이 프로젝트는 이전 버전에서 Denoise가 먼저 완료되었습니다. "
            "호환 모드로 Deblur/Parallax를 수행한 뒤 GHS로 이어갑니다."
        )
        p["next_task"] = t
        save_project(pdir, project)

    # Old project where Denoise was skipped before Deblur.
    elif p.get("current_state") == "COLOR_CALIBRATED" and task.get("task_id") == "POST_DENOISE_REVIEW":
        p["next_task"] = make_deblur_task()
        save_project(pdir, project)

    return project

def _current_linear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")

    if p.get("image_state", {}).get("linearity") != "LINEAR":
        raise ValueError("Restoration / Deblur는 Linear 이미지에서만 실행합니다.")
    if p.get("image_state", {}).get("stretched") is True:
        raise ValueError("이미 Stretch된 입력에는 이 Restoration 경로를 실행하지 않습니다.")
    if p.get("current_state") not in ("COLOR_CALIBRATED", "DENOISED"):
        raise ValueError(
            "Restoration은 SPCC 완료(COLOR_CALIBRATED) 또는 "
            "이전 버전 호환 DENOISED 상태에서 시작합니다."
        )
    return current

def _validate_native(
    iterations: int,
    regularization: str,
    alpha: float,
    kernel_size: int | None,
):
    iterations = int(iterations)
    if iterations < 1 or iterations > 100:
        raise ValueError("RL Iterations는 1~100 범위로 입력하세요.")

    regularization = str(regularization).upper()
    if regularization not in ("NONE", "TV", "FH"):
        raise ValueError("Regularization은 NONE / TV / FH 중 하나여야 합니다.")

    alpha = float(alpha)
    if alpha <= 0:
        raise ValueError("Alpha는 0보다 커야 합니다.")

    if kernel_size in ("", None):
        kernel_size = None
    else:
        kernel_size = int(kernel_size)
        if kernel_size < 3 or kernel_size > 255:
            raise ValueError("PSF Kernel Size는 3~255 범위로 입력하거나 비워두세요.")
        if kernel_size % 2 == 0:
            raise ValueError("PSF Kernel Size는 홀수만 허용합니다.")

    return iterations, regularization, alpha, kernel_size

def build_makepsf_command(
    *,
    symmetric_psf: bool = False,
    kernel_size: int | None = None,
    savepsf: str | None = None,
) -> str:
    args = ["makepsf", "stars"]
    if symmetric_psf:
        args.append("-sym")
    if kernel_size not in (None, ""):
        args.append(f"-ks={int(kernel_size)}")
    if savepsf:
        args.append(f'"-savepsf={savepsf}"')
    return " ".join(args)

def build_rl_command(
    *,
    iterations: int = 10,
    regularization: str = "NONE",
    alpha: float = 3000,
    multiplicative: bool = False,
) -> str:
    iterations, regularization, alpha, _ = _validate_native(
        iterations, regularization, alpha, None
    )
    args = ["rl", f"-iters={iterations}"]
    if regularization == "TV":
        args.extend(["-tv", f"-alpha={alpha:g}"])
    elif regularization == "FH":
        args.extend(["-fh", f"-alpha={alpha:g}"])
    if multiplicative:
        args.append("-mul")
    return " ".join(args)

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def _native_commands(current: Path, result_stem: Path, psf_stem: Path, params: dict):
    iterations, regularization, alpha, kernel_size = _validate_native(
        params.get("iterations", 10),
        params.get("regularization", "NONE"),
        params.get("alpha", 3000),
        params.get("kernel_size"),
    )

    psf_cmd = build_makepsf_command(
        symmetric_psf=bool(params.get("symmetric_psf", False)),
        kernel_size=kernel_size,
        savepsf=normalize_siril_path(psf_stem.with_suffix(".fits")),
    )
    rl_cmd = build_rl_command(
        iterations=iterations,
        regularization=regularization,
        alpha=alpha,
        multiplicative=bool(params.get("multiplicative", False)),
    )

    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        "makepsf clear",
        psf_cmd,
        rl_cmd,
        f'save "{normalize_siril_path(result_stem)}"',
    ]
    return commands, psf_cmd, rl_cmd

def _parallax_command(config: dict, params: dict):
    script_path = require_syqon_script("PARALLAX", config)
    cmd = build_parallax_command(
        script_path,
        edition=params.get("edition", "nano"),
        correct=bool(params.get("correct", True)),
        star_level=float(params.get("star_level", 3.0)),
        sharpen=float(params.get("sharpen", 1.0)),
        tile=int(params.get("tile", 512)),
        overlap=int(params.get("overlap", 64)),
        pad=int(params.get("pad", 96)),
        use_mtf=bool(params.get("use_mtf", True)),
        mtf_target=float(params.get("mtf_target", 0.25)),
        linked=bool(params.get("linked", False)),
        use_gpu=bool(params.get("use_gpu", True)),
    )
    return script_path, cmd

def preview_deblur(project_dir: Path, config: dict, *, preview_mode: str = "FULL", **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]
    engine = str(params.get("engine", "SYQON_PARALLAX")).upper()
    preview_mode = str(preview_mode).upper()
    if preview_mode not in ("QUICK", "FULL"):
        raise ValueError("preview_mode는 QUICK / FULL 중 하나여야 합니다.")

    base_temp = pdir / "temp" / "deblur_preview"
    preview_dir = pdir / "output" / "preview"
    base_temp.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    # A unique run directory prevents a cancelled/incomplete result from being
    # mistaken for the next preview.
    run_token = uuid.uuid4().hex[:10]
    run_dir = base_temp / f"{preview_mode.lower()}_{run_token}"
    run_dir.mkdir(parents=True, exist_ok=True)
    preview_input = current
    crop_meta = None

    try:
        if preview_mode == "QUICK":
            crop_path = run_dir / f"{target}_quick_input.fits"
            crop_meta = make_center_crop_fits(
                current,
                crop_path,
                max_size=int(config.get("syqon", {}).get("quick_preview_size", 1536)),
            )
            preview_input = crop_path

        linear_stem = run_dir / f"{target}_restore_{preview_mode.lower()}_linear"
        jpg_stem = preview_dir / f"{target}_restore_{preview_mode.lower()}_preview_{run_token}"

        psf_file = None
        engine_command = None
        script_path = None

        if engine == "SYQON_PARALLAX":
            script_path, engine_command = _parallax_command(config, params)
            commands = [
                "set32bits",
                "setext fits",
                f'load "{normalize_siril_path(preview_input)}"',
                engine_command,
                f'save "{normalize_siril_path(linear_stem)}"',
                "autostretch -linked",
                f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
                "close",
            ]
            timeout = int(
                config.get("syqon", {}).get(
                    "quick_preview_timeout_sec" if preview_mode == "QUICK" else "command_timeout_sec",
                    900 if preview_mode == "QUICK" else 3600,
                )
            )
            proc = run_script(config, commands, cwd=preview_input.parent, timeout_sec=timeout)
            assert_syqon_process_success(proc, "SyQon Parallax")
        elif engine == "SIRIL_RL":
            psf_stem = run_dir / f"{target}_restore_{preview_mode.lower()}_psf"
            commands, psf_cmd, rl_cmd = _native_commands(
                preview_input, linear_stem, psf_stem, params
            )
            engine_command = f"{psf_cmd}  →  {rl_cmd}"
            commands.extend([
                "autostretch -linked",
                f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
                "close",
            ])
            proc = run_script(config, commands, cwd=preview_input.parent)
            if proc.returncode != 0:
                raise SirilError(
                    "Siril RL Restoration 미리보기 생성 실패\n"
                    f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
                )
            psf_file = _find_saved(psf_stem)
        else:
            raise ValueError("Restoration Engine은 SYQON_PARALLAX / SIRIL_RL 중 하나여야 합니다.")

        linear_preview = _find_saved(linear_stem)
        jpg = jpg_stem.with_suffix(".jpg")
        if not linear_preview or not jpg.exists():
            raise SirilError(
                "Restoration 실행 후 미리보기 출력 파일을 찾지 못했습니다.\n"
                "SyQon 모델/스크립트 또는 Siril 로그를 확인하세요.\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )

        meta = {
            "timestamp": iso_now(),
            "engine": engine,
            "preview_mode": preview_mode,
            "input_file": str(current),
            "preview_input_file": str(preview_input),
            "crop": crop_meta,
            "display_preview": str(jpg),
            "linear_preview": str(linear_preview),
            "psf_file": str(psf_file) if psf_file else None,
            "script_path": str(script_path) if script_path else None,
            "engine_command": engine_command,
            "parameters": params,
            "siril_stdout": proc.stdout,
            "siril_stderr": proc.stderr,
        }
        (pdir / "logs" / f"deblur_preview_{preview_mode.lower()}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        append_jsonl(pdir, {"event": "DEBLUR_PREVIEW", "status": "SUCCESS", **meta})
        return jpg, linear_preview, meta
    except ExecutionCancelled:
        shutil.rmtree(run_dir, ignore_errors=True)
        # A JPG may have been partially created just before cancellation.
        try:
            candidate = jpg_stem.with_suffix(".jpg") if 'jpg_stem' in locals() else None
            if candidate and candidate.exists(): candidate.unlink()
        except Exception:
            pass
        raise
    except Exception:
        # Failed preview outputs are never reusable.
        shutil.rmtree(run_dir, ignore_errors=True)
        raise

def apply_deblur(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 Restoration 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    p = project["project"]
    target = p["target_name"]
    input_state = p.get("current_state")
    engine = str(params.get("engine", "SYQON_PARALLAX")).upper()

    if input_state == "COLOR_CALIBRATED":
        out_dir = pdir / "working" / "05_restore"
        stage_no = "05"
    else:
        # Legacy v0.6-v0.13 compatibility.
        out_dir = pdir / "working" / "06_deblur"
        stage_no = "06"
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = "parallax" if engine == "SYQON_PARALLAX" else "siril_deblur"
    out_stem = out_dir / f"{target}_{stage_no}_{suffix}"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    psf_file = None
    script_path = None
    engine_command = None

    if engine == "SYQON_PARALLAX":
        script_path, engine_command = _parallax_command(config, params)
        commands = [
            "set32bits",
            "setext fits",
            f'load "{normalize_siril_path(current)}"',
            engine_command,
            f'save "{normalize_siril_path(out_stem)}"',
            "close",
        ]
        proc = run_script(
            config, commands, cwd=current.parent,
            timeout_sec=int(config.get("syqon", {}).get("command_timeout_sec", 3600)),
        )
        assert_syqon_process_success(proc, "SyQon Parallax")
    elif engine == "SIRIL_RL":
        psf_stem = out_dir / f"{target}_{stage_no}_psf"
        commands, psf_cmd, rl_cmd = _native_commands(
            current, out_stem, psf_stem, params
        )
        engine_command = f"{psf_cmd}  →  {rl_cmd}"
        commands.append("close")
        proc = run_script(config, commands, cwd=current.parent)
        if proc.returncode != 0:
            raise SirilError(
                "Siril RL Restoration 실행 실패\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        psf_file = _find_saved(psf_stem)
    else:
        raise ValueError("Restoration Engine은 SYQON_PARALLAX / SIRIL_RL 중 하나여야 합니다.")

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Restoration 실행 후 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["current_file"] = str(output)
    p["current_state"] = "DEBLURRED"
    p["image_state"]["deblurred"] = True
    p["image_state"]["linearity"] = "LINEAR"
    p["image_state"]["stretched"] = False
    p["restoration"] = {
        "engine": engine,
        "input_file": str(current),
        "output_file": str(output),
        "parameters": params,
        "command": engine_command,
        "script_path": str(script_path) if script_path else None,
        "timestamp": iso_now(),
    }

    if input_state == "COLOR_CALIBRATED":
        # New v0.14 manual-inspired order: Parallax/restore -> Prism/denoise.
        from .denoise import make_denoise_task
        p["next_task"] = make_denoise_task()
    else:
        # Legacy order already denoised before restoration.
        p["next_task"] = make_ghs_task(additional=False)

    save_project(pdir, project)

    payload = {
        "event": "DEBLUR_APPLY",
        "status": "SUCCESS",
        "engine": engine,
        "input_state": input_state,
        "input_file": str(current),
        "output_file": str(output),
        "psf_file": str(psf_file) if psf_file else None,
        "script_path": str(script_path) if script_path else None,
        "engine_command": engine_command,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "deblur_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload

def skip_deblur(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    state = p.get("current_state")

    if state not in ("COLOR_CALIBRATED", "DENOISED"):
        raise ValueError(
            "Restoration 건너뛰기는 COLOR_CALIBRATED 또는 legacy DENOISED 상태에서만 사용합니다."
        )

    if state == "COLOR_CALIBRATED":
        from .denoise import make_denoise_task
        p["next_task"] = make_denoise_task()
        p["next_task"]["current_status"] = "COLOR_CALIBRATED / LINEAR / RESTORE_SKIPPED"
        p["next_task"]["summary"] = "Restoration을 건너뛴 Linear 이미지에서 Prism/Siril Denoise를 수행합니다."
    else:
        p["next_task"] = make_ghs_task(additional=False)
        p["next_task"]["current_status"] = "DENOISED / LINEAR / RESTORE_SKIPPED"

    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "DEBLUR_SKIP",
        "status": "SKIPPED",
        "input_state": state,
        "current_file": p.get("current_file"),
    })
    return project
