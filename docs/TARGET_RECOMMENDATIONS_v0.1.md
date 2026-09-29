# Target-aware Recommendation Engine v0.1

## Goal

추천값을 하나의 고정값으로 강제하지 않고 다음 정보를 조합합니다.

1. Target Category
2. Structural Features
3. Current image statistics
4. Current processing stage

출력은 항상 `STARTING_POINT`이며 자동 정답값으로 취급하지 않습니다.

## Target Features

예:
- BRIGHT_CORE
- FAINT_OUTER_STRUCTURE
- DUST_LANES
- LOW_SURFACE_BRIGHTNESS
- FINE_FILAMENTS
- STRONG_EMISSION
- HIGH_DYNAMIC_RANGE
- WIDE_DIFFUSE

## Known target registry

v0.1에는 사용자가 자주 촬영한 대표 대상 일부를 초기 등록합니다.

- M31
- M33
- M51
- M42
- IC1805
- IC1848
- NGC1499
- NGC281
- NGC6992

이름이 등록되지 않은 대상은 Category 기본 프로필을 사용합니다.

## Human control

UI에서:
- 추천 다시 계산
- 추천값 적용
- 천체 특징 수정

을 제공합니다.

사용자가 특징을 수정하면 USER_CONFIRMED로 저장하며 자동 추정보다 우선합니다.

## First integration

v0.10.0은 Starless Processing에 처음 연결합니다.

이후 같은 엔진을:
- Gradient
- Denoise
- Deblur
- GHS
- StarNet
- Stars Processing
로 확장할 수 있습니다.
