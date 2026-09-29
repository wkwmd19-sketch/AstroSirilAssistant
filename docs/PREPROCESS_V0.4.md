# Deep Sky Preprocess Engine v0.4

v0.4에서 처음으로 실제 Siril CLI를 이용해 아래 작업을 수행합니다.

1. Calibration master 생성
2. Light calibration
3. Deep-sky registration
4. Registered frame 생성
5. Rejection stack
6. 32-bit FITS 결과 저장
7. 프로젝트 State 자동 갱신

## 기본 Siril 명령

- `convert`
- `calibrate`
- `stack`
- `register -2pass`
- `seqapplyreg`
- `set32bits`

## Master 정책

### Dark
Master Dark는 기본적으로 Bias를 따로 빼지 않고 stack합니다.

### Flat
우선순위:
1. Dark-flat이 있으면 Dark-flat으로 Flat calibration
2. 아니면 Bias가 있으면 Bias로 Flat calibration
3. 둘 다 없으면 경고 후 Flat 자체를 Master stack

### Light
- Dark가 있으면 Master Dark 사용
- Dark가 없고 Bias가 있으면 Master Bias 사용
- Flat이 있으면 Master Flat 사용

## OSC
Camera mode를 `OSC`로 명시하면 Light calibration에서:
- `-cfa`
- `-equalize_cfa`
- `-debayer`
옵션을 사용합니다.

`AUTO`는 안전상 CFA/debayer를 강제하지 않습니다.

## Registration
`register -2pass`는 변환값만 계산하므로 반드시 이어서:
`seqapplyreg ...`
를 사용합니다.

## Stack
기본값:
- Winsorized rejection
- 3 / 3 sigma
- additive with scale normalization
- wFWHM weighting
- 32-bit output

Subframe 자동 제외는 아직 강제하지 않습니다.
향후 품질분석에서 제외 후보를 제안하고 사용자 승인 후 필터링합니다.
