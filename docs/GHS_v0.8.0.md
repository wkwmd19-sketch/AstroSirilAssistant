# GHS Stretch v0.8.0

v0.7 Deblur 다음 실제 처리 단계입니다.

## Default path: AutoGHS

Siril 1.4.4:
`autoghs [-linked] shadowsclip stretchamount [-b=] [-hp=] [-lp=] [-clipmode=]`

AstroSirilAssistant default starting values:

- Linked RGB: ON
- Shadows Clip: -2.8
- Stretch Amount D: 1.0
- B: 13
- LP: 0.0
- HP: 0.7
- Clip Mode: rgbblend

Important:
- Siril AutoGHS itself computes SP from median/sigma.
- Siril's implicit AutoGHS defaults are B=13, HP=0.7, LP=0.
- D is mandatory in Siril; v0.8 uses 1.0 as a conservative application starting value.

## Advanced path: Manual GHT

Siril:
`ght -D= -B= -LP= -SP= -HP= -clipmode= -human/-even/-independent`

## Preview

Unlike earlier Linear processing previews, GHS preview does NOT apply AutoStretch after GHS.

Reason:
GHS itself is the actual nonlinear stretch.

## Multi-pass safety

First pass:
`LINEAR -> NONLINEAR`

After each apply:
`GHS_REVIEW`

User explicitly chooses:
- Additional GHS Pass
- Finish Stretch -> StarNet

Additional pass files:
- `{TARGET}_07_ghs1.fits`
- `{TARGET}_07_ghs2.fits`
- ...

This separates intentional iterative GHS from accidental duplicate initial stretching.
