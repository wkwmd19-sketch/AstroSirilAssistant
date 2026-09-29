# AstroSirilAssistant v0.12.0 — Pixel Math Recombine

현재 실제 처리 흐름:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet → Starless → Stars → Pixel Math Recombine → Final/Export(다음 구현)`

## v0.12 핵심
- Siril 1.4.4 `pm` 실제 실행
- 기본 표현식: `Main + Stars * Star Weight`
- `-nosum` 고정
- Rescale Output 선택 가능 / 기본 OFF
- Stars Processing의 Brightness를 중복 반영하지 않는 Recombine 추천
- Preview 결과의 highlight clipping 통계
- 동일 설정 Apply 시 Preview FITS를 재계산 없이 정식 결과로 승격
- 결과: `working\11_recombine\{TARGET}_11_recombined.fits`
- State: `RECOMBINED`

v0.11.1의 스크롤/로그 Pane 핫픽스도 그대로 포함합니다.

---

# AstroSirilAssistant v0.12.0 — Dynamic UI Hotfix

v0.11.0의 Stars Processing 기능은 그대로 유지합니다.

이번 Hotfix:
- 짧은 페이지에서 마우스휠을 움직이면 UI가 위/아래로 크게 밀리던 문제 수정
- 화면보다 내용이 짧을 때 Scroll 자체를 비활성화
- 실제 overflow에서만 일정한 픽셀 단위로 Scroll
- `상세 로그 보기`를 눌러도 Log Pane이 1px 높이로 남아 보이지 않던 문제 수정
- Log Pane을 열 때 geometry 완료 후 sash 위치를 여러 번 안정화
- 사용자가 조절한 로그 높이 비율을 다시 열 때 복원

---

# AstroSirilAssistant v0.12.0 — Stars Processing + Dynamic UI

현재 실제 처리 흐름:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet → Starless → Stars Processing → Pixel Math Recombine(다음 구현)`

## Stars Processing
- Target-aware Recommendation Engine v0.2
- Stars Brightness Scale (`fmul`)
- Stars Saturation (`satu`)
- 추천 다시 계산 / 추천값 적용 / 천체 특징 수정
- 미리보기 / 승인 후 적용 / 건너뛰기
- Main/Starless 레이어는 보존

## Dynamic UI
- 고정 1050x820 창 제거
- 화면 해상도에 맞춘 초기 창 크기
- 전체 작업영역 세로 스크롤
- 창 폭에 맞춰 내부 UI 자동 확장
- 로그는 별도 Resizable Pane
- 로그/작업영역 사이 경계선을 드래그해 높이 조절
- 낮은 해상도에서도 아래 버튼과 로그에 접근 가능

기존 v0.10에서 Starless Processing까지 완료한 프로젝트는
`기존 프로젝트 열기`로 Stars Processing 실제 UI에 진입합니다.

---

# AstroSirilAssistant v0.12.0 — Starless Processing + Target-aware Recommendations

현재 실제 흐름:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet → Starless Processing → Stars Processing(다음 구현)`

## v0.10 핵심
- Starless CLAHE 실제 실행
- Starless Saturation 실제 실행
- Target-aware Recommendation Engine v0.1
- Category + Target Features + 현재 이미지 통계 기반 시작값
- M31/M33/M51/M42 등 일부 대표 대상 특징 Registry
- `추천 다시 계산`
- `추천값 적용`
- `천체 특징 수정`
- 추천은 자동 적용하지 않고 사용자가 선택
- Starless 미리보기 / 승인 후 적용 / 건너뛰기
- Stars 레이어는 변경하지 않음

기존 v0.9에서 StarNet까지 완료한 프로젝트를 열면
Starless Processing 실제 UI로 자동 마이그레이션됩니다.

---

# AstroSirilAssistant v0.12.0 — StarNet / 별 분리

현재 실제 처리 흐름:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet → Starless Processing(다음 구현)`

## v0.9 핵심
- Siril 공식 Python StarNet wrapper 사용
- StarNet2 2.5+ 경로
- 현재 Non-linear 상태에 맞춰 `--no-linear` 자동 고정
- Stride Standard / Large / Small / Custom
- 2x Upsampling
- Protect Highlights
- Subtraction Stars layer
- 선택적 Native Starmask
- Starless / Stars 미리보기
- 비싼 AI 작업을 두 번 하지 않도록 Preview 결과를 Apply에서 재사용
- Starless / Stars 정식 FITS 자동 저장
- Common Help System 적용

기존 v0.8에서 GHS를 완료하고 StarNet 단계에 있는 프로젝트는
`기존 프로젝트 열기`로 바로 실제 StarNet UI로 마이그레이션됩니다.

---

# AstroSirilAssistant v0.12.0 — GHS Stretch

처리 흐름:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet(다음 구현)`

## v0.8 핵심
- Siril `autoghs` 실제 실행
- Siril `ght` Manual 고급 모드
- GHS 미리보기 / 승인 후 적용
- 첫 Pass에서 Linear → Non-linear State 자동 전환
- 여러 GHS Pass를 명시적으로 반복 가능
- 각 Pass를 개별 FITS와 로그로 저장
- GHS 미리보기에는 추가 AutoStretch를 적용하지 않음
- Stretch 완료 후 StarNet 단계로 이동

기존 v0.7에서 Deblur까지 완료한 프로젝트는
`기존 프로젝트 열기`로 바로 GHS 단계에 진입합니다.

---

# AstroSirilAssistant v0.12.0 — Deblur / Deconvolution

이번 버전은 v0.6.0의 Denoise 다음 단계를 실제 구현합니다.

`SPCC → Denoise → Deblur → GHS(다음 구현)`

Deblur는 Siril 1.4.4의:
- `makepsf stars`
- `rl`

을 이용합니다.

기존 v0.6.0에서 Denoise까지 완료한 프로젝트는
`기존 프로젝트 열기`로 열면 자동으로 Deblur 단계로 마이그레이션됩니다.

기존 Progress Bar / 경과시간 / 접이식 로그 / 성공 팝업 / Common Help System도 그대로 적용됩니다.

---

# AstroSirilAssistant v0.12.0 — 작업 상태 UX + Denoise

## 새 UI
- 승인 후 적용 성공 팝업
- 실행 중 무한 Progress Bar
- 실행 경과시간
- 처리 중 주요 버튼 잠금
- 상세 로그 보기/숨기기
- 로그 복사
- 오류 시 로그 자동 펼침

## SPCC 다음 실제 단계
`COLOR_CALIBRATED / LINEAR → DENOISE`

기존 v0.5.x에서 SPCC까지 끝난 프로젝트도 `기존 프로젝트 열기`로 열면
자동으로 Denoise 단계가 표시됩니다.

---

# AstroSirilAssistant v0.12.0 — Help UI 정리 + SPCC Hotfix

- 파라미터별 `?` 버튼 → 섹션당 `도움말 ?` 1개로 정리
- Tooltip은 항목명 Label에만 표시
- 상세 도움말 팝업은 항상 1개만 유지
- Siril 1.4.4 Windows의 `-bgtol=-2.8,2` 오류 우회

---

# AstroSirilAssistant v0.12.0 — SPCC + Common Help System

이번 버전의 오늘 테스트 범위:

`기존 M31 프로젝트 열기 → SPCC 목록 불러오기 → Plate Solve 상태 확인 → SPCC 미리보기 → 승인 후 적용`

## 새 기능
- Siril `spcc_list` 기반 Sensor / Filter / White Reference 목록
- `platesolve` 자동 선행
- Siril `spcc` 실제 미리보기/적용
- Gaia DR3 Catalog 선택
- Background Tolerance -2.8 / +2.0
- Common Help System v0.1
  - 짧은 마우스오버 Tooltip
  - 각 항목 옆 `?` 상세 도움말
- 기존 Gradient 항목에도 Help System 적용

SPCC는 Linear + Plate Solved 이미지가 필요합니다.
오늘 테스트는 OSC 경로를 우선 대상으로 하며 Mono 엔진 지원은 포함하지만
GUI의 R/G/B 필터 입력은 다음 확장에 추가합니다.

---

# AstroSirilAssistant v0.12.0 — Interactive single-FITS + Gradient

v0.4.2에서는 `run_gui.bat`에 실제 단계 선택 버튼과 Gradient 미리보기/적용 기능이 추가되었습니다.

### 단일 스택 FITS 흐름

`분석 → [스택된 Linear] → Gradient 값 확인 → [미리보기] → [승인 후 적용] → M31_03_gradient.fits`

미리보기는 표시용 AutoStretch JPEG를 만들지만 실제 작업 FITS는 Linear 상태를 유지합니다.

---

# AstroSirilAssistant v0.12.0 — Siril 1.4.4 script hotfix

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
