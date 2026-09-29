# Validation v0.14.0

## Static validation

- Python source compile: PASS
- YAML parse: PASS
- SyQon command-builder tests: PASS
- Manual-inspired project-order tests: PASS
- Legacy migration tests: PASS
- Shared BAT launcher tests: PASS
- Shared UI structure tests: PASS

## Unit tests

55 tests passed in the build container.

The build container does not include `astropy`, so test discovery used a minimal
import stub. These tests cover command generation, state transitions, migration,
help/config structure, launchers and UI structure. They do not substitute for
real FITS I/O testing on the Windows runtime.

## Tk GUI smoke test

Using Xvfb:

- Main GUI opens with Astro Graphite theme
- Sequence GUI opens with Astro Graphite theme
- Dynamic log Pane opens/closes with visible height in both GUIs
- Main default Restoration panel = SyQon Parallax
- Main default Denoise panel = SyQon Prism
- Sequence log-view/copy controls remain enabled while a processing job is busy

## Runtime boundary

Actual Windows + Siril 1.4.4 + installed SyQon Parallax/Prism execution cannot
be validated in this build container. Test `SyQon 설치 확인`, then run
Restoration Preview and Denoise Preview in the user's environment before relying
on v0.14 for a full production image.
