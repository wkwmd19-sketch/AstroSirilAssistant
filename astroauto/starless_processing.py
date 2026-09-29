from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl
from .stars_processing import make_stars_process_task

def make_starless_process_task() -> dict:
    return {
        "task_id": "STARLESS_PROCESS",
        "title": "Starless Processing",
        "summary": "별이 제거된 천체 본체의 국부 대비와 채도를 보수적으로 조정합니다.",
        "purpose": "은하/성운 구조를 Stars 레이어와 독립적으로 다듬습니다.",
        "current_status": "STARS_SEPARATED / STARLESS_ACTIVE / NONLINEAR",
        "recommendations": {
            "engine": "Target-aware Recommendation Engine v0.1",
            "operations": "CLAHE + Saturation",
            "policy": "천체 분류/특징 + 현재 이미지 통계 → 시작값 추천 → 사용자 승인",
        },
        "cautions": [
            "추천값은 정답이 아니라 시작점입니다.",
            "CLAHE는 노이즈/미세 아티팩트도 강조할 수 있으므로 미리보기 확인이 필요합니다.",
            "Stars 레이어는 이 단계에서 변경하지 않습니다.",
        ],
        "completion_criteria": [
            "Starless 구조 개선",
            "과도한 국부 대비 없음",
            "색 노이즈/과포화 없음",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def _legacy_make_stars_process_task(skipped: bool = False) -> dict:
    return {
        "task_id": "STARS_PROCESS",
        "title": "Stars Processing",
        "summary": (
            "Starless 보정이 완료되었습니다. 다음 단계는 별 레이어를 별도로 조정합니다."
            if not skipped else
            "Starless 보정을 건너뛰었습니다. 다음 단계는 별 레이어를 별도로 조정합니다."
        ),
        "purpose": "별 크기/밝기/색을 천체 본체와 독립적으로 조정한 뒤 Pixel Math 재합성을 준비합니다.",
        "current_status": "STARLESS_PROCESSED / STARS_AVAILABLE" if not skipped else "STARS_SEPARATED / STARLESS_SKIPPED",
        "recommendations": {
            "status": "다음 구현 단계",
            "next": "Star brightness / saturation / reduction → Pixel Math recombine",
        },
        "cautions": [
            "Stars 레이어는 subtraction layer이며 이후 덧셈 방식 재합성을 사용합니다.",
        ],
        "completion_criteria": ["Stars 레이어 조정 완료"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def migrate_ready_for_starless(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}
    if (
        p.get("current_state") == "STARS_SEPARATED"
        and task.get("task_id") == "STARLESS_PROCESS"
    ):
        p["next_task"] = make_starless_process_task()
        save_project(pdir, project)
    return project

def _current_starless(project: dict) -> Path:
    p = project["project"]
    if p.get("current_state") != "STARS_SEPARATED":
        raise ValueError("Starless Processing은 STARS_SEPARATED 상태에서 시작합니다.")
    if p.get("image_state", {}).get("stars_removed") is not True:
        raise ValueError("현재 파일이 Starless 상태인지 확인할 수 없습니다.")
    if p.get("image_state", {}).get("linearity") != "NONLINEAR":
        raise ValueError("v0.10 Starless Processing은 Non-linear Starless 이미지용입니다.")

    sep = p.get("separation") or {}
    stars = sep.get("stars_file")
    if not stars or not Path(stars).exists():
        raise FileNotFoundError("Stars 레이어 파일을 찾을 수 없습니다.")

    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 Starless FITS가 없습니다: {current}")
    return current

def _validate(
    *,
    clahe_enabled: bool,
    clahe_clip_limit: float,
    clahe_tile_size: int,
    saturation_enabled: bool,
    saturation_amount: float,
    saturation_background_factor: float,
    saturation_hue_range: int,
):
    clip = float(clahe_clip_limit)
    tile = int(clahe_tile_size)
    sat = float(saturation_amount)
    bg = float(saturation_background_factor)
    hue = int(saturation_hue_range)

    if clahe_enabled:
        if clip <= 0:
            raise ValueError("CLAHE Clip Limit은 0보다 커야 합니다.")
        if tile < 2 or tile > 64:
            raise ValueError("CLAHE Tile Size는 2~64 범위로 입력하세요.")

    if saturation_enabled:
        if sat < -1.0 or sat > 2.0:
            raise ValueError("Saturation Amount는 -1.0~2.0 범위로 입력하세요.")
        if bg < 0:
            raise ValueError("Saturation Background Factor는 0 이상이어야 합니다.")
        if hue < 0 or hue > 6:
            raise ValueError("Hue Range는 0~6 범위여야 합니다.")

    if not clahe_enabled and not saturation_enabled:
        raise ValueError("CLAHE 또는 Saturation 중 하나 이상을 켜세요.")

    return {
        "clahe_enabled": bool(clahe_enabled),
        "clahe_clip_limit": clip,
        "clahe_tile_size": tile,
        "saturation_enabled": bool(saturation_enabled),
        "saturation_amount": sat,
        "saturation_background_factor": bg,
        "saturation_hue_range": hue,
    }

def build_starless_commands(**params) -> list[str]:
    p = _validate(**params)
    commands = []

    # App pipeline order: local contrast first, color saturation second.
    # This is an application workflow choice, not a claim of universal ordering.
    if p["clahe_enabled"]:
        commands.append(
            f'clahe {p["clahe_clip_limit"]:g} {p["clahe_tile_size"]}'
        )
    if p["saturation_enabled"] and abs(p["saturation_amount"]) > 1e-12:
        commands.append(
            f'satu {p["saturation_amount"]:g} '
            f'{p["saturation_background_factor"]:g} '
            f'{p["saturation_hue_range"]}'
        )
    return commands

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def preview_starless_processing(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_starless(project)
    target = project["project"]["target_name"]

    temp_dir = pdir / "temp" / "starless_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    out_stem = temp_dir / f"{target}_starless_processed_preview"
    jpg_stem = preview_dir / f"{target}_starless_processed_preview"

    ops = build_starless_commands(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        *ops,
        f'save "{normalize_siril_path(out_stem)}"',
        # Starless is already non-linear: no AutoStretch.
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Starless Processing 미리보기 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    preview_fits = _find_saved(out_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not preview_fits or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Starless 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "preview_fits": str(preview_fits),
        "display_preview": str(jpg),
        "commands": ops,
        "parameters": params,
        "note": "Starless는 이미 Non-linear이므로 preview JPEG에 AutoStretch를 추가하지 않습니다.",
    }
    (pdir / "logs" / "starless_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "STARLESS_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, preview_fits, meta

def apply_starless_processing(project_dir: Path, config: dict, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 Starless Processing 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_starless(project)
    p = project["project"]
    target = p["target_name"]

    out_dir = pdir / "working" / "09_starless"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_09_starless_processed"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    ops = build_starless_commands(**params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        *ops,
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Starless Processing 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 Starless Processing 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    sep = p.setdefault("separation", {})
    sep["starless_processed_file"] = str(output)

    p["starless_processing"] = {
        "applied": True,
        "skipped": False,
        "parameters": params,
        "commands": ops,
        "timestamp": iso_now(),
    }
    p["current_file"] = str(output)
    p["current_state"] = "STARLESS_PROCESSED"
    p["image_state"]["stars_removed"] = True
    p["image_state"]["linearity"] = "NONLINEAR"
    p["image_state"]["stretched"] = True
    p["next_task"] = make_stars_process_task(skipped_starless=False)
    save_project(pdir, project)

    payload = {
        "event": "STARLESS_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "commands": ops,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "starless_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload

def skip_starless_processing(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    _current_starless(project)

    p["starless_processing"] = {
        "applied": False,
        "skipped": True,
        "timestamp": iso_now(),
    }
    p["next_task"] = make_stars_process_task(skipped_starless=True)
    save_project(pdir, project)

    append_jsonl(pdir, {
        "event": "STARLESS_SKIP",
        "status": "SKIPPED",
        "current_file": p.get("current_file"),
    })
    return project
