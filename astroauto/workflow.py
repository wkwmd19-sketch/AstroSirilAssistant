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
    "UNKNOWN": "미분류",
}

def next_task_after_analysis(project: dict):
    p = project["project"]
    linearity = p["image_state"].get("linearity", "UNKNOWN")
    category = p["target"].get("category", "UNKNOWN")
    label = PROFILE_LABELS.get(category, category)
    source_stage = p.get("input_stage", {}).get("source_stage", "UNKNOWN")
    input_status = p.get("calibration", {}).get("input_status", "UNKNOWN")

    if source_stage == "UNKNOWN":
        return {
            "task_id": "CONFIRM_INPUT_STAGE",
            "title": "입력 데이터 단계 확인",
            "summary": "현재 파일이 개별 Light인지, 등록/스택 완료 데이터인지 먼저 확인합니다.",
            "purpose": "캘리브레이션과 스택을 이미 처리한 데이터에 다시 적용하지 않기 위함입니다.",
            "current_status": f"INPUT_ANALYZED / {label}",
            "recommendations": {
                "options": "LIGHT_SEQUENCE / SINGLE_LIGHT / REGISTERED_SEQUENCE / STACKED_LINEAR / STACKED_NONLINEAR"
            },
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
        return {
            "task_id": "CHECK_CALIBRATION_FRAMES",
            "title": "Dark / Flat / Bias / Dark-flat 검사",
            "summary": "보유한 캘리브레이션 프레임을 감지하고 Light와 조건이 맞는지 검사합니다.",
            "purpose": "스택 전에 센서/광학계의 체계적인 오차를 가능한 범위에서 제거합니다.",
            "current_status": f"{source_stage} / RAW_UNCALIBRATED",
            "recommendations": {"scan": "calibration/dark, bias, flat, dark_flat"},
            "cautions": [
                "Bias와 Dark-flat을 무조건 동시에 요구하거나 중복 적용하지 않습니다.",
                "Dark는 Light의 노출/Gain/온도 조건을 비교합니다.",
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

    # Generic conservative fallback
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

    return _gradient_task(label)

def _gradient_task(label: str):
    return {
        "task_id": "GRADIENT_CORRECTION",
        "title": "Background / Gradient Correction",
        "summary": "광해, 달빛, 광학계 때문에 생긴 배경 밝기 불균형을 줄입니다.",
        "purpose": f"{label} 신호를 보존하면서 이후 색보정과 Stretch가 안정적으로 동작하도록 배경을 정리합니다.",
        "current_status": f"STACKED_LINEAR / {label}",
        "recommendations": {
            "engine": "Siril subsky",
            "mode": "RBF 우선 검토",
            "parameters": "향후 이미지 분석 기반 자동 추천"
        },
        "cautions": ["희미한 천체 구조가 배경으로 제거되지 않도록 보호합니다."],
        "completion_criteria": ["배경 균일화", "희미한 구조 유지"],
        "actions": ["PREVIEW", "RUN", "EDIT", "SKIP"],
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
