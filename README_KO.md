# AstroSirilAssistant v0.4.2 — Interactive single-FITS + Gradient

v0.4.2에서는 `run_gui.bat`에 실제 단계 선택 버튼과 Gradient 미리보기/적용 기능이 추가되었습니다.

### 단일 스택 FITS 흐름

`분석 → [스택된 Linear] → Gradient 값 확인 → [미리보기] → [승인 후 적용] → M31_03_gradient.fits`

미리보기는 표시용 AutoStretch JPEG를 만들지만 실제 작업 FITS는 Linear 상태를 유지합니다.

---

# AstroSirilAssistant v0.4.2 — Siril 1.4.4 script hotfix

> v0.4.1 fixes the single-FITS analysis failure caused by the missing `requires` command in Siril 1.4.4.

## 기존 v0.4 기능


이제 규격만 있는 단계에서 벗어나,
**FITS Light sequence에 대해 Siril CLI를 실제 실행하여 Calibration → Registration → Stack**까지 수행할 수 있습니다.

## 가장 쉬운 실행

1. `install_windows.bat`
2. `run_sequence_gui.bat`
3. Lights / Dark / Flat / Bias / Dark-flat 폴더 지정
4. 대상명 / 날짜 / 카메라 모드 지정
5. `1. 프로젝트 생성`
6. `2. 실행 계획 보기`
7. 계획 확인
8. `3. 승인 후 실제 실행`

## 반자동 안전 원칙

실제 Siril 처리는 사용자 승인 전에는 실행되지 않습니다.

GUI에서도 반드시:
`계획 생성 → 확인 → 실제 실행`
순서를 거칩니다.

## v0.4 실제 지원 범위

- 딥스카이 FITS Light sequence
- OSC 또는 Mono
- Dark
- Flat
- Bias
- Dark-flat
- Master 생성
- Calibration
- Deep-sky registration
- Rejection stack

## 아직 전용 실행 경로를 사용하지 않는 대상

- 별 일주사진
- 혜성
- 달 / 목성 / 토성
- 모자이크

이 대상들은 프로파일/규격은 이미 존재하지만, 각각 전용 엔진으로 구현할 예정입니다.

## CLI 예

프로젝트 생성:

`run_cli.bat new-sequence --lights "D:\M31\lights" --darks "D:\M31\darks" --flats "D:\M31\flats" --target M31 --date 2026-09-29 --category GALAXY --camera-mode OSC`

계획 확인:

`run_cli.bat preprocess-plan "D:\AstroProjects_Auto\M31_2026-09-29_Auto"`

실제 실행:

`run_cli.bat preprocess-run "D:\AstroProjects_Auto\M31_2026-09-29_Auto" --yes`

최종 스택 예:

`D:\AstroProjects_Auto\M31_2026-09-29_Auto\working\02_stacked\M31_02_stacked.fit`

다음 구현 목표는 이 결과를 이어 받아:
**Gradient → SPCC → GHS → StarNet → Pixel Math 재합성**
경로를 실제 실행 기능으로 연결하는 것입니다.
