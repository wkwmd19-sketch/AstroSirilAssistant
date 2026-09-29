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
from .starless_processing import make_starless_process_task

STRIDE_PRESETS = {
    "LARGE": 384,
    "STANDARD": 256,
    "SMALL": 128,
}

def make_star_separation_task() -> dict:
    return {
        "task_id": "STAR_SEPARATION",
        "title": "StarNet / 별 분리",
        "summary": "Stretch 완료 이미지를 Starless와 Stars 레이어로 분리합니다.",
        "purpose": "은하/성운과 별을 각각 독립적으로 처리하고 이후 Pixel Math로 재합성할 준비를 합니다.",
        "current_status": "STRETCHED / NONLINEAR",
        "recommendations": {
            "engine": "Siril pyscript StarNet.py (StarNet2 2.5+)",
            "linear_data": "OFF (현재 Non-linear)",
            "stride": "STANDARD / 256",
            "upsample_2x": "OFF",
            "protect_highlights": "ON",
            "stars_layer": "SUBTRACT (Original - Starless)",
        },
        "cautions": [
            "StarNet은 시간이 오래 걸릴 수 있습니다.",
            "작은 별이 잘 남는 경우에만 Small stride 또는 2x Upsampling을 비교하세요.",
            "미리보기와 적용 설정이 같으면 v0.9.0은 결과를 재계산하지 않고 그대로 확정합니다.",
        ],
        "completion_criteria": [
            "Starless의 큰 제거 아티팩트 없음",
            "Stars 레이어 생성",
            "밝은 핵/하이라이트 보존",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def _legacy_make_starless_process_task() -> dict:
    return {
        "task_id": "STARLESS_PROCESS",
        "title": "Starless Processing",
        "summary": "별이 제거된 천체 본체를 별과 독립적으로 조정합니다.",
        "purpose": "은하 외곽, 먼지띠, 성운 구조의 대비/색을 별에 영향을 덜 주면서 조정합니다.",
        "current_status": "STARS_SEPARATED / STARLESS_ACTIVE",
        "recommendations": {
            "status": "다음 구현 단계",
            "next": "Starless Curves / Saturation / Local Contrast",
        },
        "cautions": [
            "현재 current_file은 Starless입니다.",
            "Stars 파일은 별도로 보존되어 이후 재합성에 사용됩니다.",
        ],
        "completion_criteria": ["Starless 조정 완료"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def make_starnet_skipped_task() -> dict:
    return {
        "task_id": "POST_STARNET_SKIPPED",
        "title": "StarNet 건너뜀 / 최종 처리 준비",
        "summary": "별 분리를 사용하지 않고 현재 Non-linear 이미지를 유지합니다.",
        "purpose": "성단 등 별 분리가 적합하지 않은 대상의 단일 이미지 후처리로 이어갑니다.",
        "current_status": "STRETCHED / STARNET_SKIPPED",
        "recommendations": {"next": "Final Curves / Color / Export"},
        "cautions": ["Starless/Stars 분기 처리는 사용할 수 없습니다."],
        "completion_criteria": ["다음 처리 선택"],
        "actions": ["CONFIRM"],
    }

def migrate_ready_for_starnet(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    if (
        p.get("current_state") == "STRETCHED"
        and p.get("image_state", {}).get("linearity") == "NONLINEAR"
        and task.get("task_id") == "STAR_SEPARATION"
    ):
        p["next_task"] = make_star_separation_task()
        save_project(pdir, project)
    return project

def _current_nonlinear_file(project: dict) -> Path:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")
    if p.get("current_state") != "STRETCHED":
        raise ValueError("StarNet은 Stretch 완료 상태에서 시작합니다.")
    if p.get("image_state", {}).get("linearity") != "NONLINEAR":
        raise ValueError("v0.9 StarNet 경로는 Non-linear 이미지용입니다.")
    if p.get("image_state", {}).get("stretched") is not True:
        raise ValueError("Stretch 완료 상태가 확인되지 않았습니다.")
    return current

def _validate(
    stride_preset: str,
    stride: int,
    upsample: bool,
    protect_highlights: bool,
    save_native_starmask: bool,
):
    preset = str(stride_preset).upper()
    if preset in STRIDE_PRESETS:
        stride_value = STRIDE_PRESETS[preset]
    elif preset == "CUSTOM":
        stride_value = int(stride)
        if stride_value < 2 or stride_value > 512 or stride_value % 2:
            raise ValueError("Custom Stride는 2~512 범위의 짝수여야 합니다.")
    else:
        raise ValueError("Stride Preset은 LARGE / STANDARD / SMALL / CUSTOM 중 하나여야 합니다.")

    return {
        "stride_preset": preset,
        "stride": stride_value,
        "upsample": bool(upsample),
        "protect_highlights": bool(protect_highlights),
        "save_native_starmask": bool(save_native_starmask),
    }

def build_starnet_pyscript_command(
    *,
    stride_preset: str = "STANDARD",
    stride: int = 256,
    upsample: bool = False,
    protect_highlights: bool = True,
    save_native_starmask: bool = False,
) -> str:
    opts = _validate(
        stride_preset, stride, upsample,
        protect_highlights, save_native_starmask,
    )

    masks = ["subtract"]
    if opts["save_native_starmask"]:
        masks.append("starnet-mask")

    parts = [
        "pyscript",
        "StarNet.py",
        "--no-linear",
        "--stride", str(opts["stride"]),
        "--upsample" if opts["upsample"] else "--no-upsample",
        "--protect-highlights" if opts["protect_highlights"]
        else "--disable-highlights-protection",
        "--masks", ",".join(masks),
    ]
    return " ".join(parts)

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts", ".fits.fz", ".fit.fz"):
        if ext.startswith(".fits.") or ext.startswith(".fit."):
            p = Path(str(stem) + ext)
        else:
            p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def _find_prefixed(run_dir: Path, prefix: str):
    found = sorted(
        [p for p in run_dir.glob(prefix + "*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return found[0] if found else None

def _new_run_dir(project_dir: Path):
    run_dir = project_dir / "temp" / "starnet_preview" / uuid.uuid4().hex[:10]
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

def _run_starnet_once(project_dir: Path, config: dict, current: Path, target: str, params: dict):
    opts = _validate(
        params.get("stride_preset", "STANDARD"),
        params.get("stride", 256),
        params.get("upsample", False),
        params.get("protect_highlights", True),
        params.get("save_native_starmask", False),
    )
    run_dir = _new_run_dir(project_dir)

    starless_stem = run_dir / f"{target}_starnet_preview_starless"
    starless_jpg_stem = run_dir / f"{target}_starnet_preview_starless"
    stars_jpg_stem = run_dir / f"{target}_starnet_preview_stars"

    cmd = build_starnet_pyscript_command(**opts)

    commands = [
        "set32bits",
        "setext fits",
        f'cd "{normalize_siril_path(run_dir)}"',
        f'load "{normalize_siril_path(current)}"',
        cmd,
        f'save "{normalize_siril_path(starless_stem)}"',
        # The loaded image is now Starless and already non-linear.
        f'savejpg "{normalize_siril_path(starless_jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=run_dir)
    if proc.returncode != 0:
        raise SirilError(
            "StarNet 실행 실패\n"
            "Siril의 StarNet.py script와 StarNet2 CLI 설치를 확인하세요.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    starless_fits = _find_saved(starless_stem)
    subtract_layer = _find_prefixed(run_dir, "subtract_mask_")
    native_mask = (
        _find_prefixed(run_dir, "starnetmask_")
        if opts["save_native_starmask"] else None
    )
    starless_jpg = starless_jpg_stem.with_suffix(".jpg")

    if not starless_fits or not subtract_layer or not starless_jpg.exists():
        raise SirilError(
            "StarNet은 종료되었지만 필요한 Starless/Stars 출력 파일을 찾지 못했습니다.\n"
            f"Run dir: {run_dir}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    # Generate an honest preview of the additive stars layer.
    proc2 = run_script(config, [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(subtract_layer)}"',
        f'savejpg "{normalize_siril_path(stars_jpg_stem)}" 95',
        "close",
    ], cwd=run_dir)
    if proc2.returncode != 0:
        raise SirilError(
            "Stars 레이어 JPEG 미리보기 생성 실패\n"
            f"STDOUT:\n{proc2.stdout}\nSTDERR:\n{proc2.stderr}"
        )

    stars_jpg = stars_jpg_stem.with_suffix(".jpg")
    if not stars_jpg.exists():
        raise SirilError("Stars 레이어 JPEG 미리보기 파일을 찾지 못했습니다.")

    return {
        "run_dir": str(run_dir),
        "input_file": str(current),
        "starless_fits": str(starless_fits),
        "stars_fits": str(subtract_layer),
        "native_starmask": str(native_mask) if native_mask else None,
        "starless_jpg": str(starless_jpg),
        "stars_jpg": str(stars_jpg),
        "command": cmd,
        "parameters": opts,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

def preview_star_separation(project_dir: Path, config: dict, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_nonlinear_file(project)
    target = project["project"]["target_name"]

    result = _run_starnet_once(pdir, config, current, target, params)
    result["timestamp"] = iso_now()
    result["note"] = (
        "미리보기 StarNet 결과는 설정이 바뀌지 않으면 승인 시 재계산 없이 정식 작업파일로 승격할 수 있습니다."
    )

    (pdir / "logs" / "starnet_preview.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {
        "event": "STARNET_PREVIEW",
        "status": "SUCCESS",
        **result,
    })
    return result

def _same_params(a: dict, b: dict):
    keys = (
        "stride_preset", "stride", "upsample",
        "protect_highlights", "save_native_starmask",
    )
    return all(a.get(k) == b.get(k) for k in keys)

def apply_star_separation(
    project_dir: Path,
    config: dict,
    *,
    confirmed: bool = False,
    preview_meta: dict | None = None,
    **params,
):
    if not confirmed:
        raise PermissionError("실제 StarNet 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_nonlinear_file(project)
    p = project["project"]
    target = p["target_name"]

    opts = _validate(
        params.get("stride_preset", "STANDARD"),
        params.get("stride", 256),
        params.get("upsample", False),
        params.get("protect_highlights", True),
        params.get("save_native_starmask", False),
    )

    reused_preview = False
    run_result = None

    if preview_meta:
        meta_params = preview_meta.get("parameters", {})
        input_ok = Path(preview_meta.get("input_file", "")).resolve() == current.resolve()
        files_ok = (
            Path(preview_meta.get("starless_fits", "")).exists()
            and Path(preview_meta.get("stars_fits", "")).exists()
        )
        if input_ok and files_ok and _same_params(meta_params, opts):
            run_result = preview_meta
            reused_preview = True
        else:
            raise ValueError(
                "현재 설정/입력과 미리보기 결과가 일치하지 않습니다. StarNet 미리보기를 다시 실행하세요."
            )

    if run_result is None:
        run_result = _run_starnet_once(pdir, config, current, target, opts)

    out_dir = pdir / "working" / "08_starnet"
    out_dir.mkdir(parents=True, exist_ok=True)

    starless_out = out_dir / f"{target}_08_starless.fits"
    stars_out = out_dir / f"{target}_08_stars.fits"
    native_out = out_dir / f"{target}_08_starnetmask.fits"

    shutil.copy2(run_result["starless_fits"], starless_out)
    shutil.copy2(run_result["stars_fits"], stars_out)

    native_source = run_result.get("native_starmask")
    native_saved = None
    if opts["save_native_starmask"] and native_source and Path(native_source).exists():
        shutil.copy2(native_source, native_out)
        native_saved = native_out

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )
    starless_stats = analyze_pixels(
        starless_out,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["separation"] = {
        "engine": "Siril pyscript StarNet.py",
        "source_file": str(current),
        "starless_file": str(starless_out),
        "stars_file": str(stars_out),
        "native_starmask_file": str(native_saved) if native_saved else None,
        "stars_layer_method": "SUBTRACT",
        "recombine_mode": "ADD",
        "parameters": opts,
        "preview_promoted": bool(reused_preview),
        "timestamp": iso_now(),
    }

    p["current_file"] = str(starless_out)
    p["current_state"] = "STARS_SEPARATED"
    p["image_state"]["stars_removed"] = True
    p["image_state"]["linearity"] = "NONLINEAR"
    p["image_state"]["stretched"] = True
    p["next_task"] = make_starless_process_task()
    save_project(pdir, project)

    payload = {
        "event": "STARNET_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "starless_file": str(starless_out),
        "stars_file": str(stars_out),
        "native_starmask_file": str(native_saved) if native_saved else None,
        "parameters": opts,
        "pyscript_command": run_result.get("command"),
        "preview_promoted": bool(reused_preview),
        "analysis_before": before,
        "analysis_starless": starless_stats,
        "siril_stdout": run_result.get("stdout", ""),
        "siril_stderr": run_result.get("stderr", ""),
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / "starnet_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, starless_out, stars_out, payload

def skip_star_separation(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    if p.get("current_state") != "STRETCHED":
        raise ValueError("StarNet 건너뛰기는 STRETCHED 상태에서만 사용할 수 있습니다.")

    p["next_task"] = make_starnet_skipped_task()
    save_project(pdir, project)
    append_jsonl(pdir, {
        "event": "STARNET_SKIP",
        "status": "SKIPPED",
        "current_file": p.get("current_file"),
    })
    return project
