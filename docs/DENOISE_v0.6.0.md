# Siril Denoise v0.6.0

SPCC 다음 실제 처리 단계로 Siril 1.4.4 `denoise`를 연결합니다.

## UI 기본값
- Modulation: 1.0
- Cosmetic Correction: ON
- DA3D: OFF
- Independent RGB: OFF

## 명령 예
`denoise -mod=1`

옵션:
- Cosmetic OFF → `-nocosmetic`
- DA3D ON → `-da3d`
- Independent RGB ON → `-indep`

## VST
스택 이미지에서는 일반적으로 유리하지 않다는 Siril 문서 안내에 따라
v0.6.0 기본 UI에서는 VST를 제외합니다.

## 안전 흐름
`Denoise 미리보기 → 사용자 확인 → 승인 후 적용`

실제 적용 결과:
`working\05_denoise\{TARGET}_05_denoise.fits`

State:
`DENOISED`

다음:
Deblur 또는 GHS Stretch 구현 예정
