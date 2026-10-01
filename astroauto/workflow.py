from __future__ import annotations

PROFILE_LABELS = {
    "GALAXY": "은하",
    "EMISSION_NEBULA": "방출성운",
    "REFLECTION_NEBULA": "반사성운",
    "DARK_NEBULA": "암흑성운",
    "PLANETARY_NEBULA": "행성상성운",
    "SUPERNOVA_REMNANT": "초신성잔해",
    "OPEN_CLUSTER": "산개성단",
    "GLOBULAR_CLUSTER": "구상성단",
    "MILKYWAY": "은하수",
    "GENERAL_STARFIELD": "일반 별필드",
    "STAR_TRAIL": "별 일주사진",
    "COMET": "혜성/소행성",
    "PLANETARY_LUNAR": "달/행성",
    "MOSAIC": "모자이크",
    "UNKNOWN": "미분류",
}

def next_task_after_analysis(project: dict):
    p = project["project"]
    linearity = p["image_state"].get("linearity", "UNKNOWN")
    category = p["target"].get("category", "UNKNOWN")
    label = PROFILE_LABELS.get(category, category)
    source_stage = p.get("input_stage", {}).get("source_stage", "UNKNOWN")
    input_status = p.get("calibration", {}).get("input_status", "UNKNOWN")
    trail_mode = p.get("star_trail", {}).get("mode", "UNKNOWN")

    if category == "STAR_TRAIL":
        return _star_trail_task(source_stage, input_status, trail_mode, p)

    if category == "COMET":
        return {
            "task_id": "COMET_WORKFLOW_REVIEW",
            "title": "혜성 워크플로 검토",
            "summary": "혜성은 별 기준 정렬과 혜성 기준 정렬을 분리해야 할 수 있습니다.",
            "purpose": "혜성 핵/꼬리 보존과 별 배경 처리를 구분하기 위함입니다.",
            "current_status": "COMET / RESERVED_PROFILE",
            "recommendations": {"next_design": "comet-centered registration + star background workflow"},
            "cautions": ["일반 딥스카이 스택만으로는 혜성 형태가 흐려질 수 있습니다."],
            "completion_criteria": ["혜성 전용 구현 단계 진입 전 설계 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if category == "PLANETARY_LUNAR":
        return {
            "task_id": "PLANETARY_LUNAR_WORKFLOW_REVIEW",
            "title": "달 / 행성 워크플로 검토",
            "summary": "달/목성/토성은 딥스카이 스택이 아니라 고속 연사/영상 기반 처리가 필요할 수 있습니다.",
            "purpose": "행성/달용 별도 파이프라인과 외부 도구 연계를 준비하기 위함입니다.",
            "current_status": "PLANETARY_LUNAR / RESERVED_PROFILE",
            "recommendations": {"next_design": "SER/AVI input + quality selection + planetary stack"},
            "cautions": ["Siril 중심 딥스카이 파이프라인에 그대로 넣지 않습니다."],
            "completion_criteria": ["행성/달 전용 구현 단계 진입 전 설계 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if category == "MOSAIC":
        return {
            "task_id": "MOSAIC_WORKFLOW_REVIEW",
            "title": "모자이크 워크플로 검토",
            "summary": "패널별 처리 후 최종 패널 결합이 필요한 모자이크 촬영입니다.",
            "purpose": "패널 그룹핑과 모자이크 결합 단계를 분리하기 위함입니다.",
            "current_status": "MOSAIC / RESERVED_PROFILE",
            "recommendations": {"next_design": "panel grouping + assemble"},
            "cautions": ["단일 FOV 딥스카이와 다른 후반부 파이프라인이 필요합니다."],
            "completion_criteria": ["모자이크 구현 단계 진입 전 설계 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if source_stage == "UNKNOWN":
        return {
            "task_id": "CONFIRM_INPUT_STAGE",
            "title": "입력 데이터 단계 확인",
            "summary": "현재 파일이 개별 Light인지, 등록/스택 완료 데이터인지 먼저 확인합니다.",
            "purpose": "캘리브레이션과 스택을 이미 처리한 데이터에 다시 적용하지 않기 위함입니다.",
            "current_status": f"INPUT_ANALYZED / {label}",
            "recommendations": {"options": "LIGHT_SEQUENCE / SINGLE_LIGHT / REGISTERED_SEQUENCE / STACKED_LINEAR / STACKED_NONLINEAR"},
            "cautions": [
                "DWARF 등 스마트 망원경의 결과 파일은 기기 내부에서 이미 캘리브레이션/스택되었을 수 있습니다.",
                "확실하지 않으면 UNKNOWN을 유지하고 사용자 확인을 받습니다."
            ],
            "completion_criteria": ["입력 데이터 단계 확정"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if source_stage in ("LIGHT_SEQUENCE", "SINGLE_LIGHT", "REGISTERED_SEQUENCE") and input_status == "UNKNOWN":
        return {
            "task_id": "CONFIRM_CALIBRATION_STATUS",
            "title": "캘리브레이션 상태 확인",
            "summary": "입력 Light가 이미 Dark/Flat/Bias/Dark-flat 보정을 받은 데이터인지 확인합니다.",
            "purpose": "캘리브레이션 중복 적용을 방지합니다.",
            "current_status": f"{source_stage} / {label}",
            "recommendations": {"options": "RAW_UNCALIBRATED / PRECALIBRATED"},
            "cautions": ["PRECALIBRATED로 확인되면 캘리브레이션 프레임을 다시 적용하지 않습니다."],
            "completion_criteria": ["입력 캘리브레이션 상태 확정"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if source_stage in ("LIGHT_SEQUENCE", "SINGLE_LIGHT", "REGISTERED_SEQUENCE") and input_status == "RAW_UNCALIBRATED":
        calibration = p.get("calibration", {})
        if calibration.get("checked"):
            if calibration.get("resolution") == "SKIPPED" and source_stage == "SINGLE_LIGHT":
                if linearity == "LINEAR":
                    return _gradient_task(label, stage="SINGLE_LIGHT")
                return _confirm_light_linearity_task(label)
            return _review_calibration_task(p, label)
        return {
            "task_id": "CHECK_CALIBRATION_FRAMES",
            "title": "Dark / Flat / Bias / Dark-flat 검사",
            "summary": "보유한 캘리브레이션 프레임을 감지하고 Light와 조건이 맞는지 검사합니다.",
            "purpose": "스택 전에 센서/광학계의 체계적인 오차를 가능한 범위에서 제거합니다.",
            "current_status": f"{source_stage} / RAW_UNCALIBRATED",
            "recommendations": {
                "scan": "calibration/dark, bias, flat, dark_flat",
                "shared_library": "공유 Library는 아직 자동 검색하지 않습니다. 프로젝트 프레임 폴더에서 검사합니다."
            },
            "cautions": [
                "Bias와 Dark-flat을 무조건 동시에 요구하거나 중복 적용하지 않습니다.",
                "Dark는 Light의 노출/Gain/온도/해상도/비닝/ROI 조건을 비교합니다.",
                "Flat은 광학계/필터/센서 형상 일치를 우선 확인합니다."
            ],
            "completion_criteria": ["프레임 존재 여부와 호환성 보고서 생성"],
            "actions": ["RUN", "EDIT", "SKIP"],
        }

    if source_stage in ("STACKED_LINEAR", "STACKED_NONLINEAR"):
        if source_stage == "STACKED_NONLINEAR" or linearity == "NONLINEAR":
            return {
                "task_id": "REVIEW_INPUT_STATE",
                "title": "입력 상태 검토",
                "summary": "현재 데이터는 이미 Stretch된 상태이므로 초기 Linear 파이프라인을 적용하지 않습니다.",
                "purpose": "중복 Stretch와 과보정을 방지합니다.",
                "current_status": "STACKED_NONLINEAR",
                "recommendations": {"action": "사용자 확인 후 중간 단계부터 시작"},
                "cautions": ["GHS 초기 Stretch 자동 적용 금지"],
                "completion_criteria": ["현재 처리 단계를 확인"],
                "actions": ["CONFIRM", "EDIT"],
            }

        if linearity == "UNKNOWN":
            return {
                "task_id": "CONFIRM_LINEARITY",
                "title": "Linear 상태 확인",
                "summary": "스택 데이터의 Linear/Non-linear 상태를 확정합니다.",
                "purpose": "Gradient/SPCC/GHS 순서를 안전하게 선택합니다.",
                "current_status": f"STACKED / {label}",
                "recommendations": {"question": "실제 Stretch를 아직 적용하지 않은 Linear 스택인가요?"},
                "cautions": ["AutoStretch 화면 표시는 실제 데이터 Stretch가 아닙니다."],
                "completion_criteria": ["LINEAR 또는 NONLINEAR 확정"],
                "actions": ["CONFIRM", "EDIT"],
            }

        return _gradient_task(label)

    if linearity == "NONLINEAR":
        return {
            "task_id": "REVIEW_INPUT_STATE",
            "title": "입력 상태 검토",
            "summary": "Stretch 기록이 확인되어 자동 초기 보정을 멈춥니다.",
            "purpose": "중복 보정을 방지합니다.",
            "current_status": "NONLINEAR",
            "recommendations": {},
            "cautions": ["사용자 확인 필요"],
            "completion_criteria": ["처리 단계 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    return _gradient_task(label, stage="SINGLE_LIGHT" if source_stage == "SINGLE_LIGHT" else "STACKED_LINEAR")

def _star_trail_task(source_stage: str, input_status: str, trail_mode: str, p: dict | None = None):
    calibration = (p or {}).get("calibration", {})
    if trail_mode == "UNKNOWN":
        return {
            "task_id": "CONFIRM_STAR_TRAIL_MODE",
            "title": "별 일주사진 유형 확인",
            "summary": "별 일주사진이 순수 하늘 중심인지, 지상 풍경이 포함된 장면인지 먼저 확인합니다.",
            "purpose": "일주 합성 안내와 프레임 검토 기준을 맞추기 위함입니다.",
            "current_status": "STAR_TRAIL / INPUT_ANALYZED",
            "recommendations": {"options": "STAR_TRAIL_SKY / STAR_TRAIL_LANDSCAPE"},
            "cautions": [
                "별 일주사진은 일반 별 정렬을 사용하지 않습니다.",
                "지상 풍경이 포함되어도 기본적으로 trail composition 파이프라인으로 처리합니다."
            ],
            "completion_criteria": ["STAR_TRAIL_SKY 또는 STAR_TRAIL_LANDSCAPE 확정"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if source_stage == "UNKNOWN":
        return {
            "task_id": "CONFIRM_INPUT_STAGE",
            "title": "일주 입력 단계 확인",
            "summary": "현재 입력이 개별 프레임 시퀀스인지 확인합니다.",
            "purpose": "일주 합성은 보통 다수의 연속 프레임을 기반으로 하기 때문입니다.",
            "current_status": f"{trail_mode}",
            "recommendations": {"options": "LIGHT_SEQUENCE / PRECALIBRATED_SEQUENCE / SINGLE_LIGHT(미리보기용)"},
            "cautions": ["실제 일주 합성에는 보통 연속 촬영 프레임 시퀀스가 필요합니다."],
            "completion_criteria": ["입력 유형 확정"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if input_status == "UNKNOWN":
        return {
            "task_id": "CONFIRM_CALIBRATION_STATUS",
            "title": "캘리브레이션 상태 확인",
            "summary": "일주 원본 프레임이 이미 보정된 데이터인지 확인합니다.",
            "purpose": "Dark/Flat 중복 적용을 방지합니다.",
            "current_status": f"{trail_mode} / {source_stage}",
            "recommendations": {"options": "RAW_UNCALIBRATED / PRECALIBRATED"},
            "cautions": ["Dark는 일주사진의 핫픽셀/고정패턴 억제에 유용할 수 있습니다."],
            "completion_criteria": ["입력 캘리브레이션 상태 확정"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if input_status == "RAW_UNCALIBRATED":
        if calibration.get("checked"):
            if calibration.get("resolution") != "SKIPPED":
                return _review_calibration_task(p or {}, "별 일주사진")
        else:
            return {
                "task_id": "CHECK_CALIBRATION_FRAMES",
                "title": "Dark / Flat / Bias / Dark-flat 검사",
                "summary": "일주 프레임용 캘리브레이션 프레임을 점검합니다.",
                "purpose": "핫픽셀, 고정패턴, 비네팅 등을 줄여 trail 품질을 높입니다.",
                "current_status": f"{trail_mode} / RAW_UNCALIBRATED",
                "recommendations": {"scan": "calibration/dark, bias, flat, dark_flat"},
                "cautions": ["Flat은 있으면 유용하지만 필수는 아닙니다.", "Bias와 Dark-flat은 센서/워크플로에 따라 선택합니다."],
                "completion_criteria": ["캘리브레이션 프레임 호환성 보고서 생성"],
                "actions": ["RUN", "EDIT", "SKIP"],
            }

    return {
        "task_id": "FRAME_QUALITY_CHECK",
        "title": "일주 프레임 품질 점검",
        "summary": "프레임 수, 시간 간격, 흔들림, 구름, 비행기/위성 흔적 여부를 검토합니다.",
        "purpose": "trail 끊김과 불필요한 인공 흔적을 최소화하면서 합성 대상을 정리합니다.",
        "current_status": f"{trail_mode} / READY_FOR_TRAIL",
        "recommendations": {
            "checks": "frame_count / time_gap / cloud / shake / airplane_satellite_candidates",
            "next": "STAR_TRAIL_COMPOSE"
        },
        "cautions": [
            "일주사진은 일반 딥스카이 registration/stack을 사용하지 않습니다.",
            "문제 프레임은 자동 삭제가 아니라 후보 제안 후 사용자 확인 방식이 적합합니다."
        ],
        "completion_criteria": ["제외 후보 프레임 확인", "합성 전 검토 완료"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
    }


def _review_calibration_task(p: dict, label: str) -> dict:
    cal = p.get("calibration", {})
    frames = cal.get("frames") or {}
    counts = ", ".join(f"{name} {frames.get(name, {}).get('count', 0)}장" for name in ("dark", "bias", "flat", "dark_flat"))
    cautions = ["검사는 실제 캘리브레이션을 적용하지 않습니다.",
                "프레임을 새로 등록했다면 다시 검사해야 합니다."]
    cautions.extend((cal.get("recommendation") or {}).get("warnings") or [])
    return {
        "task_id": "REVIEW_CALIBRATION_FRAMES",
        "title": "캘리브레이션 검사 결과 확인",
        "summary": "프레임 검사 결과를 검토하고, 보정 없이 진행할지 결정합니다.",
        "purpose": "불완전하거나 호환되지 않는 프레임이 데이터에 적용되지 않도록 방지합니다.",
        "current_status": f"CALIBRATION_CHECKED / {label}",
        "recommendations": {"detected": counts, "report": "logs/calibration_report.json"},
        "cautions": cautions,
        "completion_criteria": ["검사 결과 확인", "보정 적용 여부에 대한 명시적 결정"],
        "actions": ["EDIT", "RUN", "SKIP"],
    }


def _confirm_light_linearity_task(label: str) -> dict:
    return {
        "task_id": "CONFIRM_LINEARITY",
        "title": "Linear 상태 확인",
        "summary": "후처리 시작 전 Linear 상태를 확인합니다.",
        "purpose": "Non-linear 영상에 Linear 전용 보정을 적용하지 않기 위함입니다.",
        "current_status": f"SINGLE_LIGHT / {label}",
        "recommendations": {"question": "Stretch가 적용되지 않은 Linear 데이터인가요?"},
        "cautions": ["확실하지 않다면 적용하지 마세요."],
        "completion_criteria": ["Linearity 확정"],
        "actions": ["CONFIRM"],
    }

def _gradient_task(label: str, stage: str = "STACKED_LINEAR"):
    return {
        "task_id": "GRADIENT_CORRECTION",
        "title": "Background / Gradient Correction",
        "summary": "광해, 달빛, 광학계 때문에 생긴 배경 밝기 불균형을 줄입니다.",
        "purpose": f"{label} 신호를 보존하면서 이후 색보정과 Stretch가 안정적으로 동작하도록 배경을 정리합니다.",
        "current_status": f"{stage} / {label}",
        "recommendations": {
            "engine": "Siril 1.4.4 subsky -rbf",
            "samples": 20,
            "tolerance": 1.0,
            "smooth": 0.5,
            "basis": "Siril 기본 시작값. 미리보기 후 조정"
        },
        "cautions": [
            "M31처럼 화면을 크게 차지하는 은하나 넓은 성운은 배경 샘플에 천체가 포함될 수 있어 미리보기 확인이 중요합니다.",
            "미리보기 JPEG의 AutoStretch는 표시용이며 실제 Gradient FITS는 Linear 상태를 유지합니다."
        ],
        "completion_criteria": ["배경 균일화", "희미한 구조 유지", "과도한 천체 신호 제거 없음"],
        "actions": ["PREVIEW", "RUN", "EDIT"],
    }

def format_task(task: dict) -> str:
    lines = [
        f"다음 작업: {task['title']}",
        f"요약 설명: {task['summary']}",
        f"작업 목적: {task['purpose']}",
        f"현재 상태: {task['current_status']}",
        "",
        "추천값/권장:",
    ]
    for k, v in task.get("recommendations", {}).items():
        lines.append(f"  - {k}: {v}")
    lines.append("주의사항:")
    for item in task.get("cautions", []):
        lines.append(f"  - {item}")
    lines.append("완료 기준:")
    for item in task.get("completion_criteria", []):
        lines.append(f"  - {item}")
    lines.append("선택: " + " / ".join(task.get("actions", [])))
    return "\n".join(lines)
