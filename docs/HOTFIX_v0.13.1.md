# v0.13.1 Final Result Folder Hotfix

Final / Export 완료 후 `최종 결과 폴더 열기` 버튼을 조건부로 표시합니다.

## 표시 조건

버튼은 다음 조건을 모두 만족할 때만 노출됩니다.

1. `project.current_state == EXPORTED`
2. `project.finalization.exported == true`
3. 실제 사용자용 Export 파일이 최소 1개 이상 존재
   - FITS
   - TIFF
   - PNG

내부 Working Final FITS만 존재하는 경우에는 버튼을 표시하지 않습니다.

## 동작

`최종 결과 폴더 열기`를 누르면 프로젝트의:

`output\`

폴더를 Windows 탐색기로 엽니다.

프로젝트를 나중에 다시 열더라도 위 조건을 다시 검사해 버튼 표시 여부를 결정합니다.
