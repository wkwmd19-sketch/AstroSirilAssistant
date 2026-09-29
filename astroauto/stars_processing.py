from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl

def make_stars_process_task(skipped_starless: bool = False) -> dict:
    return {
        "task_id": "STARS_PROCESS",
        "title": "Stars Processing",
        "summary": (
            "Starless 보정이 완료되었습니다. Stars 레이어의 밝기와 색을 독립적으로 조정합니다."
            if not skipped_starless else
            "Starless 보정은 건너뛰었습니다. Stars 레이어의 밝기와 색을 독립적으로 조정합니다."
        ),
        "purpose": "별의 존재감과 색을 조절한 뒤 Pixel Math 재합성을 준비합니다.",
        "current_status": (
            "STARLESS_PROCESSED / STARS_AVAILABLE"
            if not skipped_starless else
            "STARS_SEPARATED / STARLESS_SKIPPED / STARS_AVAILABLE"
        ),
        "recommendations": {
            "engine": "Target-aware Recommendation Engine v0.2",
            "brightness": "fmul scalar",
            "saturation": "satu amount background_factor hue_range",
            "policy": "천체 특징 + Stars 레이어 통계 → 시작값 추천 → 사용자 승인",
        },
        "cautions": [
            "Brightness Scale은 별의 전체 밝기/존재감을 조절하며 실제 별 반경을 기하학적으로 줄이는 기능은 아닙니다.",
            "Stars는 subtraction layer이므로 이후 Main + Stars * weight 형태의 재합성에 사용됩니다.",
            "추천값은 시작점이며 미리보기로 반드시 확인하세요.",
        ],
        "completion_criteria": [
            "별 밝기와 대상 구조의 균형",
            "별색 과포화 없음",
            "Stars 레이어 보존",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def make_recombine_task(stars_skipped: bool = False) -> dict:
    return {
        "task_id": "PIXEL_MATH_RECOMBINE",
        "title": "Pixel Math Recombine",
        "summary": (
            "Starless와 보정된 Stars 레이어를 다시 합성합니다."
            if not stars_skipped else
            "Starless와 원본 Stars 레이어를 다시 합성합니다."
        ),
        "purpose": "독립적으로 보정한 Main/Stars를 원하는 별 강도로 재합성합니다.",
        "current_status": "STARS_PROCESSED / READY_TO_RECOMBINE",
        "recommendations": {
            "expression_family": "Main + Stars * star_weight",
            "status": "다음 구현 단계",
        },
        "cautions": [
            "Stars 레이어는 subtraction/additive layer입니다.",
            "재합성 시 clipping 여부를 확인해야 합니다.",
        ],
        "completion_criteria": ["별 재합성 완료"],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def migrate_ready_for_stars(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    if task.get("task_id") == "STARS_PROCESS" and p.get("current_state") in (
        "STARLESS_PROCESSED", "STARS_SEPARATED"
    ):
        skipped = bool(p.get("starless_processing", {}).get("skipped", False))
        p["next_task"] = make_stars_process_task(skipped_starless=skipped)
        save_project(pdir, project)
    return project

def _layer_paths(project: dict) -> tuple[Path, Path]:
    p = project["project"]
    if p.get("current_state") not in ("STARLESS_PROCESSED", "STARS_SEPARATED"):
        raise ValueError("Stars Processing은 Starless 처리 완료/건너뜀 상태에서 시작합니다.")

    sep = p.get("separation") or {}

    starless = sep.get("starless_processed_file") or p.get("current_file")
    stars = sep.get("stars_file")

    if not starless or not Path(starless).exists():
        raise FileNotFoundError("Starless/Main 레이어를 찾을 수 없습니다.")
    if not stars or not Path(stars).exists():
        raise FileNotFoundError("Stars 레이어를 찾을 수 없습니다.")

    return Path(starless), Path(stars)

def _validate(
    *,
    brightness_scale: float,
    saturation_enabled: bool,
    saturation_amount: float,
    saturation_background_factor: float,
    saturation_hue_range: int,
):
    scale = float(brightness_scale)
    sat = float(saturation_amount)
    bg = float(saturation_background_factor)
    hue = int(saturation_hue_range)

    if scale < 0 or scale > 2:
        raise ValueError("Stars Brightness Scale은 0~2 범위로 입력하세요.")
    if saturation_enabled:
        if sat < -1 or sat > 2:
            raise ValueError("Stars Saturation Amount는 -1~2 범위로 입력하세요.")
        if bg < 0:
            raise ValueError("Stars Saturation Background Factor는 0 이상이어야 합니다.")
        if hue < 0 or hue > 6:
            raise ValueError("Stars Hue Range는 0~6 범위여야 합니다.")

    return {
        "brightness_scale": scale,
        "saturation_enabled": bool(saturation_enabled),
        "saturation_amount": sat,
        "saturation_background_factor": bg,
        "saturation_hue_range": hue,
    }

def build_stars_commands(**params) -> list[str]:
    p = _validate(**params)
    commands = []

    # Color is adjusted before the global brightness scale. With background_factor=0
    # this is especially predictable for a black-background additive Stars layer.
    if p["saturation_enabled"] and abs(p["saturation_amount"]) > 1e-12:
        commands.append(
            f'satu {p["saturation_amount"]:g} '
            f'{p["saturation_background_factor"]:g} '
            f'{p["saturation_hue_range"]}'
        )

    if abs(p["brightness_scale"] - 1.0) > 1e-12:
        commands.append(f'fmul {p["brightness_scale"]:g}')

    return commands

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def preview_stars_processing(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    _main, stars = _layer_paths(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "stars_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    out_stem = temp_dir / f"{target}_stars_processed_preview"
    jpg_stem = preview_dir / f"{target}_stars_processed_preview"

    ops = build_stars_commands(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(stars)}"',
        *ops,
        f'save "{normalize_siril_path(out_stem)}"',
        # Stars layer is already non-linear; do not add AutoStretch.
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=stars.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Stars Processing 미리보기 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    preview_fits = _find_saved(out_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not preview_fits or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Stars 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_stars_file": str(stars),
        "preview_fits": str(preview_fits),
        "display_preview": str(jpg),
        "commands": ops,
        "parameters": params,
        "note": "Stars 레이어는 Non-linear이므로 preview JPEG에 AutoStretch를 추가하지 않습니다.",
    }
    (pdir / "logs" / "stars_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "STARS_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, preview_fits, meta

def apply_stars_processing(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 Stars Processing 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    main, stars = _layer_paths(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "10_stars"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_10_stars_processed"

    before = analyze_pixels(
        stars,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    ops = build_stars_commands(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(stars)}"',
        *ops,
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]

    proc = run_script(config, commands, cwd=stars.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Stars Processing 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 Stars Processing 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    sep = p.setdefault("separation", {})
    sep["stars_processed_file"] = str(output)
    sep["recombine_main_file"] = str(main)
    sep["recombine_stars_file"] = str(output)

    p["stars_processing"] = {
        "applied": True,
        "skipped": False,
        "input_file": str(stars),
        "output_file": str(output),
        "parameters": params,
        "commands": ops,
        "timestamp": iso_now(),
    }

    # current_file intentionally remains the Main/Starless layer.
    p["current_file"] = str(main)
    p["current_state"] = "STARS_PROCESSED"
    p["next_task"] = make_recombine_task(stars_skipped=False)
    save_project(pdir, project)

    payload = {
        "event": "STARS_APPLY",
        "status": "SUCCESS",
        "main_file": str(main),
        "input_stars_file": str(stars),
        "output_stars_file": str(output),
        "commands": ops,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "stars_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload

def skip_stars_processing(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    main, stars = _layer_paths(project)
    p = project["project"]

    sep = p.setdefault("separation", {})
    sep["stars_processed_file"] = str(stars)
    sep["recombine_main_file"] = str(main)
    sep["recombine_stars_file"] = str(stars)

    p["stars_processing"] = {
        "applied": False,
        "skipped": True,
        "input_file": str(stars),
        "output_file": str(stars),
        "timestamp": iso_now(),
    }
    p["current_file"] = str(main)
    p["current_state"] = "STARS_PROCESSED"
    p["next_task"] = make_recombine_task(stars_skipped=True)
    save_project(pdir, project)

    append_jsonl(pdir, {
        "event": "STARS_SKIP",
        "status": "SKIPPED",
        "main_file": str(main),
        "stars_file": str(stars),
    })
    return project
