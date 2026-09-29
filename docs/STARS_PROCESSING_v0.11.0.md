# Stars Processing v0.11.0

Starless Processing 다음 실제 처리 단계입니다.

## Operations

Saturation:
`Satu amount background_factor hue_range_index`

Brightness scale:
`fmul scalar`

Order:
`Saturation -> Brightness Scale`

## Important distinction

Brightness Scale changes the amplitude / visual prominence of the additive Stars
layer. It is NOT geometric star-size reduction.

No median/morphological star reduction is enabled by default because it can
change star profiles and introduce artifacts. A dedicated, validated star-size
reduction stage can be added later.

## Target-aware Recommendation Engine v0.2

Stars recommendation considers:

- Target Category
- Target Features
- Current Stars-layer statistics

Examples:

- galaxies / nebulae: reduce stars to emphasize target structure
- open/globular clusters: preserve star prominence
- low surface brightness / faint outer structure: reduce stars more
- high star density: reduce brightness and saturation slightly

Recommendations are starting points only and are not auto-applied.

## Output

`working\10_stars\{TARGET}_10_stars_processed.fits`

Project state:

`STARS_PROCESSED`

The Main/Starless file remains `current_file`.

Next:

`PIXEL_MATH_RECOMBINE`
