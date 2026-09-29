# AstroSirilAssistant

Siril 기반 천체사진 반자동 보정 도구입니다. 현재 작업 기준은 **v0.14.1**입니다.

보관된 원본 ZIP 21개를 버전 순서대로 Git 커밋과 주석 태그로 가져왔습니다.
`v0.1`, `v0.2`는 스키마 단계이며, `v0.3`부터 실행형 프로그램입니다.

## 실행과 문서

- 프로그램 설치·사용: [README_KO.md](README_KO.md)
- 전체 버전별 변경 내용: [CHANGELOG.md](CHANGELOG.md)
- 버전 비교·복원·GitHub 업로드: [Git 관리 안내](docs/GIT_WORKFLOW_KO.md)
- 원본 ZIP 및 파일별 SHA-256: [가져오기 기록](docs/git/ARCHIVE_IMPORT.json)

Windows에서 의존성을 설치한 후, 단일 FITS 보정은 `run_gui.bat`,
Light/Dark/Flat 시퀀스 전처리는 `run_sequence_gui.bat`으로 실행합니다.

## 이력의 의미

`v0.1`부터 `v0.14.1`까지 각 태그는 해당 원본 ZIP의 파일을 그대로 보존합니다.
버전명이 붙은 ZIP 최상위 폴더만 제거해 동일 경로에서 변경점을 비교할 수 있게 했습니다.
ZIP에 없는 중간 개발 이력은 생성하지 않았습니다. Git 커밋 시각은 이번 가져오기 시각이며,
실제 과거 개발 시각으로 소급하지 않았습니다.

`main`에는 최신 원본 소스와 Git 관리 문서·설정이 들어 있습니다.
Git 관리 작업은 별도 마지막 커밋으로 기록했습니다. 기존 프로그램 소스는 수정하지 않았습니다.
프로그램 실행 검증이 아니라, 모든 태그의 파일 목록·바이트·실행 권한과 원본의 일치 여부를 검증했습니다.

v0.14.0 ZIP에 들어 있던 Python 캐시는 그 태그에 원본대로 보존되어 있습니다.
최신 작업 트리에는 없으며, 이후 생성되는 캐시는 `.gitignore`로 제외됩니다.
BAT의 CRLF를 포함한 원본 바이트 보존을 위해 `.gitattributes`에서 자동 줄바꿈 변환을 비활성화했습니다.

GitHub 저장소: [wkwmd19-sketch/AstroSirilAssistant](https://github.com/wkwmd19-sketch/AstroSirilAssistant)

GitHub 저장소 생성 시 만들어진 초기 README 커밋도 병합해 보존했습니다.
다른 PC에서는 이 저장소를 clone하면 버전 이력을 함께 가져올 수 있습니다.
폴더를 직접 복사할 때는 `.git`까지 포함해야 커밋과 태그가 유지됩니다.
GitHub 웹 파일 업로드만으로는 이력이 이전되지 않습니다.
