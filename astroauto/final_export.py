from __future__ import annotations
from pathlib import Path
import json
from astropy.io import fits

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl

def make_final_export_task(*, direct: bool = False) -> dict:
    return {
        "task_id": "FINALIZE_EXPORT",
        "title": "Final / Export",
        "summary": (
            "StarNet을 생략한 Non-linear 이미지를 최종 검토하고 FITS / TIFF / PNG로 내보냅니다."
            if direct else "재합성 결과를 최종 검토하고 FITS / TIFF / PNG로 내보냅니다."
        ),
        "purpose": "최종 결과를 작업용 FITS와 배포/편집용 출력 형식으로 안전하게 저장합니다.",
        "current_status": "EXPORT_READY / STARNET_SKIPPED / NONLINEAR" if direct else "RECOMBINED / NONLINEAR",
        "recommendations": {
            "final_working": "32-bit FITS",
            "export_fits": "32-bit FITS",
            "export_tiff": "16-bit TIFF",
            "export_png": "16-bit PNG",
            "final_name": "{TARGET}_final_Auto",
        },
        "cautions": [
            "PNG/TIFF는 현재 Non-linear 픽셀 결과를 그대로 저장합니다.",
            "v0.14.0은 ICC/sRGB 프로파일 변환을 강제하지 않습니다.",
            "최종 Export 전에 highlight clipping을 확인하세요.",
        ],
        "completion_criteria": [
            "최종 Working FITS 생성",
            "선택한 Export 파일 존재 확인",
            "State = EXPORTED",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def make_pipeline_complete_task() -> dict:
    return {
        "task_id": "PIPELINE_COMPLETE",
        "title": "기본 파이프라인 완료",
        "summary": "Gradient부터 Final Export까지 기본 처리 파이프라인이 완료되었습니다.",
        "purpose": "결과 확인 및 필요 시 외부 편집/추가 보정으로 이어갑니다.",
        "current_status": "EXPORTED",
        "recommendations": {
            "review": "FITS/TIFF/PNG 결과 확인",
            "next": "필요 시 Photoshop 등 외부 편집 또는 추가 세부 조정",
        },
        "cautions": [
            "외부 편집 후 다시 프로젝트로 가져오는 Round-trip은 향후 확장 기능입니다.",
        ],
        "completion_criteria": ["완료"],
        "actions": ["CONFIRM"],
    }

def migrate_ready_for_final_export(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    if p.get("current_state") == "RECOMBINED" and task.get("task_id") == "FINALIZE_EXPORT":
        p["next_task"] = make_final_export_task()
        save_project(pdir, project)
    elif p.get("current_state") == "EXPORT_READY" and task.get("task_id") == "FINALIZE_EXPORT":
        p["next_task"] = make_final_export_task(direct=True)
        save_project(pdir, project)
    elif p.get("current_state") == "STRETCHED" and task.get("task_id") == "POST_STARNET_SKIPPED":
        # Older projects were stranded after skipping StarNet. No pixels change.
        current = Path(p.get("current_file") or "")
        if (current.is_file() and p.get("image_state", {}).get("linearity") == "NONLINEAR"
                and p.get("image_state", {}).get("stretched") is True):
            p.setdefault("separation", {})["skipped"] = True
            p["separation"]["source_file"] = str(current)
            p["current_state"] = "EXPORT_READY"
            p["next_task"] = make_final_export_task(direct=True)
            save_project(pdir, project)
            append_jsonl(pdir, {"event": "MIGRATE_STARNET_SKIP", "status": "SUCCESS",
                                    "next_task": "FINALIZE_EXPORT"})
    return project

def _current_recombined(project: dict) -> Path:
    p = project["project"]
    if p.get("current_state") not in ("RECOMBINED", "EXPORT_READY"):
        raise ValueError("Final / Export는 RECOMBINED 또는 StarNet 생략(EXPORT_READY) 상태에서 시작합니다.")
    if p.get("image_state", {}).get("linearity") != "NONLINEAR":
        raise ValueError("v0.14 Final / Export는 Non-linear 최종 이미지용입니다.")

    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 최종 입력 FITS가 없습니다: {current}")
    return current

def _validate(
    *,
    export_fits: bool,
    export_tiff16: bool,
    export_png16: bool,
    tiff_deflate: bool,
    fits_checksum: bool,
    preview_jpeg_quality: int = 95,
):
    q = int(preview_jpeg_quality)
    if q < 1 or q > 100:
        raise ValueError("Preview JPEG Quality는 1~100 범위여야 합니다.")

    if not (export_fits or export_tiff16 or export_png16):
        raise ValueError("FITS / TIFF / PNG 중 하나 이상을 선택하세요.")

    return {
        "export_fits": bool(export_fits),
        "export_tiff16": bool(export_tiff16),
        "export_png16": bool(export_png16),
        "tiff_deflate": bool(tiff_deflate),
        "fits_checksum": bool(fits_checksum),
        "preview_jpeg_quality": q,
    }

def final_basename(target_name: str) -> str:
    return f"{target_name}_final_Auto"

def _find_saved(stem: Path, extensions: tuple[str, ...]):
    for ext in extensions:
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def _max_highlight_clip(stats: dict) -> float:
    ratios = [
        float(c.get("highlight_clip_ratio", 0) or 0)
        for c in (stats.get("channels") or {}).values()
    ]
    return max(ratios) if ratios else 0.0


def _write_fits_copyright(path: Path, value: str, *, checksum: bool):
    value = str(value or "").strip()
    if not value:
        return False
    path = Path(path)
    with fits.open(path, mode="update", checksum=False) as hdul:
        hdu = next((h for h in hdul if getattr(h, "data", None) is not None), hdul[0])
        hdu.header["COPYRGHT"] = (value, "Copyright / rights holder")
        if checksum:
            for item in hdul:
                try:
                    item.add_checksum(override_datasum=True)
                except Exception:
                    pass
        hdul.flush(output_verify="fix")
    return True

def preview_final_export(
    project_dir: Path,
    config: dict,
    *,
    preview_jpeg_quality: int = 95,
):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_recombined(project)
    p = project["project"]
    target = p["target_name"]

    quality = int(preview_jpeg_quality)
    if quality < 1 or quality > 100:
        raise ValueError("Preview JPEG Quality는 1~100 범위여야 합니다.")

    preview_dir = pdir / "output" / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    jpg_stem = preview_dir / f"{target}_final_review"

    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        f'savejpg "{normalize_siril_path(jpg_stem)}" {quality}',
        "close",
    ]

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Final 미리보기 생성 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    jpg = jpg_stem.with_suffix(".jpg")
    if not jpg.exists():
        raise SirilError(
            "Siril 실행 후 Final preview JPEG를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    stats = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "display_preview": str(jpg),
        "analysis": stats,
        "max_highlight_clip_ratio": _max_highlight_clip(stats),
        "preview_jpeg_quality": quality,
        "note": "Final preview에는 AutoStretch를 추가하지 않습니다.",
    }

    (pdir / "logs" / "final_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {
        "event": "FINAL_PREVIEW",
        "status": "SUCCESS",
        **meta,
    })
    return jpg, meta

def apply_final_export(
    project_dir: Path,
    config: dict,
    *,
    export_fits: bool,
    export_tiff16: bool,
    export_png16: bool,
    tiff_deflate: bool,
    fits_checksum: bool,
    preview_jpeg_quality: int = 95,
    confirmed: bool = False,
    preview_meta: dict | None = None,
):
    if not confirmed:
        raise PermissionError("Final / Export 실제 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current = _current_recombined(project)
    p = project["project"]
    target = p["target_name"]
    opts = _validate(
        export_fits=export_fits,
        export_tiff16=export_tiff16,
        export_png16=export_png16,
        tiff_deflate=tiff_deflate,
        fits_checksum=fits_checksum,
        preview_jpeg_quality=preview_jpeg_quality,
    )

    if not preview_meta:
        raise ValueError("Final 미리보기를 먼저 확인하세요.")
    if Path(preview_meta.get("input_file", "")).resolve() != current.resolve():
        raise ValueError("현재 Recombined 파일과 Final 미리보기의 입력이 다릅니다. 미리보기를 다시 실행하세요.")

    work_dir = pdir / "working" / "12_final"
    fits_dir = pdir / "output" / "fits"
    tiff_dir = pdir / "output" / "tiff"
    png_dir = pdir / "output" / "png"
    preview_dir = pdir / "output" / "preview"

    for d in (work_dir, fits_dir, tiff_dir, png_dir, preview_dir):
        d.mkdir(parents=True, exist_ok=True)

    base = final_basename(target)
    working_stem = work_dir / f"{target}_12_final"
    fits_stem = fits_dir / base
    tiff_stem = tiff_dir / base
    png_stem = png_dir / base
    jpg_stem = preview_dir / base

    save_flags = " -chksum" if opts["fits_checksum"] else ""

    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        f'save "{normalize_siril_path(working_stem)}"{save_flags}',
    ]

    if opts["export_fits"]:
        commands.append(
            f'save "{normalize_siril_path(fits_stem)}"{save_flags}'
        )

    if opts["export_tiff16"]:
        tif_cmd = f'savetif "{normalize_siril_path(tiff_stem)}"'
        if opts["tiff_deflate"]:
            tif_cmd += " -deflate"
        commands.append(tif_cmd)

    if opts["export_png16"]:
        commands.append(
            f'savepng "{normalize_siril_path(png_stem)}"'
        )

    commands.extend([
        f'savejpg "{normalize_siril_path(jpg_stem)}" {opts["preview_jpeg_quality"]}',
        "close",
    ])

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "Final / Export 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    working_final = _find_saved(working_stem, (".fits", ".fit", ".fts"))
    if not working_final:
        raise SirilError(
            "Final Working FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    outputs = {
        "working_final_fits": str(working_final),
        "fits": None,
        "tiff16": None,
        "png16": None,
        "preview_jpg": None,
    }

    if opts["export_fits"]:
        f = _find_saved(fits_stem, (".fits", ".fit", ".fts"))
        if not f:
            raise SirilError("선택한 Final FITS Export 파일을 찾지 못했습니다.")
        outputs["fits"] = str(f)

    if opts["export_tiff16"]:
        f = _find_saved(tiff_stem, (".tif", ".tiff"))
        if not f:
            raise SirilError("선택한 16-bit TIFF Export 파일을 찾지 못했습니다.")
        outputs["tiff16"] = str(f)

    if opts["export_png16"]:
        f = _find_saved(png_stem, (".png",))
        if not f:
            raise SirilError("선택한 16-bit PNG Export 파일을 찾지 못했습니다.")
        outputs["png16"] = str(f)

    preview_jpg = jpg_stem.with_suffix(".jpg")
    if not preview_jpg.exists():
        raise SirilError("Final preview JPG를 찾지 못했습니다.")
    outputs["preview_jpg"] = str(preview_jpg)

    copyright_text = str((p.get("metadata") or {}).get("copyright") or "").strip()
    copyright_embedded = []
    if copyright_text:
        if _write_fits_copyright(working_final, copyright_text, checksum=opts["fits_checksum"]):
            copyright_embedded.append(str(working_final))
        if outputs.get("fits"):
            export_fits_path = Path(outputs["fits"])
            if export_fits_path.resolve() != working_final.resolve():
                if _write_fits_copyright(export_fits_path, copyright_text, checksum=opts["fits_checksum"]):
                    copyright_embedded.append(str(export_fits_path))

    stats = analyze_pixels(
        working_final,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    p["finalization"] = {
        "finalized": True,
        "exported": True,
        "base_name": base,
        "source_file": str(current),
        "working_final_file": str(working_final),
        "outputs": outputs,
        "options": opts,
        "states": ["FINALIZED", "EXPORTED"],
        "timestamp": iso_now(),
        "metadata": {
            "copyright": copyright_text or None,
            "copyright_embedded_fits": copyright_embedded,
            "raster_note": "TIFF/PNG에는 별도 Copyright 메타데이터를 강제 삽입하지 않습니다.",
        },
        "notes": {
            "fits_internal_precision": "32-bit float path via set32bits",
            "tiff": "16-bit per channel via savetif",
            "png": "16-bit per channel when source is 16/32-bit via savepng",
            "icc_profile": "not force-set by v0.14.0",
        },
    }

    p["current_file"] = str(working_final)
    p["current_state"] = "EXPORTED"
    p["image_state"]["linearity"] = "NONLINEAR"
    p["image_state"]["stretched"] = True
    p["next_task"] = make_pipeline_complete_task()
    save_project(pdir, project)

    payload = {
        "event": "FINAL_EXPORT_APPLY",
        "status": "SUCCESS",
        "source_file": str(current),
        "working_final_file": str(working_final),
        "base_name": base,
        "outputs": outputs,
        "options": opts,
        "metadata": {
            "copyright": copyright_text or None,
            "copyright_embedded_fits": copyright_embedded,
        },
        "analysis": stats,
        "max_highlight_clip_ratio": _max_highlight_clip(stats),
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }

    append_jsonl(pdir, payload)
    (pdir / "logs" / "final_export.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, outputs, payload
