# v0.14.6 UI Copy Polish + Parallax Before/After

## Runtime baseline

The v0.14.5 Safe-Band Parallax path was user-confirmed on Windows with Siril 1.4.4 / SyQon, and the single-image pipeline was completed through Final export.

## Quick preview comparison

Parallax QUICK preview now creates two display-only PPM images from the same 1536×1536 FITS crop:

- Before: SPCC output crop
- After: Parallax linear result crop

One linked display stretch is calculated from the Before crop only and then applied unchanged to both views. The underlying FITS files remain Linear and unmodified.

The GUI opens an in-app side-by-side comparison window. The existing After JPEG remains available as a fallback.

## Copy cleanup policy

The workflow summary card is the primary explanation surface:

- `현재 단계 : <한 줄 설명>`
- `다음 작업 : <단계명>`

Stage cards focus on controls. Repeated subtitles, default-value prose, implementation-only labels, and duplicated AutoStretch notes were removed where the same information is already available through Help or the detailed log.
