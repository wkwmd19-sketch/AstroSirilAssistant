from __future__ import annotations
from pathlib import Path
import json

from .project import load_project, save_project
from .siril import run_script, SirilError
from .utils import normalize_siril_path, iso_now
from .fits_analysis import analyze_pixels
from .logging_utils import append_jsonl

CLIP_MODES = {"clip", "rescale", "rgbblend", "globalrescale"}
LUMINANCE_MODES = {"HUMAN", "EVEN", "INDEPENDENT"}

def make_ghs_task(additional: bool = False) -> dict:
    return {
        "task_id": "GHS_STRETCH",
        "title": "GHS Stretch" if not additional else "추가 GHS Stretch",
        "summary": (
            "Linear 이미지를 GHS로 Stretch해 희미한 구조를 보이게 만듭니다."
            if not additional else
            "현재 Non-linear 이미지에 의도적으로 GHS Pass를 한 번 더 적용합니다."
        ),
        "purpose": "희미한 천체 신호의 대비를 높이면서 별과 밝은 하이라이트를 보호합니다.",
        "current_status": (
            "LINEAR / READY_FOR_GHS"
            if not additional else
            "STRETCHED / ADDITIONAL_GHS_ALLOWED"
        ),
        "recommendations": {
            "method": "AUTO_GHS",
            "linked": True,
            "shadows_clip": -2.8,
            "stretch_amount": 1.0,
            "b": 13.0,
            "lp": 0.0,
            "hp": 0.7,
            "clip_mode": "rgbblend",
            "note": "AutoGHS가 SP를 이미지 median/sigma에서 자동 계산",
        },
        "cautions": [
            "첫 적용 후 이미지는 Non-linear 상태가 됩니다.",
            "한 번에 강하게 Stretch하기보다 미리보기 후 작은 Pass를 반복하는 편이 안전합니다.",
        ],
        "completion_criteria": [
            "희미한 구조 가시화",
            "하이라이트 보존",
            "별 팽창 억제",
        ],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def make_ghs_review_task(pass_count: int) -> dict:
    return {
        "task_id": "GHS_REVIEW",
        "title": "GHS Stretch 결과 확인",
        "summary": f"GHS Pass {pass_count}가 적용되었습니다. 추가 Stretch 또는 다음 단계로 이동할 수 있습니다.",
        "purpose": "필요 이상의 Stretch를 피하면서 충분한 밝기와 대비를 확보합니다.",
        "current_status": f"STRETCHED / PASS_{pass_count}",
        "recommendations": {
            "choice": "추가 GHS Pass 또는 Stretch 완료",
        },
        "cautions": [
            "추가 GHS는 의도적인 반복 처리이며 각 Pass가 별도 파일/로그로 기록됩니다.",
        ],
        "completion_criteria": [
            "현재 Stretch 결과 확인",
            "추가 Pass 필요 여부 결정",
        ],
        "actions": ["EDIT", "CONFIRM"],
    }

def make_starnet_task() -> dict:
    return {
        "task_id": "STAR_SEPARATION",
        "title": "StarNet / 별 분리",
        "summary": "Stretch가 완료되었습니다. 다음 단계는 별과 Starless 이미지를 분리하는 StarNet입니다.",
        "purpose": "은하/성운과 별을 분리해 각각 독립적으로 조정할 준비를 합니다.",
        "current_status": "STRETCHED / NONLINEAR",
        "recommendations": {
            "engine": "Siril 1.4.4 starnet",
            "status": "다음 구현 단계",
        },
        "cautions": [
            "현재 파일은 Non-linear입니다.",
            "StarNet Linear Data 옵션을 잘못 켜지 않도록 다음 단계에서 State와 연동합니다.",
        ],
        "completion_criteria": ["Starless / Stars 생성"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }

def migrate_ready_for_ghs(project_dir: Path):
    """Upgrade v0.7 projects from DEBLURRED/ready states into the real GHS task."""
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]
    task = p.get("next_task") or {}

    if p.get("current_state") == "DEBLURRED" and task.get("task_id") == "GHS_STRETCH":
        # Existing task was placeholder: replace with v0.8 real task.
        p["next_task"] = make_ghs_task(additional=False)
        save_project(pdir, project)
    elif p.get("current_state") in ("DENOISED", "COLOR_CALIBRATED") and task.get("task_id") == "GHS_STRETCH":
        p["next_task"] = make_ghs_task(additional=False)
        p["next_task"]["current_status"] = f"{p.get('current_state')} / LINEAR / DEBLUR_SKIPPED"
        save_project(pdir, project)
    return project

def _stretch_meta(p: dict):
    return p.setdefault("stretch", {
        "method": "GHS",
        "passes": [],
        "additional_pass_mode": False,
        "completed": False,
    })

def _current_file_for_ghs(project: dict) -> tuple[Path, bool]:
    p = project["project"]
    current = Path(p["current_file"])
    if not current.exists():
        raise FileNotFoundError(f"현재 FITS가 없습니다: {current}")

    stretch = _stretch_meta(p)
    linearity = p.get("image_state", {}).get("linearity")
    stretched = p.get("image_state", {}).get("stretched")

    if linearity == "LINEAR" and stretched is not True:
        return current, False

    if (
        linearity == "NONLINEAR"
        and stretched is True
        and stretch.get("additional_pass_mode") is True
    ):
        return current, True

    raise ValueError(
        "현재 이미지 상태에서는 GHS를 실행할 수 없습니다. "
        "이미 Stretch된 이미지에 추가 GHS를 적용하려면 '추가 GHS Pass'를 먼저 선택하세요."
    )

def _validate_clip_mode(value: str) -> str:
    v = str(value).lower()
    if v not in CLIP_MODES:
        raise ValueError("Clip Mode는 clip / rescale / rgbblend / globalrescale 중 하나여야 합니다.")
    return v

def _validate_auto(params: dict):
    shadows = float(params.get("shadows_clip", -2.8))
    d = float(params.get("stretch_amount", 1.0))
    b = float(params.get("b", 13.0))
    lp = float(params.get("lp", 0.0))
    hp = float(params.get("hp", 0.7))
    clip = _validate_clip_mode(params.get("clip_mode", "rgbblend"))

    if not (0 <= d <= 10):
        raise ValueError("Stretch Amount(D)는 0~10 범위여야 합니다.")
    if not (-5 <= b <= 15):
        raise ValueError("B는 -5~15 범위여야 합니다.")
    if not (0 <= lp <= 1 and 0 <= hp <= 1):
        raise ValueError("LP/HP는 0~1 범위여야 합니다.")
    if lp > hp:
        raise ValueError("LP는 HP보다 클 수 없습니다.")

    return shadows, d, b, lp, hp, clip

def _validate_manual(params: dict):
    d = float(params.get("d", 1.0))
    b = float(params.get("b", 0.0))
    lp = float(params.get("lp", 0.0))
    sp = float(params.get("sp", 0.0))
    hp = float(params.get("hp", 1.0))
    lum = str(params.get("luminance_mode", "HUMAN")).upper()
    clip = _validate_clip_mode(params.get("clip_mode", "rgbblend"))

    if not (0 <= d <= 10):
        raise ValueError("D는 0~10 범위여야 합니다.")
    if not (-5 <= b <= 15):
        raise ValueError("B는 -5~15 범위여야 합니다.")
    if not (0 <= lp <= 1 and 0 <= sp <= 1 and 0 <= hp <= 1):
        raise ValueError("LP/SP/HP는 0~1 범위여야 합니다.")
    if not (lp <= sp <= hp):
        raise ValueError("Manual GHT는 LP ≤ SP ≤ HP 순서여야 합니다.")
    if lum not in LUMINANCE_MODES:
        raise ValueError("Luminance Mode는 HUMAN / EVEN / INDEPENDENT 중 하나여야 합니다.")

    return d, b, lp, sp, hp, lum, clip

def build_ghs_command(method: str, **params) -> str:
    method = str(method).upper()

    if method == "AUTO_GHS":
        shadows, d, b, lp, hp, clip = _validate_auto(params)
        parts = ["autoghs"]
        if bool(params.get("linked", True)):
            parts.append("-linked")
        parts.extend([
            f"{shadows:g}",
            f"{d:g}",
            f"-b={b:g}",
            f"-lp={lp:g}",
            f"-hp={hp:g}",
            f"-clipmode={clip}",
        ])
        return " ".join(parts)

    if method == "MANUAL_GHT":
        d, b, lp, sp, hp, lum, clip = _validate_manual(params)
        parts = [
            "ght",
            f"-D={d:g}",
            f"-B={b:g}",
            f"-LP={lp:g}",
            f"-SP={sp:g}",
            f"-HP={hp:g}",
            f"-clipmode={clip}",
        ]
        parts.append({
            "HUMAN": "-human",
            "EVEN": "-even",
            "INDEPENDENT": "-independent",
        }[lum])
        return " ".join(parts)

    raise ValueError("GHS Method는 AUTO_GHS 또는 MANUAL_GHT여야 합니다.")

def _find_saved(stem: Path):
    for ext in (".fits", ".fit", ".fts"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def _next_pass_number(project: dict) -> int:
    stretch = _stretch_meta(project["project"])
    return len(stretch.get("passes", [])) + 1

def preview_ghs(project_dir: Path, config: dict, method: str, **params):
    pdir = Path(project_dir)
    project = load_project(pdir)
    current, additional = _current_file_for_ghs(project)
    target = project["project"]["target_name"]
    pass_no = _next_pass_number(project)

    temp_dir = pdir / "temp" / "ghs_preview"
    preview_dir = pdir / "output" / "preview"
    temp_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    result_stem = temp_dir / f"{target}_ghs_pass{pass_no}_preview"
    jpg_stem = preview_dir / f"{target}_ghs_pass{pass_no}_preview"

    ghs_cmd = build_ghs_command(method, **params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        ghs_cmd,
        f'save "{normalize_siril_path(result_stem)}"',
        # IMPORTANT: no autostretch here; GHS result itself is the real stretch.
        f'savejpg "{normalize_siril_path(jpg_stem)}" 95',
        "close",
    ]

    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "GHS 미리보기 생성 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    linear_or_stretched_preview = _find_saved(result_stem)
    jpg = jpg_stem.with_suffix(".jpg")
    if not linear_or_stretched_preview or not jpg.exists():
        raise SirilError(
            "Siril 실행 후 GHS 미리보기 파일을 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    meta = {
        "timestamp": iso_now(),
        "input_file": str(current),
        "display_preview": str(jpg),
        "preview_fits": str(linear_or_stretched_preview),
        "pass_number": pass_no,
        "additional_pass": bool(additional),
        "method": method,
        "ghs_command": ghs_cmd,
        "parameters": params,
        "note": "GHS preview JPEG에는 별도의 AutoStretch를 적용하지 않습니다.",
    }
    (pdir / "logs" / "ghs_preview.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    append_jsonl(pdir, {"event": "GHS_PREVIEW", "status": "SUCCESS", **meta})
    return jpg, linear_or_stretched_preview, meta

def apply_ghs(project_dir: Path, config: dict, method: str, confirmed: bool = False, **params):
    if not confirmed:
        raise PermissionError("실제 GHS 적용에는 사용자 승인이 필요합니다.")

    pdir = Path(project_dir)
    project = load_project(pdir)
    current, additional = _current_file_for_ghs(project)
    p = project["project"]
    target = p["target_name"]
    pass_no = _next_pass_number(project)

    out_dir = pdir / "working" / "07_stretch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / f"{target}_07_ghs{pass_no}"

    before = analyze_pixels(
        current,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    ghs_cmd = build_ghs_command(method, **params)
    commands = [
        "set32bits",
        "setext fits",
        f'load "{normalize_siril_path(current)}"',
        ghs_cmd,
        f'save "{normalize_siril_path(out_stem)}"',
        "close",
    ]
    proc = run_script(config, commands, cwd=current.parent)
    if proc.returncode != 0:
        raise SirilError(
            "GHS 실행 실패\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    output = _find_saved(out_stem)
    if not output:
        raise SirilError(
            "Siril 실행 후 GHS 결과 FITS를 찾지 못했습니다.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    after = analyze_pixels(
        output,
        max_samples=int(config.get("analysis", {}).get("max_samples_per_channel", 1500000)),
        bins=int(config.get("analysis", {}).get("histogram_bins", 2048)),
        clip_fraction=float(config.get("analysis", {}).get("clip_fraction", 0.0001)),
    )

    stretch = _stretch_meta(p)
    pass_record = {
        "pass": pass_no,
        "method": str(method).upper(),
        "additional_pass": bool(additional),
        "input_file": str(current),
        "output_file": str(output),
        "command": ghs_cmd,
        "parameters": params,
        "timestamp": iso_now(),
    }
    stretch["passes"].append(pass_record)
    stretch["additional_pass_mode"] = False
    stretch["completed"] = False

    p["current_file"] = str(output)
    p["current_state"] = "STRETCHED"
    p["image_state"]["linearity"] = "NONLINEAR"
    p["image_state"]["linearity_confidence"] = 1.0
    p["image_state"]["stretched"] = True
    p["next_task"] = make_ghs_review_task(pass_no)
    save_project(pdir, project)

    payload = {
        "event": "GHS_APPLY",
        "status": "SUCCESS",
        "input_file": str(current),
        "output_file": str(output),
        "pass_number": pass_no,
        "additional_pass": bool(additional),
        "method": method,
        "ghs_command": ghs_cmd,
        "parameters": params,
        "analysis_before": before,
        "analysis_after": after,
        "siril_stdout": proc.stdout,
        "siril_stderr": proc.stderr,
    }
    append_jsonl(pdir, payload)
    (pdir / "logs" / f"ghs_pass{pass_no}_apply.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return project, output, payload

def begin_additional_ghs(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    if p.get("current_state") != "STRETCHED":
        raise ValueError("추가 GHS는 STRETCHED 상태에서만 시작할 수 있습니다.")
    if p.get("image_state", {}).get("linearity") != "NONLINEAR":
        raise ValueError("추가 GHS는 Non-linear 이미지에서만 시작할 수 있습니다.")

    stretch = _stretch_meta(p)
    stretch["additional_pass_mode"] = True
    p["next_task"] = make_ghs_task(additional=True)
    save_project(pdir, project)

    append_jsonl(pdir, {
        "event": "GHS_ADDITIONAL_PASS_BEGIN",
        "status": "SUCCESS",
        "current_file": p.get("current_file"),
        "next_pass": len(stretch.get("passes", [])) + 1,
    })
    return project

def finish_ghs(project_dir: Path):
    pdir = Path(project_dir)
    project = load_project(pdir)
    p = project["project"]

    if p.get("current_state") != "STRETCHED":
        raise ValueError("Stretch 완료는 STRETCHED 상태에서만 가능합니다.")

    stretch = _stretch_meta(p)
    if not stretch.get("passes"):
        raise ValueError("적용된 GHS Pass가 없습니다.")
    stretch["additional_pass_mode"] = False
    stretch["completed"] = True
    p["next_task"] = make_starnet_task()
    save_project(pdir, project)

    append_jsonl(pdir, {
        "event": "GHS_FINISH",
        "status": "SUCCESS",
        "passes": len(stretch["passes"]),
        "current_file": p.get("current_file"),
    })
    return project
