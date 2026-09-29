from __future__ import annotations
import argparse
from pathlib import Path
import sys
import json

from astroauto.config import load_app_config
from astroauto.siril import get_siril_info, SirilError
from astroauto.project import create_project, load_project
from astroauto.analyzer import analyze_project, confirm_linearity
from astroauto.workflow import format_task

CATEGORIES = [
    "GALAXY", "EMISSION_NEBULA", "REFLECTION_NEBULA", "DARK_NEBULA",
    "PLANETARY_NEBULA", "SUPERNOVA_REMNANT", "OPEN_CLUSTER",
    "GLOBULAR_CLUSTER", "MILKYWAY", "GENERAL_STARFIELD", "UNKNOWN"
]

def cmd_doctor(args):
    cfg = load_app_config()
    print("AstroSirilAssistant v0.3")
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
        root=root,
        target=args.target,
        capture_date=args.date,
        category=args.category,
        input_file=Path(args.input),
        copy_input=not args.no_copy,
    )
    print(f"프로젝트 생성: {pdir}")
    if args.analyze:
        project, report, task = analyze_project(pdir, cfg)
        print()
        print(format_task(task))
    return 0

def cmd_analyze(args):
    cfg = load_app_config()
    project, report, task = analyze_project(Path(args.project), cfg)
    print(format_task(task))
    print(f"\n분석 로그: {Path(args.project) / 'logs' / 'analysis_report.json'}")
    return 0

def cmd_status(args):
    project = load_project(Path(args.project))
    p = project["project"]
    print(f"Project: {p['id']}")
    print(f"State: {p['current_state']}")
    print(f"Linearity: {p['image_state']['linearity']}")
    print(f"Current file: {p['current_file']}")
    if p.get("next_task"):
        print()
        print(format_task(p["next_task"]))
    return 0

def cmd_confirm(args):
    project = confirm_linearity(Path(args.project), args.linearity)
    print(f"Linearity를 {args.linearity.upper()}로 확정했습니다.")
    print()
    print(format_task(project["project"]["next_task"]))
    return 0

def build_parser():
    parser = argparse.ArgumentParser(description="AstroSirilAssistant v0.3")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="Siril 연결과 환경 확인")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("new", help="새 반자동 프로젝트 생성")
    p.add_argument("--input", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--category", choices=CATEGORIES, default="UNKNOWN")
    p.add_argument("--root")
    p.add_argument("--no-copy", action="store_true")
    p.add_argument("--analyze", action="store_true")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("analyze", help="프로젝트 FITS 분석")
    p.add_argument("project")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("status", help="프로젝트 상태 출력")
    p.add_argument("project")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("confirm-linearity", help="Linear/Non-linear 사용자 확정")
    p.add_argument("project")
    p.add_argument("linearity", choices=["LINEAR", "NONLINEAR", "linear", "nonlinear"])
    p.set_defaults(func=cmd_confirm)

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
