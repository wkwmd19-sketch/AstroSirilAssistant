# Common Help System v0.1

모든 주요 처리 파라미터는 같은 도움말 구조를 사용합니다.

## 1. Short Tooltip
마우스 오버 또는 키보드 포커스 시 약 450ms 후 짧은 설명을 표시합니다.

내용:
- 항목이 무엇인지
- 값 변화 방향의 핵심

## 2. `?` Detailed Help
각 주요 항목 옆 `?` 버튼을 누르면 상세 도움말 창을 엽니다.

내용:
- 정의
- 기본 시작값
- 값을 높이면 / 낮추면
- 주의사항
- 현재 워크플로에서의 의미

## 데이터
`help/topics.yaml`

향후 SPCC / GHS / StarNet / Pixel Math / Calibration / Stack 품질지표까지 동일 구조로 확장합니다.
