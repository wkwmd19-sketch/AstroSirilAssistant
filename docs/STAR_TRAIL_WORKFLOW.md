# Star Trail Workflow v0.3.2

## 목적

별의 이동 자체를 결과물로 사용하는 촬영을 일반 딥스카이 스택과 분리해서 관리합니다.

## 프로파일

- `STAR_TRAIL_SKY`
- `STAR_TRAIL_LANDSCAPE`

## 핵심 원칙

1. 일반 별 정렬을 하지 않습니다.
2. 연속 프레임 시퀀스가 기본 입력입니다.
3. Dark는 핫픽셀/고정패턴 억제에 유용할 수 있습니다.
4. Flat은 비네팅/먼지 얼룩 보정에 유용할 수 있습니다.
5. 프레임 간 시간 간격(gap)을 중요하게 봅니다.
6. 비행기/위성/자동차 불빛/구름/흔들림 프레임은 후보 제안 방식으로 검토합니다.

## 상태 흐름

`INPUT_IMPORTED`
→ `INPUT_ANALYZED`
→ `STAR_TRAIL_MODE_CONFIRMED`
→ `CALIBRATION_CHECKED`
→ `CALIBRATED`
→ `FRAME_QUALITY_CHECKED`
→ `STAR_TRAIL_COMPOSITED`
→ `FINALIZED`

## 참고

v0.3.2에서는 실제 일주 합성을 수행하지 않고,
프로파일/상태머신/설명/캘리브레이션 연동까지만 제공합니다.
다음 단계에서 자체 합성 또는 외부 엔진 연계를 붙일 예정입니다.
