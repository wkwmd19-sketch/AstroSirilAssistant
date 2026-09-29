# Starless Processing v0.10.0

StarNet 다음 실제 처리 단계입니다.

## Pipeline

`Starless input → CLAHE(optional) → Saturation(optional) → Starless processed`

## Siril 1.4.4 commands

CLAHE:
`clahe cliplimit tileSize`

Saturation:
`satu amount [background_factor [hue_range_index]]`

Siril documents CLAHE as better suited to non-linear data, which matches the
post-GHS Starless image in this workflow.

## Output

`working\09_starless\{TARGET}_09_starless_processed.fits`

State:
`STARLESS_PROCESSED`

Stars layer:
unchanged; retained under `working\08_starnet`.

Next:
`STARS_PROCESS`

## Recommendations

The UI displays a target-aware recommendation card before the controls.

The recommendation combines:
- category profile
- target structural features
- bounded modifiers from current Starless image statistics

The values are a conservative starting point, not an optimum.
