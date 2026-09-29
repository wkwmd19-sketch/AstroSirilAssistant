# SPCC v0.5.0

Siril 1.4.4의 scriptable 명령을 사용합니다.

- `platesolve`
- `spcc`
- `spcc_list`
- `online`

## SPCC 기본 조건
- 이미지가 Linear
- Plate Solved
- Gaia DR3 사용 가능
- 촬영 Sensor / Filter 정보

## 기본값
- Camera Mode: OSC
- Sensor: Sony IMX678
- OSC Filter: DWARF Mini Astro
- White Reference: Average Spiral Galaxy
- Catalog: AUTO
- Background Tolerance: -2.8 / +2.0

Sensor / Filter 이름은 실제 Siril SPCC 데이터베이스 이름과 정확히 일치해야 합니다.
따라서 GUI에서 `SPCC 목록 불러오기`를 제공하며 `spcc_list`로 현재 Siril 목록을 읽습니다.

## 안전 흐름
`SPCC 목록 확인 → Plate Solve 상태 확인 → SPCC 미리보기 → 승인 → 실제 적용`

미리보기는 임시 복사본에 Plate Solve + SPCC를 수행하고,
표시용 AutoStretch JPEG를 생성합니다.
실제 작업 FITS는 미리보기 단계에서 변경되지 않습니다.
