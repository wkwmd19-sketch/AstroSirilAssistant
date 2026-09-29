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

    if linearity == "NONLINEAR":
        return {
            "task_id": "REVIEW_INPUT_STATE",
            "title": "입력 상태 검토",
            "summary": "현재 FITS는 이미 Stretch된 흔적이 있어 초기 Linear 보정 파이프라인을 바로 적용하지 않습니다.",
            "purpose": "중복 Stretch와 과보정을 방지합니다.",
            "current_status": "INPUT_ANALYZED / NONLINEAR",
            "recommendations": {"action": "사용자 확인 후 적절한 중간 단계부터 시작"},
            "cautions": ["GHS 초기 Stretch를 자동 적용하지 않습니다."],
            "completion_criteria": ["현재 파일이 어느 단계까지 처리됐는지 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    if linearity == "UNKNOWN":
        return {
            "task_id": "CONFIRM_LINEARITY",
            "title": "Linear 상태 확인",
            "summary": "FITS HISTORY만으로는 Linear/Non-linear을 확정할 수 없습니다.",
            "purpose": "잘못된 초기 Stretch 적용을 방지하기 위해 사용자가 처리 상태를 확인합니다.",
            "current_status": f"INPUT_ANALYZED / {label}",
            "recommendations": {
                "question": "이 파일은 스택 후 아직 실제 Stretch를 적용하지 않은 Linear 이미지인가요?"
            },
            "cautions": [
                "Siril의 AutoStretch 화면 표시만 사용한 것은 데이터 Stretch가 아닙니다.",
                "GHS/Histogram/Asinh 등을 실제 적용했다면 Non-linear로 선택합니다."
            ],
            "completion_criteria": ["사용자가 LINEAR 또는 NONLINEAR 확인"],
            "actions": ["CONFIRM", "EDIT"],
        }

    return {
        "task_id": "GRADIENT_CORRECTION",
        "title": "Background / Gradient Correction",
        "summary": "광해, 달빛, 센서/광학계 때문에 생긴 배경 밝기 불균형을 줄입니다.",
        "purpose": f"{label} 신호를 보존하면서 이후 색보정과 Stretch가 안정적으로 동작하도록 배경을 정리합니다.",
        "current_status": f"INPUT_ANALYZED / LINEAR / {label}",
        "recommendations": {
            "engine": "Siril subsky",
            "mode": "RBF 우선 검토",
            "parameters": "v0.4에서 이미지 분석 기반 자동 추천 연결"
        },
        "cautions": [
            "은하 외곽, 성운, 은하수 자체가 배경 샘플에 포함되지 않도록 보호합니다."
        ],
        "completion_criteria": [
            "배경이 균일해짐",
            "천체의 희미한 외곽 구조가 제거되지 않음"
        ],
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
