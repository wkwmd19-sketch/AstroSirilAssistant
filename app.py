from __future__ import annotations
import argparse
from pathlib import Path
import sys

from astroauto.config import load_app_config
from astroauto.siril import get_siril_info
from astroauto.project import create_project, load_project, save_project
from astroauto.analyzer import analyze_project, confirm_linearity
from astroauto.calibration import scan_project_calibration
from astroauto.workflow import format_task, next_task_after_analysis
from astroauto.logging_utils import append_jsonl

CATEGORIES = [
    "GALAXY", "EMISSION_NEBULA", "REFLECTION_NEBULA", "DARK_NEBULA",
    "PLANETARY_NEBULA", "SUPERNOVA_REMNANT", "OPEN_CLUSTER",
    "GLOBULAR_CLUSTER", "MILKYWAY", "GENERAL_STARFIELD", "UNKNOWN"
]

SOURCE_STAGES = [
    "LIGHT_SEQUENCE", "SINGLE_LIGHT", "REGISTERED_SEQUENCE",
    "STACKED_LINEAR", "STACKED_NONLINEAR", "UNKNOWN"
]

CAL_STATUS = ["RAW_UNCALIBRATED", "PRECALIBRATED", "UNKNOWN"]

def cmd_doctor(args):
    cfg = load_app_config()
    print("AstroSirilAssistant v0.3.1")
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
    print(f"Source stage: {p.get('input_stage', {}).get('source_stage', 'UNKNOWN')}")
    print(f"Calibration input status: {p.get('calibration', {}).get('input_status', 'UNKNOWN')}")
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
    pdir = Path(args.project)
    project = load_project(pdir)
    p = project["project"]
    p.setdefault("input_stage", {})
    p["input_stage"]["source_stage"] = args.stage.upper()
    p["input_stage"]["user_confirmed"] = True
    p["current_state"] = "INPUT_STAGE_CONFIRMED"

    # STACKED_* stage provides strong user confirmation of linearity.
    if args.stage.upper() == "STACKED_LINEAR":
        p["image_state"]["linearity"] = "LINEAR"
        p["image_state"]["linearity_confidence"] = 1.0
        p["image_state"]["stretched"] = False
    elif args.stage.upper() == "STACKED_NONLINEAR":
        p["image_state"]["linearity"] = "NONLINEAR"
        p["image_state"]["linearity_confidence"] = 1.0
        p["image_state"]["stretched"] = True

    p["next_task"] = next_task_after_analysis(project)
    save_project(pdir, project)
    append_jsonl(pdir, {"event": "USER_CONFIRM_INPUT_STAGE", "value": args.stage.upper(), "status": "SUCCESS"})
    print(f"입력 단계를 {args.stage.upper()}로 확정했습니다.")
    print("\n" + format_task(p["next_task"]))
    return 0

def cmd_confirm_calibration(args):
    pdir = Path(args.project)
    project = load_project(pdir)
    p = project["project"]
    p.setdefault("calibration", {})
    p["calibration"]["input_status"] = args.status.upper()
    p["calibration"]["user_confirmed"] = True

    if args.status.upper() == "PRECALIBRATED":
        p["current_state"] = "PRECALIBRATED_CONFIRMED"

    p["next_task"] = next_task_after_analysis(project)
    save_project(pdir, project)
    append_jsonl(pdir, {"event": "USER_CONFIRM_CALIBRATION_STATUS", "value": args.status.upper(), "status": "SUCCESS"})
    print(f"캘리브레이션 상태를 {args.status.upper()}로 확정했습니다.")
    print("\n" + format_task(p["next_task"]))
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

def build_parser():
    parser = argparse.ArgumentParser(description="AstroSirilAssistant v0.3.1")
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

    p = sub.add_parser("calibration-check")
    p.add_argument("project")
    p.set_defaults(func=cmd_calibration_check)

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
