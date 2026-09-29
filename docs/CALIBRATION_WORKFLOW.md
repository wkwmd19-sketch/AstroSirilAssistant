# Calibration Workflow v0.3.1

## 공통 흐름

`INPUT_IMPORTED`
→ `INPUT_ANALYZED`
→ `INPUT_STAGE_CONFIRMED`

### 개별 Light/Sequence이고 미보정인 경우

`RAW_UNCALIBRATED`
→ `CALIBRATION_CHECKED`
→ `CALIBRATED`
→ `REGISTERED`
→ `STACKED_LINEAR`

### 이미 캘리브레이션된 Light/Sequence

`PRECALIBRATED`
→ `PRECALIBRATED_CONFIRMED`
→ `REGISTERED`
→ `STACKED_LINEAR`

### 이미 스택된 Linear FITS

`STACKED_LINEAR`
→ 캘리브레이션 재적용 없음
→ `GRADIENT_CORRECTED`

### 이미 Stretch된 스택

`STACKED_NONLINEAR`
→ 초기 Linear 파이프라인 중단
→ 사용자에게 현재 처리 단계 확인

## 스마트 망원경 / DWARF 류

브랜드명만으로 "이미 캘리브레이션되었다"고 단정하지 않습니다.
실제 입력 파일의 종류와 사용자가 가져온 처리 단계에 따라:

- 원본 Light sequence
- 기기 내부 보정 Light
- 스택 FITS
- 이미 Stretch된 이미지

를 구분합니다.

확실하지 않으면 `UNKNOWN`으로 유지합니다.
