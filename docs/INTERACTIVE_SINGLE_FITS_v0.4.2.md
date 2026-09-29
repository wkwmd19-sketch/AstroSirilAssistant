# Interactive Single-FITS Workflow v0.4.2

`run_gui.bat`의 단일 FITS 처리 경로가 실제 반자동 UI로 확장되었습니다.

## 입력 단계 버튼

분석 후 사용자가 바로 선택할 수 있습니다.

- 스택된 Linear
- 스택된 Non-linear
- 개별 Light 1장
- 잘 모르겠음

`스택된 Linear`을 선택하면 Calibration / Registration / Stack을 다시 하지 않고
바로 Gradient Correction 단계로 이동합니다.

## Gradient Correction

Siril 1.4.4의 scriptable `subsky` RBF 방식을 사용합니다.

시작값:

- Samples = 20
- Tolerance = 1.0
- Smooth = 0.5
- Dither = Off

이 값은 Siril 기본값을 기반으로 한 **시작값**이며, 천체에 맞춰 사용자가 수정할 수 있습니다.

## 안전장치

실제 적용 전에 현재 파라미터와 동일한 값으로 미리보기를 한 번 생성해야 합니다.

미리보기 흐름:

1. 원본 Linear FITS 로드
2. `subsky -rbf` 적용
3. Linear Gradient preview FITS 저장
4. 표시용으로만 `autostretch -linked`
5. JPEG 저장 및 기본 이미지 뷰어로 열기

AutoStretch는 JPEG 미리보기용 데이터에만 적용됩니다.
실제 Gradient 결과 FITS는 Linear 상태를 유지합니다.

## 실제 적용 결과

예:

`working\03_gradient\M31_03_gradient.fits`

적용 후 프로젝트 상태:

`GRADIENT_CORRECTED`

다음 작업:

`SPCC Color Calibration`
