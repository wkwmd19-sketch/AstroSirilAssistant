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
from .config import load_yaml, PACKAGE_ROOT

PROFILE_FILE = PACKAGE_ROOT / "profiles" / "recommendation_profiles.yaml"

def make_recombine_task() -> dict:
    return {
        "task_id": "PIXEL_MATH_RECOMBINE",
        "title": "Pixel Math Recombine",
        "summary": "Main/Starless와 Stars 레이어를 Pixel Math로 다시 합성합니다.",
        "purpose": "별과 천체 본체를 독립적으로 보정한 결과를 원하는 별 강도로 재결합합니다.",
        "current_status": "STARS_PROCESSED / READY_TO_RECOMBINE",
        "recommendations": {
            "expression": "Main + Stars * star_weight",
            "metadata": "-nosum",
            "rescale": "OFF",
        },
        "cautions": [
            "Stars Processing에서 이미 밝기를 줄였다면 Star Weight 1.0이 자연스러운 시작값입니다.",
            "Rescale은 전체 픽셀 범위를 다시 매핑하므로 기본 OFF입니다.",
            "미리보기에서 밝은 별/은하 핵의 clipping을 확인하세요.",
        ],
        "completion_criteria": [
            "별과 Main의 자연스러운 균형",
            "하이라이트 clipping 억제",
            "색 균형 유지",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def make_finalize_task() -> dict:
    return {
        "task_id": "FINALIZE_EXPORT",
        "title": "Final / Export",
        "summary": "재합성이 완료되었습니다. 최종 확인 후 FITS/TIFF/PNG로 내보낼 준비가 되었습니다.",
        "purpose": "최종 결과 검토, 출력 형식 변환, 파일명 규칙 적용을 수행합니다.",
        "current_status": "RECOMBINED / NONLINEAR",
        "recommendations": {
            "fits": "32-bit float",
            "tiff": "16-bit",
            "png": "sRGB preview/final",
            "status": "다음 구현 단계",
        },
        "cautions": [
            "최종 Export 전 clipping과 색공간을 다시 확인합니다.",
        ],
        "completion_criteria": ["FINALIZED", "EXPORTED"],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def migrate_ready_for_recombine(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}
    if p.get("current_state") == "STARS_PROCESSED" and task.get("task_id") == "PIXEL_MATH_RECOMBINE":
        p["next_task"] = make_recombine_task()
        save_project(pdir, project)
    return project

def _inputs(project: dict) -> tuple[Path, Path]:
    p = project["project"]
    if p.get("current_state") != "STARS_PROCESSED":
        raise ValueError("Pixel Math Recombine은 STARS_PROCESSED 상태에서 시작합니다.")

    sep = p.get("separation") or {}
    main = sep.get("recombine_main_file") or p.get("current_file")
    stars = sep.get("recombine_stars_file") or sep.get("stars_processed_file") or sep.get("stars_file")

    if not main or not Path(main).exists():
        raise FileNotFoundError("Recombine Main/Starless 파일을 찾을 수 없습니다.")
    if not stars or not Path(stars).exists():
        raise FileNotFoundError("Recombine Stars 파일을 찾을 수 없습니다.")
    return Path(main), Path(stars)

def _validate(star_weight: float, rescale_output: bool):
    weight = float(star_weight)
    if weight < 0 or weight > 2:
        raise ValueError("Star Weight는 0~2 범위로 입력하세요.")
    return weight, bool(rescale_output)

def build_pm_expression(star_weight: float) -> str:
    weight, _ = _validate(star_weight, False)
    return f"$Main$ + $Stars$ * {weight:g}"

def build_pm_command(star_weight: float, rescale_output: bool = False) -> str:
    weight, rescale = _validate(star_weight, rescale_output)
    expr = build_pm_expression(weight)
    cmd = f'pm "{expr}" -nosum'
    if rescale:
        cmd += " -rescale 0 1"
    return cmd

def recommend_recombine(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    _inputs(project)

    profiles = load_yaml(PROFILE_FILE)
    section = profiles.get("recombine", {})
    target = p.get("target", {})
    category = target.get("category", "UNKNOWN")
    features = list(target.get("features") or [])

    stars_processing = p.get("stars_processing") or {}
    processed = bool(stars_processing.get("applied", False))
    skipped = bool(stars_processing.get("skipped", False))

    reasons = []
    if processed:
        weight = float(section.get("processed_stars_default_weight", 1.0))
        scale = stars_processing.get("parameters", {}).get("brightness_scale")
        if scale is not None:
            reasons.append(
                f"Stars Processing에서 Brightness Scale={float(scale):g}가 이미 적용되어 Recombine에서는 1.0을 시작값으로 사용"
            )
        else:
            reasons.append("Stars 레이어가 이미 별도 보정되어 Recombine 가중치 1.0을 시작값으로 사용")
    else:
        weight = float(
            section.get("unprocessed_stars_by_category", {}).get(
                category,
                section.get("unprocessed_stars_by_category", {}).get("UNKNOWN", 0.8),
            )
        )
        reasons.append(f"Stars Processing을 건너뛰어 {category} 카테고리의 재합성 기본 가중치를 사용")
        modifiers = section.get("feature_modifiers_if_unprocessed", {})
        for feature in features:
            mod = modifiers.get(feature)
            if not mod:
                continue
            weight += float(mod.get("weight_delta", 0))
            if mod.get("reason"):
                reasons.append(mod["reason"])

    low, high = section.get("limits", {}).get("star_weight", [0.0, 1.5])
    weight = max(float(low), min(float(high), weight))
    weight = round(weight, 2)

    effective = weight
    prior_scale = None
    if processed:
        prior_scale = stars_processing.get("parameters", {}).get("brightness_scale")
        if prior_scale is not None:
            effective = round(float(prior_scale) * weight, 3)

    result = {
        "schema_version": "0.1",
        "timestamp": iso_now(),
        "stage": "PIXEL_MATH_RECOMBINE",
        "recommended_values": {
            "star_weight": weight,
            "rescale_output": False,
        },
        "effective_star_scale_vs_original_subtraction_layer": effective,
        "prior_stars_brightness_scale": prior_scale,
        "reasons": reasons,
        "notice": "Recombine 추천값은 Stars Processing을 중복 반영하지 않도록 설계된 시작점입니다.",
    }

    p.setdefault("recommendations", {})["recombine"] = result
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "RECOMMEND_RECOMBINE",
        "status": "SUCCESS",
        **result,
    })
    return result

def _copy_pm_inputs(run_dir: Path, main: Path, stars: Path):
    main_copy = run_dir / "Main.fits"
    stars_copy = run_dir / "Stars.fits"
    shutil.copy2(main, main_copy)
    shutil.copy2(stars, stars_copy)
    return main_copy, stars_copy

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def preview_recombine(project_dir: Path, config: dict, *, star_weight: float, rescale_output: bool = False):
    pdir = Path(project_dir)
    project = load_project(pdir)
    main, stars = _inputs(project)
    target = project["project"]["target_name"]
    weight, rescale = _validate(star_weight, rescale_output)

    run_dir = pdir / "temp" / "recombine_preview" / uuid.uuid4().hex[:10]
    run_dir.mkdir(parents=True, exist_ok=True)
    _copy_pm_inputs(run_dir, main, stars)

    out_stem = run_dir / f"{target}_recombine_preview"
    jpg_stem = pdir / "output" / "preview" / f"{target}_recombine_preview"
    jpg_stem.parent.mkdir(parents=True, exist_ok=True)

    pm_cmd = build_pm_command(weight, rescale)
    commands = [
        "set32bits",
        "setext fits",
        f'cd "{normalize_siril_path(run_dir)}"',
        pm_cmd,
        f'save "{normalize_siril_path(out_stem)}"',
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=run_dir)
    if proc.returncode != 0:
        raise SirilError(
            "Pixel Math Recombine 미리보기 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    preview_fits = _find_saved(out_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not preview_fits or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Recombine 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    stats = analyze_pixels(
        preview_fits,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    highlight_ratios = [
        float(c.get("highlight_clip_ratio", 0) or 0)
        for c in (stats.get("channels") or {}).values()
    ]
    highlight_clip = max(highlight_ratios) if highlight_ratios else 0.0

    meta = {
        "timestamp": iso_now(),
        "main_file": str(main),
        "stars_file": str(stars),
        "preview_fits": str(preview_fits),
        "display_preview": str(jpg),
        "star_weight": weight,
        "rescale_output": rescale,
        "expression": build_pm_expression(weight),
        "pm_command": pm_cmd,
        "analysis": stats,
        "max_highlight_clip_ratio": highlight_clip,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    (pdir / "logs" / "recombine_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "RECOMBINE_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, preview_fits, meta

def _same_preview(preview_meta: dict, main: Path, stars: Path, weight: float, rescale: bool):
    try:
        return (
            Path(preview_meta["main_file"]).resolve() == main.resolve()
            and Path(preview_meta["stars_file"]).resolve() == stars.resolve()
            and abs(float(preview_meta["star_weight"]) - float(weight)) < 1e-12
            and bool(preview_meta["rescale_output"]) == bool(rescale)
            and Path(preview_meta["preview_fits"]).exists()
        )
    except Exception:
        return False

def apply_recombine(
    project_dir: Path,
    config: dict,
    *,
    star_weight: float,
    rescale_output: bool = False,
    confirmed: bool = False,
    preview_meta: dict | None = None,
):
    if not confirmed:
        raise PermissionError("실제 Pixel Math Recombine 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    main, stars = _inputs(project)
    p = project["project"]
    target = p["target_name"]
    weight, rescale = _validate(star_weight, rescale_output)

    if not preview_meta or not _same_preview(preview_meta, main, stars, weight, rescale):
        raise ValueError("현재 입력/설정과 동일한 Recombine 미리보기를 먼저 확인하세요.")

    out_dir = pdir / "working" / "11_recombine"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{target}_11_recombined.fits"
    shutil.copy2(preview_meta["preview_fits"], output)

    stats = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["recombine"] = {
        "main_file": str(main),
        "stars_file": str(stars),
        "output_file": str(output),
        "expression": build_pm_expression(weight),
        "pm_command": build_pm_command(weight, rescale),
        "star_weight": weight,
        "rescale_output": rescale,
        "preview_promoted": True,
        "timestamp": iso_now(),
    }

    p["current_file"] = str(output)
    p["current_state"] = "RECOMBINED"
    p["image_state"]["stars_removed"] = False
    p["image_state"]["recombined"] = True
    p["image_state"]["linearity"] = "NONLINEAR"
    p["image_state"]["stretched"] = True
    p["next_task"] = make_finalize_task()
    save_project(pdir, project)

    payload = {
        "event": "RECOMBINE_APPLY",
        "status": "SUCCESS",
        "main_file": str(main),
        "stars_file": str(stars),
        "output_file": str(output),
        "expression": build_pm_expression(weight),
        "pm_command": build_pm_command(weight, rescale),
        "star_weight": weight,
        "rescale_output": rescale,
        "preview_promoted": True,
        "analysis": stats,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "recombine_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload
