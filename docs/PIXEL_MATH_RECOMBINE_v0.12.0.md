# Pixel Math Recombine v0.12.0

Stars Processing 다음 실제 처리 단계입니다.

## Siril 1.4.4 command

`pm "expression" [-rescale [low] [high]] [-nosum]`

Variables are image names without extension surrounded by `$`.

AstroSirilAssistant uses a temporary working directory with:

- `Main.fits`
- `Stars.fits`

Default expression:

`$Main$ + $Stars$ * 1`

Command:

`pm "$Main$ + $Stars$ * 1" -nosum`

## Why -nosum is fixed

Main and Stars are two layers derived from the same integration.
They are not independent exposures, so summing LIVETIME / STACKCNT style
metadata would be misleading.

## Recommendation behavior

If Stars Processing already changed star brightness:
- Recombine starts at Weight 1.0
- this avoids applying the same target-based star reduction twice

Example:
- Stars Processing brightness = 0.6
- Recombine weight = 1.0
- effective scale vs original subtraction layer ≈ 0.6

If Stars Processing was skipped:
- target category/features provide the starting Recombine weight

## Rescale

Default OFF.

`-rescale 0 1` is available as an advanced option, but it changes the global
range. The UI first recommends reducing Star Weight if highlight clipping is
detected.

## Preview promotion

Pixel Math preview produces a real FITS.
If input and parameters are unchanged, Apply promotes that exact preview FITS
to:

`working\11_recombine\{TARGET}_11_recombined.fits`

State:

`RECOMBINED / NONLINEAR`

Next:

`FINALIZE_EXPORT`
