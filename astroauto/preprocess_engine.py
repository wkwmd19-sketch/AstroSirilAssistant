from __future__ import annotations
from pathlib import Path
import json
import shutil

from .project import load_project, save_project
from .siril import get_siril_info, run_script_file
from .utils import iso_now
from .logging_utils import append_jsonl

def _q(text: str) -> str:
    return '"' + str(text).replace('"', '\\"') + '"'

def _arg(name: str, value: str) -> str:
    # Siril docs require quoting the entire argument when it contains spaces.
    return _q(f"-{name}={value}")

def _folder(project: dict, key: str) -> Path | None:
    rec = project["project"].get("sources", {}).get("folders", {}).get(key, {})
    raw = rec.get("path")
    return Path(raw) if raw else None

def _count(project: dict, key: str) -> int:
    rec = project["project"].get("sources", {}).get("folders", {}).get(key, {})
    return int(rec.get("count") or 0)

def _stem(path: Path) -> str:
    return path.resolve().as_posix()

def _master_stem(project_dir: Path, name: str) -> Path:
    return project_dir / "calibration" / "masters" / name

def _camera_is_osc(project: dict) -> bool:
    mode = str(project["project"].get("capture", {}).get("camera_type", "AUTO")).upper()
    if mode == "OSC":
        return True
    if mode == "MONO":
        return False
    # AUTO is conservative: no CFA flags unless user explicitly selects OSC.
    return False

def build_preprocess_plan(project_dir: Path):
    project_dir = Path(project_dir)
    project = load_project(project_dir)
    p = project["project"]

    if p["target"]["category"] in ("STAR_TRAIL", "PLANETARY_LUNAR", "COMET"):
        raise ValueError("이 카테고리는 v0.4 딥스카이 Calibration/Registration/Stack 실행 경로를 사용하지 않습니다.")

    if p.get("input_stage", {}).get("source_stage") != "LIGHT_SEQUENCE":
        raise ValueError("v0.4 실제 전처리 엔진은 LIGHT_SEQUENCE 프로젝트용입니다.")

    input_status = p.get("calibration", {}).get("input_status", "UNKNOWN")
    if input_status == "UNKNOWN":
        raise ValueError("RAW_UNCALIBRATED 또는 PRECALIBRATED 상태를 먼저 확정하세요.")

    lights = _folder(project, "lights")
    if not lights or not lights.exists():
        raise FileNotFoundError("Lights source folder를 찾지 못했습니다.")

    temp_root = project_dir / "temp" / "siril_preprocess"
    seq_root = temp_root / "sequences"
    for name in ("bias", "dark", "dark_flat", "flat", "light"):
        (seq_root / name).mkdir(parents=True, exist_ok=True)

    masters = project_dir / "calibration" / "masters"
    masters.mkdir(parents=True, exist_ok=True)
    stack_dir = project_dir / "working" / "02_stacked"
    stack_dir.mkdir(parents=True, exist_ok=True)

    target = p["target_name"]
    master_bias = _master_stem(project_dir, "master_bias")
    master_dark = _master_stem(project_dir, "master_dark")
    master_dark_flat = _master_stem(project_dir, "master_dark_flat")
    master_flat = _master_stem(project_dir, "master_flat")
    output_stem = stack_dir / f"{target}_02_stacked"

    counts = {k: _count(project, k) for k in ("lights", "dark", "flat", "bias", "dark_flat")}
    osc = _camera_is_osc(project)

    commands = ["requires 1.4.0", "set32bits", "setext fit"]
    phases = []

    def convert_phase(label, source_dir: Path, basename: str, out_dir: Path):
        phases.append(label)
        commands.extend([
            f"cd {_q(source_dir.resolve().as_posix())}",
            f"convert {basename} -fitseq {_arg('out', out_dir.resolve().as_posix())}",
        ])

    # Bias
    if input_status == "RAW_UNCALIBRATED" and counts["bias"] > 0:
        convert_phase("MASTER_BIAS", _folder(project, "bias"), "bias", seq_root / "bias")
        commands.extend([
            f"cd {_q((seq_root / 'bias').resolve().as_posix())}",
            f"stack bias rej winsorized 3 3 -nonorm {_arg('out', _stem(master_bias))} -32b",
        ])

    # Dark-flat
    if input_status == "RAW_UNCALIBRATED" and counts["dark_flat"] > 0:
        convert_phase("MASTER_DARK_FLAT", _folder(project, "dark_flat"), "darkflat", seq_root / "dark_flat")
        commands.extend([
            f"cd {_q((seq_root / 'dark_flat').resolve().as_posix())}",
            f"stack darkflat rej winsorized 3 3 -nonorm {_arg('out', _stem(master_dark_flat))} -32b",
        ])

    # Dark: unprocessed master dark; do not subtract bias by default.
    if input_status == "RAW_UNCALIBRATED" and counts["dark"] > 0:
        convert_phase("MASTER_DARK", _folder(project, "dark"), "dark", seq_root / "dark")
        commands.extend([
            f"cd {_q((seq_root / 'dark').resolve().as_posix())}",
            f"stack dark rej winsorized 3 3 -nonorm {_arg('out', _stem(master_dark))} -32b",
        ])

    # Flat
    if input_status == "RAW_UNCALIBRATED" and counts["flat"] > 0:
        convert_phase("MASTER_FLAT", _folder(project, "flat"), "flat", seq_root / "flat")
        commands.append(f"cd {_q((seq_root / 'flat').resolve().as_posix())}")
        if counts["dark_flat"] > 0:
            commands.append(f"calibrate flat {_arg('dark', _stem(master_dark_flat))} -fitseq")
            flat_seq = "pp_flat"
        elif counts["bias"] > 0:
            commands.append(f"calibrate flat {_arg('bias', _stem(master_bias))} -fitseq")
            flat_seq = "pp_flat"
        else:
            # Allowed, but recorded as a warning in the plan.
            flat_seq = "flat"
        commands.append(
            f"stack {flat_seq} rej winsorized 3 3 -norm=mul {_arg('out', _stem(master_flat))} -32b"
        )

    # Lights
    convert_phase("LIGHT_SEQUENCE", lights, "light", seq_root / "light")
    commands.append(f"cd {_q((seq_root / 'light').resolve().as_posix())}")

    calibrated_sequence = "light"
    calibration_args = []
    if input_status == "RAW_UNCALIBRATED":
        if counts["dark"] > 0:
            calibration_args.append(_arg("dark", _stem(master_dark)))
        elif counts["bias"] > 0:
            # Use bias only when there is no master dark.
            calibration_args.append(_arg("bias", _stem(master_bias)))

        if counts["flat"] > 0:
            calibration_args.append(_arg("flat", _stem(master_flat)))

        if calibration_args:
            cfa_args = []
            if osc:
                cfa_args = ["-cfa", "-equalize_cfa", "-debayer"]
            commands.append(
                "calibrate light "
                + " ".join(calibration_args + cfa_args + ["-fitseq"])
            )
            calibrated_sequence = "pp_light"

    # Registration / registered sequence creation
    phases.extend(["REGISTER_2PASS", "APPLY_REGISTRATION", "STACK"])
    commands.extend([
        f"register {calibrated_sequence} -2pass",
        f"seqapplyreg {calibrated_sequence} -prefix=r_ -framing=min",
        f"stack r_{calibrated_sequence} rej winsorized 3 3 -norm=addscale "
        f"-weight=wfwhm {_arg('out', _stem(output_stem))} -32b",
        "close",
    ])

    warnings = []
    if input_status == "RAW_UNCALIBRATED":
        if counts["dark"] == 0:
            warnings.append("Dark가 없습니다. Dark 보정 없이 진행합니다.")
        if counts["flat"] == 0:
            warnings.append("Flat이 없습니다. Flat 보정 없이 진행합니다.")
        if counts["flat"] > 0 and counts["bias"] == 0 and counts["dark_flat"] == 0:
            warnings.append("Flat은 있지만 Bias/Dark-flat이 없습니다. v0.4는 Flat을 그대로 Master stack합니다.")
    if p["capture"].get("camera_type", "AUTO").upper() == "AUTO":
        warnings.append("Camera mode=AUTO이므로 CFA/debayer 옵션을 자동 강제하지 않습니다. OSC라면 실행 전 OSC로 지정하는 것을 권장합니다.")

    plan = {
        "schema_version": "0.4.0",
        "created_at": iso_now(),
        "project_id": p["id"],
        "input_status": input_status,
        "camera_mode": p["capture"].get("camera_type", "AUTO"),
        "counts": counts,
        "phases": phases,
        "warnings": warnings,
        "masters": {
            "bias": str(master_bias) if counts["bias"] else None,
            "dark": str(master_dark) if counts["dark"] else None,
            "dark_flat": str(master_dark_flat) if counts["dark_flat"] else None,
            "flat": str(master_flat) if counts["flat"] else None,
        },
        "output_stem": str(output_stem),
        "commands": commands,
    }

    logs = project_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    plan_path = logs / "preprocess_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    script_path = logs / "preprocess_v0.4.ssf"
    script_path.write_text("\n".join(commands) + "\n", encoding="utf-8")

    append_jsonl(project_dir, {
        "event": "PREPROCESS_PLAN",
        "status": "SUCCESS",
        "plan": str(plan_path),
        "script": str(script_path),
        "warnings": warnings,
    })

    return plan, plan_path, script_path

def _find_output_from_stem(stem: Path) -> Path | None:
    candidates = [
        stem.with_suffix(".fit"),
        stem.with_suffix(".fits"),
        stem.with_suffix(".fts"),
        stem,
    ]
    for p in candidates:
        if p.exists():
            return p
    # Siril sometimes appends an extension based on preferences; search by stem name.
    found = sorted(stem.parent.glob(stem.name + ".*"))
    return found[0] if found else None

def execute_preprocess(project_dir: Path, config: dict, confirmed: bool = False):
    if not confirmed:
        raise PermissionError("반자동 안전 규칙: 실제 Siril 실행에는 confirmed=True가 필요합니다.")

    project_dir = Path(project_dir)
    project = load_project(project_dir)
    plan, plan_path, script_path = build_preprocess_plan(project_dir)

    siril_info = get_siril_info(config)
    proc = run_script_file(config, script_path, cwd=project_dir)

    stdout_path = project_dir / "logs" / "preprocess_stdout.log"
    stderr_path = project_dir / "logs" / "preprocess_stderr.log"
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    output = _find_output_from_stem(Path(plan["output_stem"]))

    success = proc.returncode == 0 and output is not None
    append_jsonl(project_dir, {
        "event": "PREPROCESS_RUN",
        "status": "SUCCESS" if success else "FAILED",
        "returncode": proc.returncode,
        "output": str(output) if output else None,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    })

    p = project["project"]
    p["runtime"]["siril_version"] = siril_info.version
    p["runtime"]["siril_executable"] = str(siril_info.executable)

    if success:
        p["current_state"] = "STACKED_LINEAR"
        p["current_file"] = str(output)
        p["image_state"]["linearity"] = "LINEAR"
        p["image_state"]["linearity_confidence"] = 1.0
        p["image_state"]["stretched"] = False
        p["next_task"] = {
            "task_id": "GRADIENT_CORRECTION",
            "title": "Background / Gradient Correction",
            "summary": "Calibration / Registration / Stack이 완료되었습니다. 다음은 배경 그라디언트 보정입니다.",
            "purpose": "스택된 Linear 결과의 배경 불균형을 정리합니다.",
            "current_status": "STACKED_LINEAR",
            "recommendations": {"next": "Siril subsky / v0.5 구현 예정"},
            "cautions": ["희미한 천체 구조가 배경 모델로 제거되지 않도록 확인합니다."],
            "completion_criteria": ["배경 균일화", "천체 구조 유지"],
            "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
        }
        save_project(project_dir, project)
    else:
        p["current_state"] = "REVIEW_REQUIRED"
        save_project(project_dir, project)
        raise RuntimeError(
            "Siril 전처리/스택이 완료되지 않았습니다. "
            f"returncode={proc.returncode}, output={output}. "
            "logs/preprocess_stdout.log 및 preprocess_stderr.log를 확인하세요."
        )

    return project, output, plan
