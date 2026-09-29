# AstroSirilAssistant v0.3 MVP

Siril을 중심으로 천체사진을 **반자동 분석/보정**하기 위한 첫 실행형 MVP입니다.

현재 v0.3에서 실제로 동작하는 범위:

1. `D:\AstroProjects_Auto` 프로젝트 생성
2. 프로젝트명/최종 결과물 `_Auto` 규칙 적용
3. FITS 파일 자동 탐색
4. Siril CLI 자동 탐색 및 버전 확인
5. Siril `jsonmetadata` 호출
6. Astropy/Numpy로 FITS 히스토그램/통계 자동 계산
7. FITS HISTORY 기반 Linear/Non-linear 보수적 판정
8. `project.yaml` 상태 자동 업데이트
9. 다음 작업 + 요약 설명 + 목적 + 주의사항 + 완료기준 출력
10. 분석/명령 로그 저장
11. 간단한 Windows GUI 제공

아직 v0.3에서 **실제 적용 버튼이 활성화되지 않은 작업**:

- Gradient Correction 실행
- SPCC 실행
- GHS 적용
- StarNet 실행
- Pixel Math 재합성
- RAW 서브프레임 Calibration/Registration/Stacking
- 은하수 지상/하늘 움직임 자동판별

위 작업들은 스키마와 command adapter를 유지하면서 v0.4 이후 차례로 실제 실행 기능을 붙이는 구조입니다.

## 중요: Siril 버전

2026-09 기준 Siril의 최신 안정판은 1.4.4입니다.
이 MVP는 안정판 1.4.x를 우선 대상으로 하며 1.5 개발 계열도 버전 검출 후 허용하도록 작성되어 있습니다.

## 설치

Python 3.11 또는 3.12 권장.

`install_windows.bat`을 실행하면 `.venv`를 만들고 필요한 패키지를 설치합니다.

## GUI 실행

`run_gui.bat`

GUI에서:

1. 원본/스택 FITS 선택
2. 대상명 입력 (예: M31)
3. 대상 종류 선택
4. 촬영일 입력
5. `프로젝트 생성 + 분석` 클릭

프로젝트 예:

`D:\AstroProjects_Auto\M31_2026-09-29_Auto`

## CLI

환경 진단:

`python app.py doctor`

새 프로젝트 생성:

`python app.py new --input "D:\photo\M31.fits" --target M31 --date 2026-09-29 --category GALAXY`

기존 프로젝트 분석:

`python app.py analyze "D:\AstroProjects_Auto\M31_2026-09-29_Auto"`

상태 확인:

`python app.py status "D:\AstroProjects_Auto\M31_2026-09-29_Auto"`

## 안전 원칙

Linear/Non-linear 판정이 확실하지 않으면 `UNKNOWN`으로 남깁니다.
UNKNOWN 상태에서 GHS 같은 큰 변경을 자동 적용하는 구조는 사용하지 않습니다.
