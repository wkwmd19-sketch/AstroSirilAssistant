# AstroSirilAssistant v0.16.0 — 단일 이미지 후처리 전체 경로 통합

기존 v0.15.4의 프로젝트/RAW 처리·캘리브레이션 검사 기능을 보존하면서 Gradient부터 최종 내보내기까지 끊기던 작업 흐름을 연결했습니다.

- **캘리브레이션 프레임이 없으면 검사 없이 승인 후 Gradient로 이동**하는 경로의 상태 버그 수정.
- **Gradient / SPCC**는 미리보기·적용하거나 사용자 승인하에 생략할 수 있습니다.
- **Restoration / Denoise**를 각각 또는 모두 생략해도 GHS 단계로 정상 진입합니다.
- **GHS**로 최소 한 번 실제 Stretch하여 Non-linear 이미지를 만든 뒤 StarNet 적용 여부를 선택합니다.
- **StarNet 적용:** Starless · Stars 개별 처리 → Pixel Math 재합성 → FITS/TIFF/PNG 최종 내보내기.
- **StarNet 생략:** 원래 Non-linear 이미지를 바로 최종 미리보기 및 FITS/TIFF/PNG 내보내기로 연결합니다.
- 이전 버전에서 StarNet을 생략한 뒤 중단된 프로젝트(`POST_STARNET_SKIPPED`)도 재열기 시 안전하게 이어갈 수 있습니다.
- 상태·원본 보존·단계 이동 검증을 추가했습니다. 실제 Windows/Siril/SyQon 전체 처리 검증은 사용자 환경에서 필요합니다.

전체 흐름 및 제한 사항: `docs/END_TO_END_v0.16.0.md`

---

# AstroSirilAssistant v0.15.3 — 캘리브레이션 프레임 검사 단계

0.15.2에서 CR3 이미지 분석 및 프로젝트 생성까지 완료된 것을 확인했습니다. 프로젝트 생성 뒤의 다음 작업인 Dark·Bias·Flat·Dark-flat 검사 GUI를 연결했습니다.

- [Dark/Bias/Flat/Dark-flat] 선택 → [폴더에서 등록] 또는 [프레임 폴더 열기] → [프레임 검사 / 재검사] → 화면에서 조건·오류 확인.
- 캘리브레이션 파일은 FITS·카메라 RAW를 지원합니다. RAW는 Siril을 통해 임시 변환 후 정보를 검사합니다. 원본은 보존합니다.
- 단일 Light에서 **명시적으로 승인한 경우만** 보정 없이 Gradient 단계로 진행합니다. 현재 버전은 **검사 전용**이며 Master 제작·Light 수치 보정은 수행하지 않습니다.
- 기존 v0.15.2 프로젝트를 그대로 열 수 있습니다. 세부 안내: `docs/CALIBRATION_CHECK_v0.15.3.md`, `docs/handoff/08_v0153_캘리브레이션_검사.md`.
- 실제 Windows/Siril 및 Astropy FITS 입출력 회귀 검증은 남아 있습니다. Git 커밋/푸시는 하지 않았습니다.

---

# AstroSirilAssistant v0.15.2 — FITS 이미지 분석 호환성 핫픽스 + 인수인계 문서

v0.15.1 CR3 테스트에서 Siril/LibRaw 변환과 `jsonmetadata`는 성공했으나 후속 이미지 분석이 중단됐습니다.
`astroauto/fits_analysis.py`가 BZERO/BSCALE 스케일링이 필요한 16-bit FITS를 `memmap=True`로 열던 호환성 문제를 수정했습니다.
픽셀·헤더 읽기에서 `memmap=False`를 사용하고, 대형 이미지에서는 float64 배열로 바꾸기 **전에** 채널을 제한 샘플링합니다.

- RAW 디코딩·원본 보존·기존 FITS 처리 순서·SyQon·Final Export는 변경하지 않았습니다.
- 인수인계 문서 9개: `docs/handoff/` (요구사항, UI 문구/용어, 단계·파일 규칙, 변경 이력, 미해결 문제).
- 상세: `docs/HOTFIX_v0.15.2.md` 및 `docs/handoff/00_먼저_읽기.md`.
- **실제 Windows/Siril 1.4.4/Canon EOS RP CR3 전체 흐름은 아직 검증되지 않았습니다.**
- Git 커밋/푸시는 수행하지 않았습니다.

---

# AstroSirilAssistant v0.15.1 — CR3/RAW 변환 경로 수정

Siril 내부 작업 디렉터리를 RAW 임시 폴더로 명시적으로 지정해 `convertraw`의 `No RAW files were found for conversion` 오류를 수정했습니다. 자세한 내용은 `docs/HOTFIX_v0.15.1.md`를 참조하세요.

---

# AstroSirilAssistant v0.15.0 — Multi-format Intake

이번 버전은 단일 이미지 입력 계층을 FITS 전용에서 다중 포맷으로 확장합니다.
기존에 Windows + Siril 1.4.4 + SyQon 환경에서 Final까지 검증된 FITS 처리 파이프라인은 유지하고,
입력 단계 앞에 **원본 보존 → 이미지 분석 → 작업용 FITS 표준화** 계층을 추가했습니다.

## 지원 입력

- FITS: `.fits`, `.fit`, `.fts`, `.fits.fz`
- Camera RAW: `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.raf`, `.orf`, `.rw2`, `.pef`
- Raster: `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg`

## 입력 원칙

- 사용자가 선택한 원본은 `input/original`에 그대로 복사해 보존합니다.
- 실제 보정은 `input/normalized/<target>_00_input.fits`에서 시작합니다.
- Camera RAW는 Siril의 RAW 변환 경로(LibRaw)에서 Debayer한 뒤 32-bit 작업 모드 FITS로 표준화합니다.
- RAW 변환 결과가 명확하게 생성되지 않으면 실패로 처리합니다. Debayer 여부가 불명확한 일반 loader fallback은 사용하지 않습니다.
- JPEG는 손실압축/표시용 형식이므로 Non-linear 입력으로 취급합니다.
- PNG/TIFF는 확장자만으로 Linear/Non-linear를 단정하지 않습니다.
- FITS 입력은 분석은 원본에서 직접 수행하고, 프로젝트 생성 시 원본 보존본과 정규화 작업본을 분리합니다.

## 프로젝트 입력 구조

```text
Auto_<대상>_<촬영일>/
├─ input/
│  ├─ original/       # 사용자 원본, 수정 금지
│  ├─ normalized/     # 파이프라인용 FITS
│  ├─ metadata/       # 원본/변환 메타데이터 JSON
│  └─ lights/         # 기존/Sequence 호환
├─ working/
├─ output/
├─ logs/
└─ project.yaml
```

## 이미지 분석

프로젝트 생성 전 `이미지 분석`이 다음을 수행합니다.

- 입력 형식 분류
- 필요한 경우 작업용 FITS 생성
- 해상도/비트 깊이/촬영 메타데이터 분석
- 대상명과 촬영일 자동 입력 시도
- Linear/Non-linear 안전 판정
- 변환 방식과 원본 형식 기록

분석 캐시의 작업용 FITS는 프로젝트 생성 후 `input/normalized`로 복사되고 임시 캐시는 정리됩니다.

## 메타데이터

`input/metadata/source_metadata.json`에 원본 파일 정보, 변환된 FITS 헤더 매핑,
Siril 메타데이터를 기록합니다. `project.yaml`에도 source format / family / lossy / RAW 여부와
normalization method를 기록합니다.

## 현재 범위

v0.15.0은 **다중 포맷 단일 이미지 입력 계층의 첫 버전**입니다.

- 기존 FITS 딥스카이 보정 파이프라인은 유지됩니다.
- RAW 시퀀스의 정식 Calibration → Debayer → Registration → Stack은 별도 Sequence 흐름의 역할입니다.
- 달/행성, 은하수/풍경, 별 일주 등의 전용 후처리 파이프라인은 이후 프로파일 단계에서 확장합니다.
- JPEG/PNG/TIFF를 억지로 Linear 딥스카이 파이프라인에 자동 투입하지 않습니다.

## 첫 실기 검증 권장

1. CR3 한 장 선택
2. `이미지 분석`
3. 로그에서 `RAW Decode: Siril/LibRaw + Debayer` 확인
4. 카메라/촬영일/노출/ISO 등 표시 확인
5. 프로젝트 생성
6. `input/original`에 CR3가 그대로 있는지 확인
7. `input/normalized`에 32-bit 작업용 FITS가 생성됐는지 확인
8. 정규화 FITS의 색/방향/해상도/Linear 상태를 확인한 뒤 다음 단계 진행

---

# AstroSirilAssistant v0.14.9 — Focus & Input Polish

프로젝트 입력 화면의 Windows 렌더링 잔여 픽셀과 포커스 UX를 다듬은 소규모 UI 패치입니다.

- 프로젝트 입력의 텍스트 입력 필드를 완전한 borderless native Entry로 변경해 모서리의 1px 점/잔여 테두리를 제거했습니다.
- 대상 종류 Combobox도 focus border 없는 레이아웃으로 정리했습니다.
- 입력창/콤보/버튼 등에 포커스가 있을 때 화면의 빈 여백, 카드 배경, 라벨 영역을 좌클릭하면 포커스와 텍스트 선택이 해제됩니다.
- 값 자체는 변경되지 않으며 FocusOut 기반 placeholder/메타데이터 저장 동작은 그대로 유지됩니다.
- v0.14.8의 프로젝트 입력/분석 흐름과 v0.14.5 이후 검증된 처리 파이프라인은 변경하지 않았습니다.

---

# AstroSirilAssistant v0.14.8 — Project Intake UX + Metadata

이번 버전은 단일 이미지 프로젝트 시작 화면과 입력 흐름을 정리한 UX 업데이트입니다.

- `입력 FITS` → `이미지`로 문구 정리
- 이미지/저장 위치 경로는 읽기 전용으로 변경
- FITS 헤더의 `OBJECT`, `DATE-OBS`/`DATE`를 이용해 대상명/촬영일 자동 입력
- 알려진 대상은 `known_targets.yaml`을 기준으로 대상 종류 자동 분류
- 알 수 없는 대상은 `기타 / 직접입력`으로 표시
- 대상명이 없을 때 `천체 명칭을 입력해주세요.` placeholder 표시
- 프로젝트 시작 순서를 `이미지 분석 → 프로젝트 생성`으로 분리
- 이미지 분석이 완료되어야 프로젝트 생성 버튼 활성화
- 프로젝트 입력 카드에 해상도/비트 깊이/카메라/노출/Gain/필터 요약 표시
- 선택 입력 `저작권` 추가: project.yaml 보관 + Final FITS `COPYRGHT` 헤더 기록
- Siril 연결 확인 결과를 팝업으로 안내
- 버튼 순서: Siril 연결 확인 → SyQon 설치 확인 → 이미지 분석 → 프로젝트 생성
- 상태 영역을 `상태` 라벨과 상태값 두 줄 구조로 변경
- 프로그레스 시간은 `경과` 문구 없이 `MM:SS`만 표시
- Entry의 하얀 corner/focus pixel 제거를 위한 borderless layout 적용
- 세로/가로 스크롤바의 화살표를 제거하고 얇은 thumb 중심 스타일로 변경
- 일반 도움말은 UI 정책 대신 용어/입력값/버튼 동작 중심의 사용 도움말로 교체

기존 Parallax Safe-Band, Before/After 비교, Prism, GHS, StarNet, Recombine, Final Export 처리 흐름은 유지합니다.

> 저작권 입력은 워터마크가 아닙니다. 현재 Working/Final FITS 헤더에 기록하며 TIFF/PNG 메타데이터에는 강제로 삽입하지 않습니다.

---

# AstroSirilAssistant v0.14.7 — Astro Cozy Dark UI

이번 버전은 v0.14.6의 처리 로직을 유지하면서 시각 톤만 부드럽게 다듬은 UI Polish 릴리스입니다.

- 따뜻한 Navy/Charcoal 기반 `Astro Cozy Dark` 팔레트
- 강한 테두리를 제거한 카드형 섹션
- 여백과 행간 확대
- 버튼/입력창 높이와 패딩 확대
- 낮은 채도의 Blue / Green / Red 액센트
- 얇은 프로그레스바와 부드러운 상태 영역
- 실행 중 `중단` 버튼은 muted-red 스타일
- Main GUI와 Sequence GUI에 같은 테마 적용
- Parallax Safe-Band, Before/After, Final Export 등 처리 로직은 변경하지 않음

> Tk/ttk 기반 구조는 그대로 유지합니다. 안정성을 위해 GUI 프레임워크를 교체하지 않고, borderless card + spacing + soft palette 방식으로 둥글고 편안한 인상을 만들었습니다.

---

# AstroSirilAssistant v0.14.6 — Preview Compare + UI Copy Polish

이번 버전은 v0.14.5의 실제 Windows/Siril/SyQon 전체 파이프라인 성공 확인을 기준으로,
처리 로직을 크게 바꾸지 않고 미리보기 비교와 화면 문구를 정리한 UX 업데이트입니다.

- Parallax 빠른 미리보기: `Before · SPCC` / `After · Parallax` 좌우 동시 비교
- Before에서 계산한 하나의 표시 Stretch를 Before/After 양쪽에 동일 적용
- 비교용 Stretch는 표시 전용이며 Linear FITS는 변경하지 않음
- 상단 `현재 단계 : 한 줄 설명` / `다음 작업 : 단계명`을 중심으로 중복 설명 제거
- 헤더, 프로젝트 입력, 상태, 처리 설정, 완료/Export 문구 간결화
- 고정 구현 정보와 반복 안내 문구는 화면에서 제거하고 도움말/상세 로그에 유지
- Main GUI와 Sequence GUI의 공통 문구 스타일 정리

v0.14.5의 Safe-Band Parallax 전체 처리, 중단 버튼, 실시간 로그, Candidate 승인 방식은 그대로 유지합니다.

---

# AstroSirilAssistant v0.14.5 — SyQon Full Safe-Band Hotfix

Parallax 빠른 미리보기는 정상인데 큰 전체 RGB32 이미지에서 `Python module is up-to-date`
이후 진행되지 않는 Windows/Siril Python bridge 패턴을 우회합니다.

전체 이미지가 안전 임계값을 넘으면 자동으로 원본 픽셀 스케일의 겹침 band로 나누어
동일한 Parallax 설정을 적용하고, overlap을 feather 결합한 뒤 원본 크기의 Linear FITS로
복원합니다. 사용자는 기존과 동일하게 `전체 처리 + 결과 확인` 후 `결과 승인`하면 됩니다.

기본값: 32 MiB 안전 payload / 192px overlap / startup watchdog 30초.

---

# AstroSirilAssistant v0.14.5 — Restoration Full-Run Reliability

이번 패치는 실제 Parallax 테스트 로그를 바탕으로 전체 처리 흐름을 수정합니다.

- `현재 단계 : 한 줄 설명` / `다음 작업 : 단계명` 고정 표시
- Parallax `전체 처리 + 결과 확인` 결과를 그대로 `결과 승인`하여 재계산 제거
- FULL SyQon 시작 watchdog 기본 90초
- 홀수 이미지 크기용 even-geometry guard + 결과 원본 크기 복원
- 기존 빠른 미리보기 / 실시간 로그 / 중단 버튼 유지

---

# AstroSirilAssistant v0.14.3 — Fast Preview / Cancel / Project UX

이번 업데이트:

- 새 프로젝트 폴더: `Auto_<대상>_<촬영일>`
- 중복 프로젝트 팝업: `기존 프로젝트 열기 / 새 프로젝트 만들기 / 취소`
- 기존 `<대상>_<촬영일>_Auto` 프로젝트 호환 유지
- Parallax `빠른 미리보기` (기본 중앙 1536×1536, 원본 픽셀 스케일 유지)
- Parallax `전체 미리보기` 분리
- 실제 적용 전 동일 설정의 전체 미리보기 필수
- Siril/SyQon 실시간 로그 스트리밍
- Progress 실행 중 `중단` 버튼
- Windows에서 Siril 하위 프로세스까지 종료 요청
- 중단/실패한 Preview temp 결과 재사용 방지
- Sequence GUI에도 동일한 중단 기능 적용

최종 산출물 파일명 `M31_final_Auto.*` 규칙은 변경하지 않습니다.

---

# AstroSirilAssistant v0.14.2 — Project Collision UX Hotfix

동일한 `대상명 + 촬영일` 프로젝트가 이미 있을 때 더 이상 일반 오류로 끝나지 않습니다.

GUI가 선택지를 표시합니다.

- **예**: 기존 프로젝트 열기
- **아니오**: 새 번호 프로젝트 생성
- **취소**: 중단

새 프로젝트 예:

`M31_2026-09-30_02_Auto`

기존 프로젝트는 절대 덮어쓰거나 삭제하지 않습니다.

v0.14.1 Windows BAT 수정, v0.14.0 Parallax/Prism 및 Astro Graphite UI는 그대로 포함합니다.

---

# AstroSirilAssistant v0.14.1 — Windows BAT Launcher Hotfix

v0.14.0에서 일부 Windows `cmd.exe` 환경이 BAT launcher를 잘못 해석하는 문제를 수정했습니다.

- `run_gui.bat`: Windows-safe ASCII + CRLF standalone launcher
- `run_sequence_gui.bat`: 동일 정책 적용
- `.venv\Scripts\python.exe` 우선
- 없으면 `py.exe -3`
- Python 미설치 / 비정상 종료 시 오류창 유지
- `install_windows.bat`, `run_cli.bat`도 CRLF로 정규화

v0.14.0의 Parallax / Prism / Astro Graphite UI 기능은 그대로 유지됩니다.

---

# AstroSirilAssistant v0.14.0 — Manual-inspired SyQon + Astro Graphite UI

이번 버전의 핵심 전제:

**이전에 수동으로 사용하던 Parallax / Prism 처리 흐름을 가능한 한 그대로 반자동화한다.**

새 Single Image 기본 흐름:

`Gradient → SPCC → Parallax → Prism → GHS → StarNet → Starless → Stars → Recombine → Final / Export`

## 핵심 변경
- Restoration 기본 엔진: **SyQon Parallax Nano**
- Denoise 기본 엔진: **SyQon Prism Mini**
- 기존 Siril RL / Siril Denoise는 Fallback으로 유지
- Siril `pyscript`를 통해 설치된 SyQon Python script를 직접 호출
- 새 프로젝트의 Linear 순서를 **Parallax → Prism**으로 변경
- v0.6~v0.13 진행 프로젝트 호환 유지
- `SyQon 설치 확인` 버튼
- Astro Graphite Dark UI
- Main/Sequence GUI에 동일한 반응형 Scroll / Log Pane / Progress / Error UX 적용
- `run_gui.bat` / `run_sequence_gui.bat` 공통 launcher 사용

## 참고
v0.14.0에서 SyQon 연동 범위는 우선 **Parallax + Prism**입니다.
Star separation은 현재 검증된 StarNet.py 경로를 계속 사용합니다.

---

# AstroSirilAssistant v0.13.1 — Final Result Folder Hotfix

Final / Export 성공 후 아래 조건을 만족할 때만:

`[최종 결과 폴더 열기]`

버튼을 표시합니다.

- State = EXPORTED
- finalization.exported = true
- FITS / TIFF / PNG 중 실제 생성된 Export 파일이 1개 이상 존재

버튼을 누르면 프로젝트의 `output` 폴더를 엽니다.

---

# AstroSirilAssistant v0.13.1 — Final / Export

기본 Deep-sky 파이프라인:

`Gradient → SPCC → Denoise → Deblur → GHS → StarNet → Starless → Stars → Recombine → Final / Export`

## v0.13 핵심
- Final 미리보기 + highlight clipping 분석
- Working Final 32-bit FITS 자동 저장
- 선택적 32-bit FITS Export
- 선택적 16-bit TIFF Export
- 선택적 16-bit PNG Export
- TIFF Deflate 무손실 압축
- FITS CHECKSUM / DATASUM 옵션
- Final 이름 `_Auto` 규칙 적용
- 선택한 출력 파일 실제 존재 검증 후에만 State = EXPORTED
- Output 폴더 열기 버튼
- 기본 파이프라인 완료 화면

최종 예:
- `working\12_final\M31_12_final.fits`
- `output\fits\M31_final_Auto.fits`
- `output\tiff\M31_final_Auto.tif`
- `output\png\M31_final_Auto.png`

주의:
v0.13.0은 ICC/sRGB 색공간 변환을 강제로 수행하지 않습니다.

---

# AstroSirilAssistant v0.13.1 — Pixel Math Recombine

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

# AstroSirilAssistant v0.13.1 — Dynamic UI Hotfix

v0.11.0의 Stars Processing 기능은 그대로 유지합니다.

이번 Hotfix:
- 짧은 페이지에서 마우스휠을 움직이면 UI가 위/아래로 크게 밀리던 문제 수정
- 화면보다 내용이 짧을 때 Scroll 자체를 비활성화
- 실제 overflow에서만 일정한 픽셀 단위로 Scroll
- `상세 로그 보기`를 눌러도 Log Pane이 1px 높이로 남아 보이지 않던 문제 수정
- Log Pane을 열 때 geometry 완료 후 sash 위치를 여러 번 안정화
- 사용자가 조절한 로그 높이 비율을 다시 열 때 복원

---

# AstroSirilAssistant v0.13.1 — Stars Processing + Dynamic UI

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

# AstroSirilAssistant v0.13.1 — Starless Processing + Target-aware Recommendations

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

# AstroSirilAssistant v0.13.1 — StarNet / 별 분리

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

# AstroSirilAssistant v0.13.1 — GHS Stretch

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

# AstroSirilAssistant v0.13.1 — Deblur / Deconvolution

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

# AstroSirilAssistant v0.13.1 — 작업 상태 UX + Denoise

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

# AstroSirilAssistant v0.13.1 — Help UI 정리 + SPCC Hotfix

- 파라미터별 `?` 버튼 → 섹션당 `도움말 ?` 1개로 정리
- Tooltip은 항목명 Label에만 표시
- 상세 도움말 팝업은 항상 1개만 유지
- Siril 1.4.4 Windows의 `-bgtol=-2.8,2` 오류 우회

---

# AstroSirilAssistant v0.13.1 — SPCC + Common Help System

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

# AstroSirilAssistant v0.13.1 — Interactive single-FITS + Gradient

v0.4.2에서는 `run_gui.bat`에 실제 단계 선택 버튼과 Gradient 미리보기/적용 기능이 추가되었습니다.

### 단일 스택 FITS 흐름

`분석 → [스택된 Linear] → Gradient 값 확인 → [미리보기] → [승인 후 적용] → M31_03_gradient.fits`

미리보기는 표시용 AutoStretch JPEG를 만들지만 실제 작업 FITS는 Linear 상태를 유지합니다.

---

# AstroSirilAssistant v0.13.1 — Siril 1.4.4 script hotfix

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
