# v0.14.9 UI Focus / Input Polish

## 변경 사항

1. 프로젝트 입력 카드의 Entry를 Windows ttk/clam 필드 요소 대신 borderless native Tk Entry로 렌더링합니다.
2. Combobox field layout에서도 native border를 제거해 모서리 잔여 픽셀을 줄입니다.
3. 비상호작용 영역(배경/Frame/Label/Canvas)을 좌클릭하면 현재 Entry/Text 선택과 키보드 포커스를 해제합니다.
4. 입력값, 프로젝트 상태, 처리 알고리즘은 변경하지 않습니다.
