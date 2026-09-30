# v0.15.1 — CR3/RAW 변환 경로 수정

## 수정 원인

Siril 1.4.4의 `convertraw`는 Siril **내부 작업 폴더**에 있는 RAW만 검색합니다.
이전 버전은 CR3를 전용 임시 폴더로 복사하고 파이썬 subprocess의 `cwd`만
변경했습니다. Siril이 GUI에서 저장된 작업 폴더(예: 사용자 Pictures 폴더)를
자체적으로 불러올 경우, 변환 명령이 해당 Pictures 폴더를 검색하고
`No RAW files were found for conversion` 오류를 냈습니다.

## v0.15.1 변경

- RAW 전용 임시 폴더에 원본을 복사한 뒤, Siril 스크립트에 명시적인
  `cd "<임시 RAW 폴더>"`를 `convertraw` **앞에** 삽입합니다.
- Windows 공백 경로를 지원하도록 디렉터리 인자를 따옴표로 감쌉니다.
- 로그에 `RAW 변환 폴더`를 명시해 Siril의 디렉터리 전환을 확인할 수 있습니다.
- 전용 임시 폴더에는 선택한 RAW 파일만 위치합니다. 사용자 원본은 그대로 보존됩니다.
- 변환 결과가 생성되지 않으면 실패로 처리하고 불완전한 FITS를 사용하지 않습니다.
- 이 수정은 다중 포맷 **RAW 입력 경로만** 수정합니다. 이미 검증된 FITS 보정,
  Parallax Safe-Band, Prism, Final Export에는 변경이 없습니다.

## 재시험

CR3 선택 → [이미지 분석] → 상세 로그에서 다음 순서를 확인합니다.

1. `RAW 변환 폴더: .../astroauto_raw_.../source`
2. Siril의 `cd` 명령과 작업 디렉터리 전환
3. `convertraw` 실행, 변환 FITS 생성
4. 분석 결과 및 [프로젝트 생성] 활성화

이 개발 환경에서는 Windows Siril/실제 CR3 런타임을 실행할 수 없으므로
실제 CR3 디코딩 성공 여부는 Windows에서 확인이 필요합니다.
