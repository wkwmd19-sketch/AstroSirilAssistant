from __future__ import annotations
import argparse
from pathlib import Path
import sys
import json

from astroauto.config import load_app_config
from astroauto.siril import get_siril_info
from astroauto.project import create_project, load_project, save_project
from astroauto.analyzer import analyze_project, confirm_linearity
from astroauto.calibration import scan_project_calibration
from astroauto.workflow import format_task, next_task_after_analysis
from astroauto.logging_utils import append_jsonl
from astroauto.state_actions import confirm_input_stage, confirm_calibration_status, confirm_star_trail_mode
from astroauto.gradient import preview_gradient, apply_gradient
from astroauto.spcc import fetch_spcc_lists, inspect_wcs, preview_spcc, apply_spcc
from astroauto.denoise import preview_denoise, apply_denoise, skip_denoise
from astroauto.deblur import preview_deblur, apply_deblur, skip_deblur
from astroauto.ghs import preview_ghs, apply_ghs, begin_additional_ghs, finish_ghs
from astroauto.star_separation import preview_star_separation, apply_star_separation, skip_star_separation
from astroauto.starless_processing import preview_starless_processing, apply_starless_processing, skip_starless_processing
from astroauto.recommendations import recommend_starless, recommend_stars
from astroauto.stars_processing import preview_stars_processing, apply_stars_processing, skip_stars_processing
from astroauto.recombine import preview_recombine, apply_recombine, recommend_recombine
from astroauto.final_export import preview_final_export, apply_final_export
from astroauto.sequence_project import create_sequence_project
from astroauto.preprocess_engine import build_preprocess_plan, execute_preprocess

CATEGORIES = [
    "GALAXY", "EMISSION_NEBULA", "REFLECTION_NEBULA", "DARK_NEBULA",
    "PLANETARY_NEBULA", "SUPERNOVA_REMNANT", "OPEN_CLUSTER",
    "GLOBULAR_CLUSTER", "MILKYWAY", "GENERAL_STARFIELD", "STAR_TRAIL",
    "COMET", "PLANETARY_LUNAR", "MOSAIC", "UNKNOWN"
]

SOURCE_STAGES = [
    "LIGHT_SEQUENCE", "SINGLE_LIGHT", "REGISTERED_SEQUENCE",
    "STACKED_LINEAR", "STACKED_NONLINEAR", "UNKNOWN"
]

CAL_STATUS = ["RAW_UNCALIBRATED", "PRECALIBRATED", "UNKNOWN"]
STAR_TRAIL_MODES = ["STAR_TRAIL_SKY", "STAR_TRAIL_LANDSCAPE", "UNKNOWN"]

def cmd_doctor(args):
    cfg = load_app_config()
    print("AstroSirilAssistant v0.14.0")
    print(f"Project root: {cfg['app']['project_root']}")
    try:
        info = get_siril_info(cfg)
        print(f"Siril CLI: {info.executable}")
        print(f"Siril version: {info.version}")
        print("Siril connection: OK")
    except Exception as e:
        print(f"Siril connection: FAIL\n{e}")
        return 1
    return 0

def cmd_new(args):
    cfg = load_app_config()
    root = Path(args.root or cfg["app"]["project_root"])
    pdir = create_project(
        root=root, target=args.target, capture_date=args.date,
        category=args.category, input_file=Path(args.input),
        copy_input=not args.no_copy,
    )
    print(f"프로젝트 생성: {pdir}")
    print(f"캘리브레이션 폴더: {pdir / 'calibration'}")
    if args.analyze:
        project, report, task = analyze_project(pdir, cfg)
        print("\n" + format_task(task))
    return 0

def cmd_analyze(args):
    cfg = load_app_config()
    project, report, task = analyze_project(Path(args.project), cfg)
    print(format_task(task))
    return 0

def cmd_status(args):
    project = load_project(Path(args.project))
    p = project["project"]
    print(f"Project: {p['id']}")
    print(f"State: {p['current_state']}")
    print(f"Category: {p['target']['category']}")
    print(f"Source stage: {p.get('input_stage', {}).get('source_stage', 'UNKNOWN')}")
    print(f"Calibration input status: {p.get('calibration', {}).get('input_status', 'UNKNOWN')}")
    print(f"Star trail mode: {p.get('star_trail', {}).get('mode', 'UNKNOWN')}")
    print(f"Linearity: {p['image_state']['linearity']}")
    print(f"Current file: {p['current_file']}")
    if p.get("next_task"):
        print("\n" + format_task(p["next_task"]))
    return 0

def cmd_confirm(args):
    project = confirm_linearity(Path(args.project), args.linearity)
    print(f"Linearity를 {args.linearity.upper()}로 확정했습니다.")
    print("\n" + format_task(project["project"]["next_task"]))
    return 0

def cmd_confirm_stage(args):
    project = confirm_input_stage(Path(args.project), args.stage)
    print(f"입력 단계를 {args.stage.upper()}로 확정했습니다.")
    print("\n" + format_task(project["project"]["next_task"]))
    return 0

def cmd_confirm_calibration(args):
    project = confirm_calibration_status(Path(args.project), args.status)
    print(f"캘리브레이션 상태를 {args.status.upper()}로 확정했습니다.")
    print("\n" + format_task(project["project"]["next_task"]))
    return 0

def cmd_confirm_star_trail_mode(args):
    project = confirm_star_trail_mode(Path(args.project), args.mode)
    print(f"별 일주 모드를 {args.mode.upper()}로 확정했습니다.")
    print("\n" + format_task(project["project"]["next_task"]))
    return 0

def cmd_calibration_check(args):
    cfg = load_app_config()
    project, report = scan_project_calibration(Path(args.project), cfg)
    rec = report["recommendation"]
    print("캘리브레이션 프레임 검사 완료")
    for key in ("dark", "bias", "flat", "dark_flat"):
        scan = report["frames"][key]
        comp = report["compatibility"][key]
        print(f"- {key}: {scan['count']}장 / {comp['status']}")
    print(f"\n추천: {rec['action']}")
    print(rec['summary'])
    for w in rec.get("warnings", []):
        print(f"주의: {w}")
    print(f"\n상세 로그: {Path(args.project) / 'logs' / 'calibration_report.json'}")
    return 0


def cmd_new_sequence(args):
    cfg = load_app_config()
    root = Path(args.root or cfg["app"]["project_root"])
    pdir = create_sequence_project(
        root=root,
        target=args.target,
        capture_date=args.date,
        category=args.category,
        lights_dir=Path(args.lights),
        darks_dir=Path(args.darks) if args.darks else None,
        flats_dir=Path(args.flats) if args.flats else None,
        bias_dir=Path(args.bias) if args.bias else None,
        dark_flats_dir=Path(args.dark_flats) if args.dark_flats else None,
        camera_mode=args.camera_mode,
        input_status=args.input_status,
        copy_inputs=args.copy_inputs,
    )
    print(f"Sequence 프로젝트 생성: {pdir}")
    print("다음: preprocess-plan로 실행 계획을 확인하세요.")
    return 0

def cmd_preprocess_plan(args):
    plan, plan_path, script_path = build_preprocess_plan(Path(args.project))
    print("=== Siril 전처리/스택 계획 ===")
    print(f"Lights: {plan['counts']['lights']}장")
    print(f"Dark: {plan['counts']['dark']}장")
    print(f"Flat: {plan['counts']['flat']}장")
    print(f"Bias: {plan['counts']['bias']}장")
    print(f"Dark-flat: {plan['counts']['dark_flat']}장")
    print(f"Camera mode: {plan['camera_mode']}")
    if plan["warnings"]:
        print("\n주의:")
        for item in plan["warnings"]:
            print(f"- {item}")
    print("\n실행 단계:")
    for phase in plan["phases"]:
        print(f"- {phase}")
    print(f"\nPlan: {plan_path}")
    print(f"Siril script: {script_path}")
    print("\n실제 실행은 preprocess-run --yes 로 승인 후 진행합니다.")
    return 0

def cmd_preprocess_run(args):
    if not args.yes:
        raise PermissionError("실제 실행에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, plan = execute_preprocess(Path(args.project), cfg, confirmed=True)
    print("Calibration / Registration / Stack 완료")
    print(f"출력: {output}")
    print("다음 작업: Background / Gradient Correction")
    return 0


def cmd_gradient_preview(args):
    cfg = load_app_config()
    jpg, linear_preview, meta = preview_gradient(
        Path(args.project), cfg,
        samples=args.samples,
        tolerance=args.tolerance,
        smooth=args.smooth,
        dither=args.dither,
    )
    print(f"표시용 JPEG: {jpg}")
    print(f"Linear 미리보기 FITS: {linear_preview}")
    return 0

def cmd_gradient_apply(args):
    if not args.yes:
        raise PermissionError("실제 Gradient 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, log = apply_gradient(
        Path(args.project), cfg,
        samples=args.samples,
        tolerance=args.tolerance,
        smooth=args.smooth,
        dither=args.dither,
        confirmed=True,
    )
    print(f"Gradient Correction 완료: {output}")
    print("\\n" + format_task(project["project"]["next_task"]))
    return 0


def cmd_spcc_lists(args):
    cfg = load_app_config()
    result = fetch_spcc_lists(cfg, mode=args.mode)
    for key, values in result["lists"].items():
        print(f"[{key}] ({len(values)})")
        for item in values:
            print(f"  {item}")
    return 0

def cmd_spcc_wcs(args):
    project = load_project(Path(args.project))
    current = Path(project["project"]["current_file"])
    status = inspect_wcs(current)
    print(json.dumps(status, ensure_ascii=False, indent=2, default=str))
    return 0

def _spcc_cli_params(args):
    return dict(
        mode=args.mode,
        sensor=args.sensor,
        osc_filter=args.osc_filter or "",
        osc_lpf=args.osc_lpf or "",
        white_reference=args.white_reference,
        catalog=args.catalog,
        bgtol_lower=args.bgtol_lower,
        bgtol_upper=args.bgtol_upper,
    )

def cmd_spcc_preview(args):
    cfg = load_app_config()
    jpg, linear_preview, meta = preview_spcc(
        Path(args.project), cfg, **_spcc_cli_params(args)
    )
    print(f"JPEG: {jpg}")
    print(f"Linear preview: {linear_preview}")
    return 0

def cmd_spcc_apply(args):
    if not args.yes:
        raise PermissionError("실제 SPCC 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_spcc(
        Path(args.project), cfg, confirmed=True, **_spcc_cli_params(args)
    )
    print(f"SPCC 완료: {output}")
    return 0


def _denoise_cli_params(args):
    if args.engine == "SYQON_PRISM":
        return dict(
            engine=args.engine,
            model=args.prism_model,
            tile_size=args.prism_tile,
            overlap=args.prism_overlap,
            pad=args.prism_pad,
            modulation=args.modulation,
            use_gpu=not args.no_gpu,
            stretch_method=args.stretch_method,
            stretch_target=args.stretch_target,
        )
    return dict(
        engine="SIRIL_NATIVE",
        modulation=args.modulation,
        cosmetic_correction=not args.no_cosmetic,
        da3d=args.da3d,
        independent_channels=args.independent,
    )

def cmd_denoise_preview(args):
    cfg = load_app_config()
    jpg, linear_preview, meta = preview_denoise(
        Path(args.project), cfg, **_denoise_cli_params(args)
    )
    print(f"Engine: {meta['engine']}")
    print(f"JPEG: {jpg}")
    print(f"Linear preview: {linear_preview}")
    print(f"Command: {meta['engine_command']}")
    return 0

def cmd_denoise_apply(args):
    if not args.yes:
        raise PermissionError("실제 Denoise 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_denoise(
        Path(args.project), cfg, confirmed=True, **_denoise_cli_params(args)
    )
    print(f"Denoise 완료: {output}")
    print(f"Engine: {payload['engine']}")
    return 0

def cmd_denoise_skip(args):
    skip_denoise(Path(args.project))
    print("Denoise를 건너뛰었습니다.")
    return 0

def _deblur_cli_params(args):
    if args.engine == "SYQON_PARALLAX":
        return dict(
            engine=args.engine,
            edition=args.edition,
            correct=not args.no_correct,
            star_level=args.star_level,
            sharpen=args.sharpen,
            tile=args.parallax_tile,
            overlap=args.parallax_overlap,
            pad=args.parallax_pad,
            use_mtf=not args.no_mtf,
            mtf_target=args.mtf_target,
            linked=args.linked,
            use_gpu=not args.no_gpu,
        )
    return dict(
        engine="SIRIL_RL",
        symmetric_psf=args.symmetric_psf,
        kernel_size=args.kernel_size,
        iterations=args.iterations,
        regularization=args.regularization,
        alpha=args.alpha,
        multiplicative=args.multiplicative,
    )

def cmd_deblur_preview(args):
    cfg = load_app_config()
    jpg, linear_preview, meta = preview_deblur(
        Path(args.project), cfg, **_deblur_cli_params(args)
    )
    print(f"Engine: {meta['engine']}")
    print(f"JPEG: {jpg}")
    print(f"Linear preview: {linear_preview}")
    print(f"Command: {meta['engine_command']}")
    return 0

def cmd_deblur_apply(args):
    if not args.yes:
        raise PermissionError("실제 Restoration 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_deblur(
        Path(args.project), cfg, confirmed=True, **_deblur_cli_params(args)
    )
    print(f"Restoration 완료: {output}")
    print(f"Engine: {payload['engine']}")
    return 0

def cmd_deblur_skip(args):
    skip_deblur(Path(args.project))
    print("Restoration을 건너뛰었습니다.")
    return 0


def _ghs_cli_params(args):
    if args.method == "AUTO_GHS":
        return dict(
            linked=args.linked,
            shadows_clip=args.shadows_clip,
            stretch_amount=args.d,
            b=args.b,
            lp=args.lp,
            hp=args.hp,
            clip_mode=args.clip_mode,
        )
    return dict(
        d=args.d,
        b=args.b,
        lp=args.lp,
        sp=args.sp,
        hp=args.hp,
        luminance_mode=args.luminance_mode,
        clip_mode=args.clip_mode,
    )


def cmd_ghs_preview(args):
    cfg = load_app_config()
    jpg, preview_fits, meta = preview_ghs(
        Path(args.project), cfg,
        method=args.method,
        **_ghs_cli_params(args),
    )
    print(f"JPEG: {jpg}")
    print(f"Preview FITS: {preview_fits}")
    print(f"Command: {meta['ghs_command']}")
    return 0

def cmd_ghs_apply(args):
    if not args.yes:
        raise PermissionError("실제 GHS 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_ghs(
        Path(args.project), cfg,
        method=args.method,
        confirmed=True,
        **_ghs_cli_params(args),
    )
    print(f"GHS Pass {payload['pass_number']} 완료: {output}")
    return 0

def cmd_ghs_additional(args):
    project = begin_additional_ghs(Path(args.project))
    print("추가 GHS Pass 모드로 전환했습니다.")
    return 0

def cmd_ghs_finish(args):
    project = finish_ghs(Path(args.project))
    print("GHS Stretch를 완료하고 StarNet 단계로 이동했습니다.")
    return 0


def _starnet_cli_params(args):
    return dict(
        stride_preset=args.stride_preset,
        stride=args.stride,
        upsample=args.upsample,
        protect_highlights=not args.disable_highlights,
        save_native_starmask=args.native_starmask,
    )

def cmd_starnet_preview(args):
    cfg = load_app_config()
    meta = preview_star_separation(
        Path(args.project), cfg, **_starnet_cli_params(args)
    )
    print(f"Starless FITS: {meta['starless_fits']}")
    print(f"Stars FITS: {meta['stars_fits']}")
    print(f"Starless JPEG: {meta['starless_jpg']}")
    print(f"Stars JPEG: {meta['stars_jpg']}")
    return 0

def cmd_starnet_apply(args):
    if not args.yes:
        raise PermissionError("실제 StarNet 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, starless, stars, payload = apply_star_separation(
        Path(args.project),
        cfg,
        confirmed=True,
        preview_meta=None,
        **_starnet_cli_params(args),
    )
    print(f"Starless: {starless}")
    print(f"Stars: {stars}")
    return 0

def cmd_starnet_skip(args):
    skip_star_separation(Path(args.project))
    print("StarNet을 건너뛰었습니다.")
    return 0


def _starless_cli_params(args):
    return dict(
        clahe_enabled=not args.no_clahe,
        clahe_clip_limit=args.clahe_clip,
        clahe_tile_size=args.clahe_tile,
        saturation_enabled=not args.no_saturation,
        saturation_amount=args.saturation,
        saturation_background_factor=args.background_factor,
        saturation_hue_range=args.hue_range,
    )

def cmd_starless_recommend(args):
    cfg = load_app_config()
    rec = recommend_starless(Path(args.project), cfg)
    print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
    return 0

def cmd_starless_preview(args):
    cfg = load_app_config()
    jpg, preview_fits, meta = preview_starless_processing(
        Path(args.project), cfg, **_starless_cli_params(args)
    )
    print(f"JPEG: {jpg}")
    print(f"Preview FITS: {preview_fits}")
    return 0

def cmd_starless_apply(args):
    if not args.yes:
        raise PermissionError("실제 Starless Processing 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_starless_processing(
        Path(args.project), cfg, confirmed=True, **_starless_cli_params(args)
    )
    print(f"Starless Processing 완료: {output}")
    return 0

def cmd_starless_skip(args):
    skip_starless_processing(Path(args.project))
    print("Starless Processing을 건너뛰었습니다.")
    return 0


def _stars_cli_params(args):
    return dict(
        brightness_scale=args.brightness,
        saturation_enabled=not args.no_saturation,
        saturation_amount=args.saturation,
        saturation_background_factor=args.background_factor,
        saturation_hue_range=args.hue_range,
    )

def cmd_stars_recommend(args):
    cfg = load_app_config()
    rec = recommend_stars(Path(args.project), cfg)
    print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
    return 0

def cmd_stars_preview(args):
    cfg = load_app_config()
    jpg, preview_fits, meta = preview_stars_processing(
        Path(args.project), cfg, **_stars_cli_params(args)
    )
    print(f"JPEG: {jpg}")
    print(f"Preview FITS: {preview_fits}")
    return 0

def cmd_stars_apply(args):
    if not args.yes:
        raise PermissionError("실제 Stars Processing 적용에는 --yes 승인이 필요합니다.")
    cfg = load_app_config()
    project, output, payload = apply_stars_processing(
        Path(args.project), cfg, confirmed=True, **_stars_cli_params(args)
    )
    print(f"Stars Processing 완료: {output}")
    return 0

def cmd_stars_skip(args):
    skip_stars_processing(Path(args.project))
    print("Stars Processing을 건너뛰었습니다.")
    return 0


def cmd_recombine_recommend(args):
    rec = recommend_recombine(Path(args.project))
    print(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
    return 0

def cmd_recombine_preview(args):
    cfg = load_app_config()
    jpg, preview_fits, meta = preview_recombine(
        Path(args.project), cfg,
        star_weight=args.star_weight,
        rescale_output=args.rescale,
    )
    print(f"JPEG: {jpg}")
    print(f"Preview FITS: {preview_fits}")
    print(f"Expression: {meta['expression']}")
    return 0

def cmd_recombine_apply(args):
    raise PermissionError(
        "CLI Recombine apply는 v0.12.0에서 preview_meta 승격 구조를 사용하므로 GUI 승인 경로를 사용하세요."
    )


def cmd_final_preview(args):
    cfg = load_app_config()
    jpg, meta = preview_final_export(
        Path(args.project), cfg,
        preview_jpeg_quality=args.quality,
    )
    print(f"Final preview: {jpg}")
    print(f"Highlight clipping: {meta['max_highlight_clip_ratio']}")
    return 0

def build_parser():
    parser = argparse.ArgumentParser(description="AstroSirilAssistant v0.14.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("new")
    p.add_argument("--input", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--category", choices=CATEGORIES, default="UNKNOWN")
    p.add_argument("--root")
    p.add_argument("--no-copy", action="store_true")
    p.add_argument("--analyze", action="store_true")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("analyze")
    p.add_argument("project")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("status")
    p.add_argument("project")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("confirm-linearity")
    p.add_argument("project")
    p.add_argument("linearity", choices=["LINEAR", "NONLINEAR", "linear", "nonlinear"])
    p.set_defaults(func=cmd_confirm)

    p = sub.add_parser("confirm-input-stage")
    p.add_argument("project")
    p.add_argument("stage", choices=SOURCE_STAGES + [x.lower() for x in SOURCE_STAGES])
    p.set_defaults(func=cmd_confirm_stage)

    p = sub.add_parser("confirm-calibration")
    p.add_argument("project")
    p.add_argument("status", choices=CAL_STATUS + [x.lower() for x in CAL_STATUS])
    p.set_defaults(func=cmd_confirm_calibration)

    p = sub.add_parser("confirm-star-trail-mode")
    p.add_argument("project")
    p.add_argument("mode", choices=STAR_TRAIL_MODES + [x.lower() for x in STAR_TRAIL_MODES])
    p.set_defaults(func=cmd_confirm_star_trail_mode)

    p = sub.add_parser("calibration-check")
    p.add_argument("project")
    p.set_defaults(func=cmd_calibration_check)


    p = sub.add_parser("new-sequence", help="FITS Light sequence 프로젝트 생성")
    p.add_argument("--lights", required=True)
    p.add_argument("--darks")
    p.add_argument("--flats")
    p.add_argument("--bias")
    p.add_argument("--dark-flats")
    p.add_argument("--target", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--category", choices=CATEGORIES, default="UNKNOWN")
    p.add_argument("--camera-mode", choices=["AUTO", "OSC", "MONO"], default="AUTO")
    p.add_argument("--input-status", choices=["RAW_UNCALIBRATED", "PRECALIBRATED"], default="RAW_UNCALIBRATED")
    p.add_argument("--root")
    p.add_argument("--copy-inputs", action="store_true")
    p.set_defaults(func=cmd_new_sequence)

    p = sub.add_parser("preprocess-plan", help="Siril Calibration/Register/Stack 계획 생성")
    p.add_argument("project")
    p.set_defaults(func=cmd_preprocess_plan)

    p = sub.add_parser("preprocess-run", help="승인 후 Siril Calibration/Register/Stack 실제 실행")
    p.add_argument("project")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_preprocess_run)


    p = sub.add_parser("gradient-preview", help="RBF Gradient 미리보기 생성")
    p.add_argument("project")
    p.add_argument("--samples", type=int, default=20)
    p.add_argument("--tolerance", type=float, default=1.0)
    p.add_argument("--smooth", type=float, default=0.5)
    p.add_argument("--dither", action="store_true")
    p.set_defaults(func=cmd_gradient_preview)

    p = sub.add_parser("gradient-apply", help="승인 후 RBF Gradient 실제 적용")
    p.add_argument("project")
    p.add_argument("--samples", type=int, default=20)
    p.add_argument("--tolerance", type=float, default=1.0)
    p.add_argument("--smooth", type=float, default=0.5)
    p.add_argument("--dither", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_gradient_apply)


    p = sub.add_parser("spcc-lists", help="현재 Siril SPCC 센서/필터 목록 출력")
    p.add_argument("--mode", choices=["OSC", "MONO"], default="OSC")
    p.set_defaults(func=cmd_spcc_lists)

    p = sub.add_parser("spcc-wcs", help="현재 프로젝트 FITS의 WCS 상태 확인")
    p.add_argument("project")
    p.set_defaults(func=cmd_spcc_wcs)

    def add_spcc_args(p):
        p.add_argument("project")
        p.add_argument("--mode", choices=["OSC", "MONO"], default="OSC")
        p.add_argument("--sensor", required=True)
        p.add_argument("--osc-filter", default="")
        p.add_argument("--osc-lpf", default="")
        p.add_argument("--white-reference", default="Average Spiral Galaxy")
        p.add_argument("--catalog", choices=["AUTO", "GAIA_ONLINE", "LOCAL_GAIA"], default="AUTO")
        p.add_argument("--bgtol-lower", type=float, default=-2.8)
        p.add_argument("--bgtol-upper", type=float, default=2.0)

    p = sub.add_parser("spcc-preview", help="Plate Solve + SPCC 미리보기")
    add_spcc_args(p)
    p.set_defaults(func=cmd_spcc_preview)

    p = sub.add_parser("spcc-apply", help="승인 후 Plate Solve + SPCC 실제 적용")
    add_spcc_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_spcc_apply)


    def add_denoise_args(p):
        p.add_argument("project")
        p.add_argument("--engine", choices=["SYQON_PRISM", "SIRIL_NATIVE"], default="SYQON_PRISM")
        p.add_argument("--modulation", type=float, default=1.0)

        # Prism
        p.add_argument("--prism-model", choices=["mini", "deep"], default="mini")
        p.add_argument("--prism-tile", type=int, default=512)
        p.add_argument("--prism-overlap", type=int, default=96)
        p.add_argument("--prism-pad", type=int, default=96)
        p.add_argument("--stretch-method", choices=["statistical", "ihs"], default="statistical")
        p.add_argument("--stretch-target", type=float, default=0.25)
        p.add_argument("--no-gpu", action="store_true")

        # Siril Native
        p.add_argument("--no-cosmetic", action="store_true")
        p.add_argument("--da3d", action="store_true")
        p.add_argument("--independent", action="store_true")

    p = sub.add_parser("denoise-preview", help="Prism/Siril Denoise 미리보기")
    add_denoise_args(p)
    p.set_defaults(func=cmd_denoise_preview)

    p = sub.add_parser("denoise-apply", help="승인 후 Prism/Siril Denoise 실제 적용")
    add_denoise_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_denoise_apply)

    p = sub.add_parser("denoise-skip", help="Denoise 단계 건너뛰기")
    p.add_argument("project")
    p.set_defaults(func=cmd_denoise_skip)

    def add_deblur_args(p):
        p.add_argument("project")
        p.add_argument("--engine", choices=["SYQON_PARALLAX", "SIRIL_RL"], default="SYQON_PARALLAX")

        # Parallax
        p.add_argument("--edition", choices=["nano", "pro"], default="nano")
        p.add_argument("--no-correct", action="store_true")
        p.add_argument("--star-level", type=float, default=3.0)
        p.add_argument("--sharpen", type=float, default=1.0)
        p.add_argument("--parallax-tile", type=int, default=512)
        p.add_argument("--parallax-overlap", type=int, default=64)
        p.add_argument("--parallax-pad", type=int, default=96)
        p.add_argument("--no-mtf", action="store_true")
        p.add_argument("--mtf-target", type=float, default=0.25)
        p.add_argument("--linked", action="store_true")
        p.add_argument("--no-gpu", action="store_true")

        # Siril RL
        p.add_argument("--symmetric-psf", action="store_true")
        p.add_argument("--kernel-size", type=int)
        p.add_argument("--iterations", type=int, default=10)
        p.add_argument("--regularization", choices=["NONE", "TV", "FH"], default="NONE")
        p.add_argument("--alpha", type=float, default=3000)
        p.add_argument("--multiplicative", action="store_true")

    p = sub.add_parser("deblur-preview", help="Parallax/Siril Restoration 미리보기")
    add_deblur_args(p)
    p.set_defaults(func=cmd_deblur_preview)

    p = sub.add_parser("deblur-apply", help="승인 후 Parallax/Siril Restoration 실제 적용")
    add_deblur_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_deblur_apply)

    p = sub.add_parser("deblur-skip", help="Restoration 단계 건너뛰기")
    p.add_argument("project")
    p.set_defaults(func=cmd_deblur_skip)


    def add_ghs_args(p):
        p.add_argument("project")
        p.add_argument("--method", choices=["AUTO_GHS", "MANUAL_GHT"], default="AUTO_GHS")
        p.add_argument("--linked", action="store_true", default=True)
        p.add_argument("--shadows-clip", type=float, default=-2.8)
        p.add_argument("--d", type=float, default=1.0)
        p.add_argument("--b", type=float, default=13.0)
        p.add_argument("--lp", type=float, default=0.0)
        p.add_argument("--sp", type=float, default=0.0)
        p.add_argument("--hp", type=float, default=0.7)
        p.add_argument("--luminance-mode", choices=["HUMAN", "EVEN", "INDEPENDENT"], default="HUMAN")
        p.add_argument("--clip-mode", choices=["rgbblend", "clip", "rescale", "globalrescale"], default="rgbblend")

    p = sub.add_parser("ghs-preview", help="GHS / AutoGHS 미리보기")
    add_ghs_args(p)
    p.set_defaults(func=cmd_ghs_preview)

    p = sub.add_parser("ghs-apply", help="승인 후 GHS 실제 적용")
    add_ghs_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_ghs_apply)

    p = sub.add_parser("ghs-additional", help="추가 GHS Pass 모드로 전환")
    p.add_argument("project")
    p.set_defaults(func=cmd_ghs_additional)

    p = sub.add_parser("ghs-finish", help="GHS Stretch 완료 후 StarNet 단계로 이동")
    p.add_argument("project")
    p.set_defaults(func=cmd_ghs_finish)


    def add_starnet_args(p):
        p.add_argument("project")
        p.add_argument(
            "--stride-preset",
            choices=["STANDARD", "LARGE", "SMALL", "CUSTOM"],
            default="STANDARD",
        )
        p.add_argument("--stride", type=int, default=256)
        p.add_argument("--upsample", action="store_true")
        p.add_argument("--disable-highlights", action="store_true")
        p.add_argument("--native-starmask", action="store_true")

    p = sub.add_parser("starnet-preview", help="StarNet2 Starless/Stars 미리보기")
    add_starnet_args(p)
    p.set_defaults(func=cmd_starnet_preview)

    p = sub.add_parser("starnet-apply", help="승인 후 StarNet2 별 분리 실제 적용")
    add_starnet_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_starnet_apply)

    p = sub.add_parser("starnet-skip", help="StarNet 별 분리 건너뛰기")
    p.add_argument("project")
    p.set_defaults(func=cmd_starnet_skip)


    def add_starless_args(p):
        p.add_argument("project")
        p.add_argument("--no-clahe", action="store_true")
        p.add_argument("--clahe-clip", type=float, default=1.5)
        p.add_argument("--clahe-tile", type=int, default=12)
        p.add_argument("--no-saturation", action="store_true")
        p.add_argument("--saturation", type=float, default=0.10)
        p.add_argument("--background-factor", type=float, default=1.10)
        p.add_argument("--hue-range", type=int, default=6)

    p = sub.add_parser("starless-recommend", help="천체 특징 + 이미지 통계 기반 Starless 추천값")
    p.add_argument("project")
    p.set_defaults(func=cmd_starless_recommend)

    p = sub.add_parser("starless-preview", help="Starless CLAHE/Saturation 미리보기")
    add_starless_args(p)
    p.set_defaults(func=cmd_starless_preview)

    p = sub.add_parser("starless-apply", help="승인 후 Starless Processing 실제 적용")
    add_starless_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_starless_apply)

    p = sub.add_parser("starless-skip", help="Starless Processing 건너뛰기")
    p.add_argument("project")
    p.set_defaults(func=cmd_starless_skip)


    def add_stars_args(p):
        p.add_argument("project")
        p.add_argument("--brightness", type=float, default=0.70)
        p.add_argument("--no-saturation", action="store_true")
        p.add_argument("--saturation", type=float, default=0.08)
        p.add_argument("--background-factor", type=float, default=0.0)
        p.add_argument("--hue-range", type=int, default=6)

    p = sub.add_parser("stars-recommend", help="천체 특징 + Stars 통계 기반 추천값")
    p.add_argument("project")
    p.set_defaults(func=cmd_stars_recommend)

    p = sub.add_parser("stars-preview", help="Stars Brightness/Saturation 미리보기")
    add_stars_args(p)
    p.set_defaults(func=cmd_stars_preview)

    p = sub.add_parser("stars-apply", help="승인 후 Stars Processing 실제 적용")
    add_stars_args(p)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_stars_apply)

    p = sub.add_parser("stars-skip", help="Stars Processing 건너뛰기")
    p.add_argument("project")
    p.set_defaults(func=cmd_stars_skip)


    p = sub.add_parser("recombine-recommend", help="Pixel Math Recombine 추천값")
    p.add_argument("project")
    p.set_defaults(func=cmd_recombine_recommend)

    p = sub.add_parser("recombine-preview", help="Pixel Math Recombine 미리보기")
    p.add_argument("project")
    p.add_argument("--star-weight", type=float, default=1.0)
    p.add_argument("--rescale", action="store_true")
    p.set_defaults(func=cmd_recombine_preview)


    p = sub.add_parser("final-preview", help="Final Export 전 최종 미리보기")
    p.add_argument("project")
    p.add_argument("--quality", type=int, default=95)
    p.set_defaults(func=cmd_final_preview)

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n취소되었습니다.")
        return 130
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
