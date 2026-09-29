# Final / Export v0.13.0

Pixel Math Recombine 다음 단계이며 기본 파이프라인의 마지막 실제 단계입니다.

## Source

`RECOMBINED / NONLINEAR`

## Final working file

`working\12_final\{TARGET}_12_final.fits`

## Export naming

Final output files use `_Auto`.

- `output\fits\{TARGET}_final_Auto.fits`
- `output\tiff\{TARGET}_final_Auto.tif`
- `output\png\{TARGET}_final_Auto.png`
- `output\preview\{TARGET}_final_Auto.jpg`

## Siril 1.4.4 commands

32-bit FITS path:

`set32bits`
`save filename [-chksum]`

16-bit TIFF:

`savetif filename [-deflate]`

16-bit PNG for 16/32-bit loaded image:

`savepng filename`

Final preview:

`savejpg filename quality`

## Color-profile note

v0.13.0 does not force ICC or sRGB conversion / profile embedding.

For color-managed web delivery, perform an explicit sRGB conversion in a
color-managed editor such as Photoshop when required.

## Safety

- Final preview is required before export.
- Source Recombined FITS is preserved.
- All selected output files are validated after Siril exits.
- Project state becomes `EXPORTED` only after successful output validation.
