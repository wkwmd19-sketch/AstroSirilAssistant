# AstroSirilAssistant v0.14.0

Siril 1.4.x 기반 천체사진 반자동 보정 도구입니다.

v0.14.0의 핵심 전제는 **이전에 수동 보정에서 사용하던 Parallax / Prism 흐름을 가능한 한 그대로 반자동화**하는 것입니다.

## Single Image 기본 파이프라인

`입력/분석 → Gradient → SPCC → Parallax Restoration → Prism Denoise → GHS → StarNet → Starless → Stars → Pixel Math Recombine → Final / Export`

각 처리 단계는 기본적으로:

`분석 → 추천/설명 → 사용자 확인 → 미리보기 → 승인 → Siril 실행 → 자동 저장/로그 → 다음 단계`

순서로 진행합니다.

## v0.14 핵심 변경

- Restoration 기본 엔진: **SyQon Parallax Nano**
- Denoise 기본 엔진: **SyQon Prism Mini**
- 설치된 SyQon Python script를 Siril `pyscript`로 직접 호출
- Parallax / Prism script의 CLI 자동호출 가능 여부 검사
- 기존 **Siril PSF + Richardson-Lucy / Siril Native Denoise**를 Fallback으로 유지
- 새 프로젝트 Linear 순서를 `SPCC → Parallax → Prism → GHS`로 변경
- v0.6~v0.13 기존 진행 프로젝트는 현재 진행 상태를 되감지 않고 호환 처리
- `SyQon 설치 확인` 버튼 추가

## Astro Graphite UI

외부 GUI 프레임워크 없이 Tk/ttk 안정성을 유지하면서 공통 Dark UI를 적용했습니다.

- Navy/Graphite 기반 색상
- Accent / Success 버튼 구분
- Project / Task Card 구조
- 화면 해상도 기반 초기 창 크기
- 실제 Overflow에서만 세로 스크롤
- 상세 로그 기본 접힘 + 드래그 가능한 Log Pane
- 로그 복사
- 작업 Progress + 경과시간
- 실행 중 작업 컨트롤 잠금
- 오류 시 로그 자동 열기

`run_gui.bat`과 `run_sequence_gui.bat` 모두 같은 UI/상태 UX 정책을 사용합니다.

## 실행

### 이미 스택된 FITS 1장 보정

`run_gui.bat`

### Light / Dark / Flat 등의 Sequence 전처리

`run_sequence_gui.bat`

두 BAT 파일은 동일한 `run_common.bat`를 사용합니다.

1. `.venv\Scripts\python.exe`가 있으면 우선 사용
2. 없으면 `py -3` 사용
3. Python이 없거나 프로그램이 비정상 종료되면 오류를 표시하고 창을 유지

## SyQon 준비

Siril에서 Parallax / Prism script와 필요한 모델을 설치/설정해야 합니다.

앱의 `SyQon 설치 확인` 버튼으로 script 경로와 반자동 CLI 호출 준비 여부를 확인할 수 있습니다.

자동 감지가 되지 않는 사용자 정의 Siril script 저장소는 `config/app.yaml`에 추가할 수 있습니다.

```yaml
syqon:
  script_roots:
    - 'D:\path\to\siril-scripts'
```

SyQon을 사용할 수 없는 경우 각 단계에서 Siril Native 엔진으로 변경할 수 있습니다.

## 새 프로젝트 작업 폴더

```text
working\
├─ 00_calibrated
├─ 01_registered
├─ 02_stacked
├─ 03_gradient
├─ 04_color
├─ 05_restore
├─ 06_denoise
├─ 07_stretch
├─ 08_starnet
├─ 09_starless
├─ 10_stars
├─ 11_recombine
└─ 12_final
```

최종 결과는 `_Auto` 이름을 사용합니다.

예:

- `M31_final_Auto.fits`
- `M31_final_Auto.tif`
- `M31_final_Auto.png`

## Sequence → Single Image 연결

`run_sequence_gui.bat`에서 Calibration / Registration / Stack 완료 후 생성된 Stack FITS를 `run_gui.bat`의 Single Image 파이프라인으로 이어서 처리할 수 있습니다.

## 기존 프로젝트 호환

- 이미 후반 단계까지 진행된 프로젝트를 v0.14가 자동으로 앞 단계로 되돌리지 않습니다.
- `COLOR_CALIBRATED` 상태에서 아직 Denoise/Restoration을 시작하지 않은 프로젝트는 새 기본 순서인 Restoration → Denoise로 이동합니다.
- 이전 버전에서 Denoise가 이미 완료된 프로젝트는 기존 순서를 유지해 Restoration → GHS로 이어집니다.

## 현재 범위

v0.14의 SyQon 직접 연동은 우선 **Parallax + Prism**입니다.

Star separation은 현재 검증된 `StarNet.py` 경로를 유지합니다.

세부 구현/변경 내용은 `docs/` 폴더를 참고하세요.
