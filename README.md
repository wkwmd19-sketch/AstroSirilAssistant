# AstroSirilAssistant Schema v0.1

반자동 Siril 천체사진 보정 시스템의 초기 스키마 규격입니다.

## 프로젝트 경로 규칙

기본 루트: `D:\\AstroProjects_Auto\\`

프로젝트 폴더: `{TARGET}_{YYYY-MM-DD}_Auto`

예: `D:\\AstroProjects_Auto\\M31_2026-09-29_Auto\\`

## 파일명 규칙

중간 작업 파일: `{TARGET}_{STEP_NO}_{STEP_NAME}.fits`

최종 파일: `{TARGET}_final_Auto.{ext}`

## 처리 원칙

반자동 기본 모드는 분석 → 추천 → 설명 → 사용자 승인 → Siril 실행 → 자동 저장 → 로그 기록입니다.
이미 완료된 State를 재실행하려면 명시적 사용자 승인이 필요합니다.
Linear/Non-linear 상태를 별도 추적하며, UNKNOWN 판정은 사용자 확인으로 넘깁니다.
