# Git 관리 안내

## 압축파일을 받은 뒤

압축을 풀고 `AstroSirilAssistant` 폴더를 터미널에서 엽니다.
숨겨진 `.git` 폴더가 이력을 담고 있으므로 함께 유지합니다.
현재 `main`은 v0.14.1 소스와 Git 관리 문서로 구성됩니다.

```shell
git status
git log --oneline --decorate --reverse
git tag --list --sort=version:refname
```

## 변경 내용 비교

```shell
git diff --stat v0.13.1 v0.14.1
git diff v0.14.0 v0.14.1 -- run_gui.bat
```

## 예전 버전을 별도 폴더로 열기

현재 작업 폴더를 유지하면서 원하는 버전을 비교할 수 있습니다.
아래 명령은 예시로 v0.8.0을 옆 폴더에 엽니다.

```shell
git worktree add --detach ../AstroSirilAssistant-v0.8.0 v0.8.0
```

예전 버전에서 수정까지 이어가려면 별도 브랜치를 만듭니다.

```shell
git worktree add -b fix/from-v0.8.0 ../AstroSirilAssistant-v0.8.0-fix v0.8.0
```

태그의 원본 파일만 ZIP으로 내보낼 수도 있습니다.
이 ZIP은 실행 파일 묶음이며 Git 이력은 포함하지 않습니다.

```shell
git archive --format=zip --prefix=AstroSirilAssistant-v0.8.0/ --output=../AstroSirilAssistant-v0.8.0.zip v0.8.0
```

## 앞으로 수정할 때

새 커밋 전에 Git 작성자 이름과 이메일을 본인 정보로 설정합니다.
이번 가져오기 커밋의 작성자는 `AstroSirilAssistant Archive Import`이며,
과거 실제 작성자나 개발 시각을 추정하지 않았습니다.

```shell
git switch -c feature/next-change
```

파일 수정 후 필요한 검증을 수행하고 변경분을 검토합니다.

```shell
git status
git diff
git add .
git diff --cached
git commit -m "fix: 수정 내용 요약"
```

검증을 마친 변경을 main에 반영합니다.

```shell
git switch main
git merge --ff-only feature/next-change
```

새 버전을 배포할 때 소스의 버전 표기와 CHANGELOG를 먼저 갱신해 커밋하고,
그 커밋에 새 주석 태그를 붙입니다. 이미 배포한 태그는 이동하지 않습니다.

## GitHub에 전체 이력 업로드

현재 원격 저장소는 연결되어 있지 않습니다.
빈 GitHub 저장소를 준비하고, 아래 명령의 `YOUR_ACCOUNT`를 실제 계정으로 바꿉니다.
원하는 저장소 이름이 다르면 이름도 변경합니다.

```shell
git remote add origin https://github.com/YOUR_ACCOUNT/AstroSirilAssistant.git
git push -u origin main
git push origin --tags
```

이미 origin이 설정되어 있으면 `git remote -v`로 목적지를 먼저 확인하고
기존 원격 설정을 임의로 덮어쓰지 않습니다. 원격에 기존 커밋이 있으면
강제 push하지 말고 이력을 먼저 비교합니다.

GitHub 웹 화면에서 파일만 업로드하면 이 21개 버전의 커밋·태그는 전달되지 않습니다.
위 push 명령으로 저장소 이력을 올려야 합니다.

이후 작업을 다른 폴더나 PC에서 이어갈 때는 원격 저장소를 clone합니다.
원격 연결 전에는 `.git`까지 포함한 전체 폴더를 보관합니다.

## 보존·검증 범위

- 보관된 ZIP 21개를 버전 순서대로 가져왔습니다.
- 태그에는 ZIP의 파일 바이트와 실행 권한을 그대로 보존했습니다.
- 최상위 버전 폴더 제거 외의 소스 정리·수정은 수행하지 않았습니다.
- Git 커밋 시각은 가져오기 시각입니다. 원본 파일 기록 시각은 해시 기록에 별도로 남았습니다.
- 최신 BAT 파일의 CRLF도 보존했습니다.
- Siril, SyQon, Windows GUI의 실제 실행은 이번 버전 관리 작업의 검증 범위에 포함하지 않았습니다.
