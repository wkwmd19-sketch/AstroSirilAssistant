from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .ghs import make_ghs_task

def make_deblur_task() -> dict:
    return {
        "task_id": "DEBLUR",
        "title": "Deblur / Deconvolution",
        "summary": "별에서 PSF를 추정하고 Richardson-Lucy 방식으로 흐려진 디테일을 복원합니다.",
        "purpose": "Denoise된 Linear 이미지에서 별과 은하 세부 구조를 보수적으로 복원합니다.",
        "current_status": "DENOISED / LINEAR",
        "recommendations": {
            "psf": "Detected Stars",
            "iterations": 10,
            "regularization": "NONE",
            "alpha": 3000,
            "multiplicative": "OFF",
        },
        "cautions": [
            "반복 횟수가 높으면 링잉/과샤픈/노이즈 증폭 위험이 커집니다.",
            "별 가장자리와 밝은 중심부를 미리보기에서 반드시 확인하세요.",
        ],
        "completion_criteria": [
            "디테일 개선",
            "링잉 억제",
            "Linear 상태 유지",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def _legacy_make_ghs_task(skipped: bool = False) -> dict:
    return {
        "task_id": "GHS_STRETCH",
        "title": "GHS Stretch",
        "summary": (
            "Deblur가 완료되었습니다. 다음 단계는 Linear 이미지를 비선형으로 전환하는 GHS Stretch입니다."
            if not skipped else
            "Deblur를 건너뛰었습니다. 다음 단계는 Linear 이미지를 비선형으로 전환하는 GHS Stretch입니다."
        ),
        "purpose": "희미한 외곽 구조를 올리면서 밝은 중심부와 별 하이라이트를 보호합니다.",
        "current_status": "DEBLURRED / LINEAR" if not skipped else "LINEAR / READY_FOR_GHS",
        "recommendations": {
            "status": "다음 구현 단계",
            "analysis": "Histogram / background / high-percentile 기반 자동 추천 예정",
        },
        "cautions": [
            "GHS 적용 후 이미지는 Non-linear 상태가 됩니다.",
            "초기 Stretch를 중복 적용하지 않도록 State를 엄격히 추적합니다.",
        ],
        "completion_criteria": [
            "외곽 신호 가시화",
            "하이라이트 보존",
            "Non-linear 전환",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def migrate_post_denoise_task(project_dir: Path):
    """Upgrade v0.6 projects so DENOISED/POST_DENOISE_REVIEW continues to DEBLUR."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    if p.get("current_state") == "DENOISED":
        if task.get("task_id") in (None, "POST_DENOISE_REVIEW"):
            p["next_task"] = make_deblur_task()
            save_project(pdir, project)

    elif p.get("current_state") == "COLOR_CALIBRATED":
        # Denoise may have been explicitly skipped in v0.6.
        if task.get("task_id") == "POST_DENOISE_REVIEW":
            next_task = make_deblur_task()
            next_task["current_status"] = "COLOR_CALIBRATED / LINEAR / DENOISE_SKIPPED"
            next_task["summary"] = "Denoise를 건너뛴 Linear 이미지에서 선택적으로 Deblur를 수행합니다."
            p["next_task"] = next_task
            save_project(pdir, project)

    return project

def _current_linear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")

    if p.get("image_state", {}).get("linearity") != "LINEAR":
        raise ValueError("Deblur는 Linear 이미지에서만 실행합니다.")
    if p.get("image_state", {}).get("stretched") is True:
        raise ValueError("이미 Stretch된 입력에는 이 Deblur 경로를 실행하지 않습니다.")
    if p.get("current_state") not in ("DENOISED", "COLOR_CALIBRATED"):
        raise ValueError("v0.7 Deblur는 Denoise 완료 또는 Denoise 건너뜀 상태에서 시작합니다.")
    return current

def _validate(
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
            raise ValueError("PSF Kernel Size는 홀수를 권장하며 v0.7에서는 홀수만 허용합니다.")

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
    iterations, regularization, alpha, _ = _validate(
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

def _build_commands(current: Path, result_stem: Path, psf_stem: Path, params: dict):
    iterations, regularization, alpha, kernel_size = _validate(
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

def preview_deblur(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "deblur_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    linear_stem = temp_dir / f"{target}_deblur_preview_linear"
    psf_stem = temp_dir / f"{target}_deblur_preview_psf"
    jpg_stem = preview_dir / f"{target}_deblur_preview"

    commands, psf_cmd, rl_cmd = _build_commands(
        current, linear_stem, psf_stem, params
    )
    commands.extend([
        "autostretch -linked",
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ])

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Deblur 미리보기 생성 실패\n"
            "PSF를 만들 수 있을 만큼 적절한 별이 검출되지 않았거나 RL 처리 중 문제가 발생했을 수 있습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    linear_preview = _find_saved(linear_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    psf_file = _find_saved(psf_stem)

    if not linear_preview or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Deblur 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "display_preview": str(jpg),
        "linear_preview": str(linear_preview),
        "psf_file": str(psf_file) if psf_file else None,
        "makepsf_command": psf_cmd,
        "rl_command": rl_cmd,
        "parameters": params,
    }
    (pdir / "logs" / "deblur_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "DEBLUR_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, linear_preview, meta

def apply_deblur(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 Deblur 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_linear_file(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "06_deblur"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_06_deblur"
    psf_stem = out_dir / f"{target}_06_psf"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    commands, psf_cmd, rl_cmd = _build_commands(
        current, out_stem, psf_stem, params
    )
    commands.append("close")

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Deblur 실행 실패\n"
            "PSF 별 검출 또는 Richardson-Lucy 처리 로그를 확인하세요.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    psf_file = _find_saved(psf_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 Deblur 결과 FITS를 찾지 못했습니다.\n"
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
    p["next_task"] = make_ghs_task(additional=False)
    save_project(pdir, project)

    payload = {
        "event": "DEBLUR_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "psf_file": str(psf_file) if psf_file else None,
        "makepsf_command": psf_cmd,
        "rl_command": rl_cmd,
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

    if p.get("current_state") not in ("DENOISED", "COLOR_CALIBRATED"):
        raise ValueError("Deblur 건너뛰기는 DENOISED 또는 Denoise 건너뜀 상태에서만 사용합니다.")

    p["next_task"] = make_ghs_task(additional=False)
    p["next_task"]["current_status"] = "LINEAR / READY_FOR_GHS / DEBLUR_SKIPPED"
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "DEBLUR_SKIP",
        "status": "SKIPPED",
        "current_file": p.get("current_file"),
    })
    return project
