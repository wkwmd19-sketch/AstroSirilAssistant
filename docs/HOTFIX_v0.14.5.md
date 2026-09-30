# v0.14.5 SyQon Full-Image Safe-Band Hotfix

## Observed Windows behavior

A 1536x1536 Parallax quick preview reaches `Connected to Siril` and CUDA inference,
while the full 3713x1743 RGB32 image repeatedly stalls after Siril reports
`Python module is up-to-date`, before Parallax's own processing logs begin.
Padding the full image to an even 3714x1744 did not change that behavior.

## v0.14.5 compatibility path

For SyQon Parallax FULL processing, AstroSirilAssistant now estimates the 32-bit
pixel payload exchanged through the Siril Python bridge. When it exceeds a
conservative configurable threshold, the image is processed as overlapping,
full-width bands at the original pixel scale.

Default configuration:

- `full_safe_banding: true`
- `safe_bridge_payload_mib: 32`
- `safe_band_overlap: 192`
- `startup_watchdog_sec: 30`

Each band is processed by the unmodified installed Parallax.py with the exact
user-selected Parallax parameters. Completed bands are feather-blended in the
overlap region and reconstructed to the original image geometry. The resulting
full-resolution Linear FITS becomes the same promotable candidate used by the
`결과 승인` action, so AI processing is still performed only once.

This is a compatibility workaround, not a claim that the exact upstream cause
has been proven. Direct full-image mode remains possible by disabling
`syqon.full_safe_banding` in config.
