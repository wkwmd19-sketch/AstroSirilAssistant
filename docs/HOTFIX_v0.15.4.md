# HOTFIX v0.15.4

## 변경 내용
- 단일 이미지(SINGLE_LIGHT) 프로젝트에서 캘리브레이션 프레임이 하나도 없어도 즉시 생략하고 다음 단계(Gradient)로 진행할 수 있도록 수정했습니다.
- `CHECK_CALIBRATION_FRAMES` 단계에서도 `프레임 없이 바로 후처리로 계속` 버튼을 표시합니다.
- 백엔드 `skip_project_calibration()`이 `CHECK_CALIBRATION_FRAMES`와 `REVIEW_CALIBRATION_FRAMES` 두 단계 모두에서 동작하도록 확장했습니다.

## 의도
- 캘리브레이션 프레임이 없는 일반 단일 촬영 이미지도 막히지 않고 후처리 흐름을 이어갈 수 있게 합니다.

## 주의
- 이 변경은 실제 캘리브레이션 적용 기능을 추가한 것이 아닙니다.
- 시퀀스(LIGHT_SEQUENCE/REGISTERED_SEQUENCE)는 기존처럼 별도 Calibration / Registration / Stack 워크플로를 사용해야 합니다.
