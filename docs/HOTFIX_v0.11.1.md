# v0.11.1 Dynamic UI Hotfix

사용자 화면 녹화에서 두 문제를 확인했습니다.

## 1. 짧은 페이지가 마우스 휠로 이동하며 큰 빈 공간 발생

원인:
- Canvas viewport가 실제 content보다 큰 경우에도 `yview_scroll`과
  `_ensure_action_visible()`가 실행되었습니다.
- 기본 Canvas scroll unit이 viewport 크기에 비례해 한 번에 크게 이동했습니다.

수정:
- content가 viewport보다 짧으면 항상 y=0으로 고정
- 실제 overflow가 있을 때만 Scrollbar 활성화
- `yscrollincrement=24`
- Windows wheel 1 notch ≈ 48px
- 자동 task scroll도 overflow일 때만 실행
- 전역 wheel binding은 workflow 내부 포인터일 때만 동작

## 2. 상세 로그 버튼은 토글되지만 로그가 보이지 않음

원인:
- v0.11.0에서 second pane을 추가한 직후 `after_idle`로 sash를 배치했으나,
  일부 Windows/Tk geometry 순서에서는 이후 layout pass가 다시 sash를
  맨 아래로 밀어 log pane 높이가 약 1px로 남을 수 있었습니다.

수정:
- pane 추가 직후 `update_idletasks()`
- 즉시 sash 배치
- 40ms / 140ms 후 재배치
- 로그 닫기 전 사용자가 조정한 sash 비율 저장
- 다시 열 때 마지막 비율 복원
- pane add/forget 오류는 더 이상 조용히 무시하지 않고 오류 팝업 표시

## Regression test

Xvfb/Tk로 실제 위젯 geometry를 검사:
- short page wheel: top 유지
- open log: 2 panes
- log height > 100px
- close log: 1 pane
