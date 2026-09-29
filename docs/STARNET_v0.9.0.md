# StarNet / Star Separation v0.9.0

GHS 다음 실제 처리 단계입니다.

## Important architecture update

Siril 1.4.4 documentation marks the built-in StarNet C interface as deprecated
for current StarNet2 releases.

StarNet2 2.5+ is handled through the official Python wrapper:

`pyscript StarNet.py`

The current official StarNetAstro/StarNet.py source states:
- minimum supported StarNet2: 2.5.0
- tested Windows CLI: StarNet2 2.6.2
- highlight-protection control requires 2.5.3+

This matches the user's installed StarNet2 2.6.2.

## Deterministic command

For a stretched telescope image:

`pyscript StarNet.py --no-linear --stride 256 --no-upsample --protect-highlights --masks subtract`

## Defaults

- Linear Data: OFF, forced from project state
- Stride: Standard 256
- 2x Upsampling: OFF
- Protect Highlights: ON
- Stars Layer: subtraction (`Original - Starless`)
- Native Starmask: OFF

## Stride presets from the official StarNet.py

- Large: 384 — super-wide landscape
- Standard: 256 — telescope image
- Small: 128 — slower; may help with extremely large stars

## Preview optimization

StarNet can be expensive.

v0.9.0 runs StarNet during Preview and caches:
- Starless FITS
- Stars FITS
- Starless JPEG
- Stars JPEG

If parameters and input remain unchanged, `승인 후 적용` promotes the preview
files into the project instead of running StarNet a second time.

## Actual output

- `working\08_starnet\{TARGET}_08_starless.fits`
- `working\08_starnet\{TARGET}_08_stars.fits`

Optional:
- `working\08_starnet\{TARGET}_08_starnetmask.fits`

Project state:
- `STARS_SEPARATED`
- `current_file = starless`
- `stars_removed = true`

The subtraction Stars layer is deliberately selected because future Pixel Math
recombination can use:

`Main + Stars * star_weight`
