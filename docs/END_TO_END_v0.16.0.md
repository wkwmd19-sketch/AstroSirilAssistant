# v0.16.0 단일 이미지 후처리 완성 경로

## 처리 흐름

1. 이미지 분석 → 프로젝트 생성 → 캘리브레이션 검사 또는 사용자 승인하 생략.
2. Gradient(RBF 배경 추출): 미리보기 → 승인 후 적용 또는 사용자 승인하 생략.
3. SPCC: Plate Solve 및 색상 보정 → 적용 또는 사용자 승인하 생략.
4. Restoration / Deblur: SyQon Parallax 또는 Siril Native RL; 미리보기·실행·생략.
5. Denoise: SyQon Prism 또는 Siril Native; 미리보기·실행·생략.
6. GHS Stretch: 실제 Non-linear 데이터 생성. 최소 한 번 적용 후 결과 확인 및 추가 Pass 선택.
7. StarNet: 실행하면 Starless와 Stars를 각각 조정하고 Pixel Math로 재합성. 실행하지 않으면 원래 Non-linear 이미지를 Final로 직접 전달.
8. Final / Export: 최종 JPEG 미리보기 확인 및 32비트 FITS/16비트 TIFF/PNG 선택 저장.

## 데이터 안전과 상태

- 생략은 사용자 확인 필수, 실제 이미지 픽셀/원본 파일 변경 없음.
- Gradient 생략 상태는 GRADIENT_SKIPPED, SPCC 생략은 `color_calibration.skipped=true` 및 `image_state.color_calibrated=false`로 구분.
- StarNet 생략 후 EXPORT_READY를 통해 최종 저장. 기존 버전의 POST_STARNET_SKIPPED는 재열기 시 이 상태로 안전하게 마이그레이션.
- Restoration 및 Denoise를 둘 다 생략해도 Legacy 순서로 되돌아가지 않고 GHS로 진행.
- GHS는 Non-linear 최종 이미지 필수이므로 Linear 입력에서는 무조건 건너뛰기 불가.
- 기존 프로젝트 폴더 규칙 `Auto_대상명_촬영일` 및 출력 규칙 `대상명_final_Auto` 보존.

## 테스트 범위 및 제한

- 통합 상태 테스트는 임시 FITS 경로를 사용해 단계·상태·원본 보존을 검증.
- Siril, SyQon, CUDA, Plate Solve 카탈로그/인터넷 연결과 실제 Canon CR3 전 단계 실행은 Windows 실기기 확인 필요.
- 완전 무인 자동 보정은 아니며, 각 단계 실제 적용 시 확인/미리보기 기반 반자동 워크플로를 유지.
- Dark/Flat 마스터 작성 및 원본 CFA 캘리브레이션은 이 단일 RGB 후처리 GUI의 범위 밖이며, 시퀀스 워크플로를 사용.
