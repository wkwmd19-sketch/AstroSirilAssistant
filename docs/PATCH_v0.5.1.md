# v0.5.1 Hotfix

## Help UI
- 파라미터마다 있던 `?` 버튼을 제거했습니다.
- Gradient / SPCC 섹션마다 `도움말 ?` 버튼 하나만 표시합니다.
- 짧은 Tooltip은 정확한 항목명(Label)에 마우스를 올렸을 때만 표시합니다.
- Entry / ComboBox / 공란에는 Tooltip을 표시하지 않습니다.
- 상세 도움말 창은 하나만 존재하며, 버튼을 여러 번 눌러도 기존 창 내용을 갱신하고 앞으로 가져옵니다.

## SPCC `-bgtol` 오류
Siril 1.4.4 문서상 Background Tolerance 기본값은 `-2.8 / +2.0`입니다.

테스트된 Windows CLI에서는 기본값을 명시적으로:
`-bgtol=-2.8,2`
형태로 넘겼을 때 `invalid argument` 오류가 발생했습니다.

v0.5.1은 기본값을 사용할 때 `-bgtol` 옵션 자체를 생략해
Siril의 내장 기본값(-2.8 / +2.0)을 사용합니다.

사용자가 기본값이 아닌 값을 직접 입력하면 문서의 `-bgtol=lower,upper`
형식을 따르되 전체 인수를 따옴표로 묶어 전달합니다.

## SPCC list parser
- Siril 로그에 날짜/틱 prefix가 붙는 경우에도 Sensor/Filter 이름만 정확히 추출하도록 보완했습니다.
