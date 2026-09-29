# AstroSirilAssistant v0.3.1 — Calibration-aware MVP

v0.3에 **Dark / Bias / Flat / Dark-flat 관리와 검증 구조**를 추가한 보완판입니다.

## 새 프로젝트 기본 경로

`D:\AstroProjects_Auto\{대상}_{YYYY-MM-DD}_Auto\`

예:

`D:\AstroProjects_Auto\M31_2026-09-29_Auto\`

## 새 폴더 구조

```text
M31_2026-09-29_Auto\
├─ input\
│  └─ lights\
├─ calibration\
│  ├─ dark\
│  ├─ bias\
│  ├─ flat\
│  ├─ dark_flat\
│  └─ masters\
├─ working\
│  ├─ 00_calibrated\
│  ├─ 01_registered\
│  ├─ 02_stacked\
│  ├─ 03_gradient\
│  ├─ 04_color\
│  ├─ 05_denoise\
│  ├─ 06_stretch\
│  ├─ 07_starnet\
│  ├─ 08_starless\
│  ├─ 09_recombine\
│  └─ 10_final\
├─ output\
├─ logs\
└─ temp\
```

## 캘리브레이션 상태

입력은 반드시 다음 중 하나로 관리합니다.

- `RAW_UNCALIBRATED`
- `PRECALIBRATED`
- `UNKNOWN`

`PRECALIBRATED` 입력에는 캘리브레이션을 다시 적용하지 않습니다.

## 입력 단계

- `LIGHT_SEQUENCE`
- `SINGLE_LIGHT`
- `REGISTERED_SEQUENCE`
- `STACKED_LINEAR`
- `STACKED_NONLINEAR`
- `UNKNOWN`

DWARF 등 스마트 망원경 결과물처럼 내부 처리 여부가 확실하지 않으면 `UNKNOWN`으로 유지하고 사용자 확인을 받습니다.

## 캘리브레이션 검사

프로젝트 생성 후 보유한 파일을 다음 폴더에 넣습니다.

- Dark → `calibration\dark`
- Bias → `calibration\bias`
- Flat → `calibration\flat`
- Dark-flat → `calibration\dark_flat`

그 다음:

`run_cli.bat calibration-check "D:\AstroProjects_Auto\M31_2026-09-29_Auto"`

프로그램은 각 FITS 헤더에서 가능한 범위 내에서 다음 조건을 읽고 비교합니다.

### Dark
- 프레임 크기
- 노출시간
- Gain
- 센서 온도(헤더에 있을 경우)

### Flat
- 프레임 크기
- Filter
- Bayer pattern
- 광학계/필터 일치 여부는 메타데이터가 부족하면 사용자 확인

### Bias
- 프레임 크기
- Gain(알 수 있을 경우)

### Dark-flat
- 프레임 크기
- Flat 노출시간과의 일치
- Gain
- 온도(알 수 있을 경우)

## 중요한 정책

Bias와 Dark-flat은 **무조건 둘 다 요구하지 않습니다.**
센서와 실제 촬영 방식에 따라 적절한 경로를 선택하도록 설계되어 있습니다.

캘리브레이션 프레임이 없다고 해서 프로그램이 임의로 만들어내지 않습니다.
없거나 불확실하면 그 영향을 설명하고 사용자의 선택을 받습니다.

## 현재 한계

v0.3.1은 캘리브레이션 프레임의 **감지/메타데이터 분석/호환성 검사/State 관리**까지 구현합니다.

실제 Siril `preprocess`/master 생성/캘리브레이션 실행은 다음 구현 단계에서 연결합니다.
이는 중복 캘리브레이션 방지와 센서별 정책을 먼저 안정화하기 위함입니다.
