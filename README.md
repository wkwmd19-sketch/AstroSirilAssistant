# AstroSirilAssistant

Siril 기반 천체사진 반자동 보정 도구입니다. 현재 작업 기준은 **v0.16.0**입니다.

보관된 원본 ZIP 34개를 버전 순서대로 Git 커밋과 주석 태그로 가져왔습니다.
`v0.1`, `v0.2`는 스키마 단계이며, `v0.3`부터 실행형 프로그램입니다.

## 실행과 문서

- 프로그램 설치·사용: [README_KO.md](README_KO.md)
- 전체 버전별 변경 내용: [CHANGELOG.md](CHANGELOG.md)
- 버전 비교·복원·GitHub 업로드: [Git 관리 안내](docs/GIT_WORKFLOW_KO.md)
- 원본 ZIP 및 파일별 SHA-256: [가져오기 기록](docs/git/ARCHIVE_IMPORT.json)

Windows에서 의존성을 설치한 후, 단일 이미지 보정은 `run_gui.bat`,
Light/Dark/Flat 시퀀스 전처리는 `run_sequence_gui.bat`으로 실행합니다.

## 이력의 의미

`v0.1`부터 `v0.16.0`까지 각 태그는 해당 원본 ZIP의 파일을 그대로 보존합니다.
버전명이 붙은 ZIP 최상위 폴더만 제거해 동일 경로에서 변경점을 비교할 수 있게 했습니다.
ZIP에 없는 중간 개발 이력은 생성하지 않았습니다. Git 커밋 시각은 이번 가져오기 시각이며,
실제 과거 개발 시각으로 소급하지 않았습니다.

`main`에는 v0.16.0 전체 배포본과 Git 관리 문서·설정이 들어 있습니다.
v0.15.2는 FITS 분석 호환성·메모리 개선, v0.15.3은 캘리브레이션 프레임 검사,
v0.16.0은 단일 이미지 후처리 단계 생략·연결과 최종 내보내기를 포함합니다.
이전 `v0.15.1-fits-hotfix` 태그와 [핫픽스 기록](docs/HOTFIX_v0.15.1_FITS_MEMMAP.md)도 유지합니다.

모든 원본 버전 태그의 파일 목록·바이트·실행 권한을 ZIP과 대조했습니다.
이번 추가 3개 버전의 Python 구문 검사와 최신 소스의 기존 의존성 없는 회귀 검사 6개를 통과했습니다.
Astropy FITS 입출력 및 실제 Windows/Siril/SyQon 실행은 이번 Git 반영 작업에서 확인하지 않았습니다.
원본 README/MANIFEST의 검증 문구와 Git 미반영 문구는 배포 당시 기록으로 보존합니다.
v0.15.4는 v0.16.0 문서에 언급되지만 별도 원본 ZIP을 찾지 못해 태그를 만들지 않았습니다.

v0.14.0 ZIP에 들어 있던 Python 캐시는 그 태그에 원본대로 보존되어 있습니다.
최신 작업 트리에는 없으며, 이후 생성되는 캐시는 `.gitignore`로 제외됩니다.
BAT의 CRLF를 포함한 원본 바이트 보존을 위해 `.gitattributes`에서 자동 줄바꿈 변환을 비활성화했습니다.

GitHub 저장소: [wkwmd19-sketch/AstroSirilAssistant](https://github.com/wkwmd19-sketch/AstroSirilAssistant)

GitHub 저장소 생성 시 만들어진 초기 README 커밋도 병합해 보존했습니다.
다른 PC에서는 이 저장소를 clone하면 버전 이력을 함께 가져올 수 있습니다.
폴더를 직접 복사할 때는 `.git`까지 포함해야 커밋과 태그가 유지됩니다.
GitHub 웹 파일 업로드만으로는 이력이 이전되지 않습니다.
