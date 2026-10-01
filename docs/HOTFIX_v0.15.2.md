# v0.15.2 — FITS 이미지 분석 호환성 핫픽스 / 개발 인수인계

## 재현 로그

Canon EOS RP CR3(6264×4180, RGGB, 133.2s, ISO 1600)로 `이미지 분석` 실행 시:

1. Siril 1.4.4 `cd` → `convertraw -debayer` 완료.
2. 3채널 16-bit FITS 및 `analysis_input.fits` 저장 완료.
3. `jsonmetadata` JSON 생성·스크립트 종료 완료.
4. 앱의 `이미지 분석 완료`까지 이어지지 않음. 현재 제공된 로그에는 Python traceback 없음.

출력 FITS Header는 `BITPIX=16`, `BZERO=32768`, `BSCALE=1`이며,
`analyze_input_file()`의 다음 순서에서 `analyze_pixels()`가 Siril 메타데이터 이후 호출됩니다.

## 수정

- `astroauto/fits_analysis.py`의 `analyze_pixels()` 및 `read_header_summary()`에서
  스케일링 대상 FITS를 안전하게 읽도록 `memmap=False` 적용.
- 대형 RGB 입력의 샘플링을 float64 변환 전에 수행해 순간 메모리 부담을 완화.
- BZERO/BSCALE 16-bit RGB FITS 및 기존 32-bit float/mono 경로에 대한 회귀 테스트 추가.
- 새 채팅에서도 기준이 보존되도록 9개 개발 인수인계 문서를 `docs/handoff/`에 추가.

## 변경하지 않은 범위

Siril RAW decoding·Debayer·격리 임시 폴더, 원본 보존 및 정규화 경로,
Calibration/Gradient/SPCC/Parallax Safe-Band/Prism/GHS/StarNet/Final Export의
기존 작업·명령 계약은 이번 핫픽스에서 수정하지 않았습니다.

## 검증 경계 및 후속 점검

- 현 패치의 **Windows/Siril/Canon CR3 실사용 성공은 아직 확인하지 않았습니다**.
- `set32bits` 처리에도 Siril 로그에 16-bit FITS가 저장된 사실이 있으므로
  원래 목표한 32-bit float 출력과 일치하는지 별도 확인해야 합니다.
- `jsonmetadata` 통계 채널명에 NUL 문자가 보이는 현상은 별도 Siril/JSON 문제로 분리해 추적합니다.
- Windows에서 `이미지 분석 → 프로젝트 생성` 성공 및 FITS Header·RGB 방향·원본 무결성을 확인합니다.
- Git 커밋/푸시는 사용자 요청에 따라 보류합니다.
