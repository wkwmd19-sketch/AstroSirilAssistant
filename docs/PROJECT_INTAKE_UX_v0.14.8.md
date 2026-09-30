# v0.14.8 Project Intake UX

## 목표

프로젝트 생성 전에 입력 이미지를 먼저 확인하고 분석하도록 흐름을 분리한다.
프로젝트 식별 정보는 FITS 헤더를 우선 사용하되 사용자가 최종 확인/수정할 수 있다.

## 시작 흐름

1. 이미지 선택
2. FITS 헤더 빠른 읽기
3. OBJECT / DATE-OBS 자동 입력
4. 알려진 대상 종류 자동 분류
5. 이미지 분석
6. 분석 성공 후 프로젝트 생성 활성화
7. 분석 결과를 새 프로젝트에 연결하고 기존 보정 파이프라인 시작

`프로젝트 생성`은 분석을 다시 실행하지 않는다.
분석 결과가 현재 선택 이미지와 일치할 때만 생성할 수 있다.

## 프로젝트 입력 UI

- 이미지: 읽기 전용 경로 + 찾기
- 대상명: 자동 입력 또는 직접 입력
- 촬영일: 자동 입력 또는 직접 입력
- 대상 종류: 자동 분류 또는 직접 선택
- 저작권: 선택 입력
- 저장 위치: 읽기 전용 경로 + 폴더 선택
- 이미지 정보: 해상도 / BITPIX / 장비 / 노출 / Gain / Filter / 분석 후 Linearity

## Copyright

`metadata.copyright`로 project.yaml에 저장한다.
Final Export 시 Working FITS 및 선택한 Final FITS에 `COPYRGHT` 헤더를 기록한다.
TIFF / PNG에 별도 메타데이터를 강제 삽입하거나 화면 워터마크를 그리지는 않는다.

## UI Polish

- 프로젝트 입력 LabelFrame을 내부 제목이 있는 Card로 변경
- 필드 라벨은 카드와 동일한 배경으로 표시
- Entry border/focus corner artifact 제거
- Scrollbar arrow 제거 및 slim thumb 적용
- 상태: 제목/값을 두 줄로 분리
- elapsed: `MM:SS`만 표시
- 일반 도움말: 개발/정책 설명 대신 사용자 용어/기능 설명
