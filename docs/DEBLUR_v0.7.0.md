# Deblur / Deconvolution v0.7.0

SPCC → Denoise 다음 실제 처리 단계입니다.

## Siril Native Flow

1. `makepsf clear`
2. `makepsf stars ...`
3. `rl -iters=...`
4. Linear FITS 저장
5. Preview일 때만 AutoStretch JPEG 생성

## 기본값

- PSF Source: Detected Stars
- Symmetric PSF: OFF
- Kernel Size: Siril default
- RL Iterations: 10
- Regularization: NONE
- Alpha: 3000
- Multiplicative RL: OFF

## Regularization

- NONE
- TV
- FH

TV/FH를 선택한 경우에만 Alpha를 사용합니다.

Siril 문서 기준:
- RL 기본 iterations = 10
- Alpha 기본값 = 3000
- Alpha는 낮을수록 정규화가 강합니다.
- 기본 RL은 Gradient Descent
- `-mul`로 Multiplicative 방식 선택 가능

## 결과

Actual apply:

`working\06_deblur\{TARGET}_06_deblur.fits`

PSF:

`working\06_deblur\{TARGET}_06_psf.fits`

State:

`DEBLURRED / LINEAR`

다음:

`GHS_STRETCH`
