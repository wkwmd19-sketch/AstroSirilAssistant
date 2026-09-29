# Siril Command Mapping Notes v0.2

## 네이티브 명령으로 우선 연결할 항목

- 입력 FITS 통계: `jsonmetadata`
- 이미지 로드: `load`
- FITS 저장: `save`
- 32-bit 작업 설정: `set32bits`
- 그래디언트 제거: `subsky`
- SPCC: `spcc`
- 딥스카이 정렬: `register`
- 스택: `stack`
- GHS: `ght`
- 채도: `satu`
- Pixel Math: `pm`
- TIFF/PNG 출력: `savetif`, `savepng`

## StarNet

Siril 1.5 계열은 StarNet 처리를 Python script 방식으로 다루는 것을 기준으로 한다.
따라서 v0.2 매핑은 `pyscript StarNet.py`를 진입점으로 정의하고, 세부 옵션은 설치된 스크립트 버전을 런타임에서 읽는 adapter가 담당한다.

## SyQon Parallax / Prism

외부 Python 스크립트이므로 파일명/버전에 의존하는 고정 명령을 스키마에 박지 않는다.
프로그램 시작 시 Siril script 목록에서 실제 스크립트를 탐색하고, 발견된 이름을 runtime adapter에 바인딩한다.

## 왜 Command Adapter를 두는가

Siril 본체 명령은 비교적 안정적이지만, 외부 Python 보정 도구는 버전별 UI/인수 차이가 있을 수 있다.
따라서 논리적 작업 ID와 실제 Siril 명령을 분리한다.

예:

`STARNET` → StarNetAdapter → 현재 설치된 StarNet.py 실행 방식

`SYQON_PRISM` → PrismAdapter → 현재 설치된 Prism script와 옵션 연결
