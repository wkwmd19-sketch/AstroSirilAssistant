# Siril Version Compatibility

v0.3 기준:

- 기본 지원 목표: Siril 1.4.x
- 현재 안정판 기준: Siril 1.4.4
- 1.5 개발 계열: 명령 호환성을 런타임에서 확인하며 허용
- 1.3 이하: 지원 대상 아님

`jsonmetadata`는 Siril 1.4.4 안정 문서에서 Scriptable 명령으로 확인됩니다.

Siril CLI는 Windows에서 일반적으로 다음 위치 중 하나에 있습니다.

`C:\Program Files\SiriL\bin\siril-cli.exe`

자동 탐색 실패 시 `config/app.yaml`의 `siril.executable`에 직접 지정합니다.
