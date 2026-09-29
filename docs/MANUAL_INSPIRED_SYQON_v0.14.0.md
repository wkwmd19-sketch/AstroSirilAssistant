# Manual-inspired SyQon Workflow v0.14.0

## Premise

AstroSirilAssistant의 기본 Single Image 파이프라인은
"비슷한 Siril 기능으로 대체"하는 것이 아니라,
이전에 수동 보정에서 사용했던 처리 흐름을 가능한 한 직접 재사용한다.

## v0.14 Linear order

`Gradient → SPCC → Parallax → Prism → GHS`

이전 v0.13 기본 순서:

`Gradient → SPCC → Siril Denoise → Siril RL Deblur → GHS`

v0.14에서는 새 프로젝트의 순서를 수동 작업 흐름에 맞게 변경했다.

## Restoration

Default:
`SYQON_PARALLAX`

Siril command family:
`pyscript <Parallax.py> ...`

Fallback:
`SIRIL_RL`

Parallax default starting values:
- Nano
- Aberration correction ON
- Star level 3
- Sharpen 1
- Tile 512
- Overlap 64
- Pad 96
- MTF ON / target 0.25
- Linked OFF
- GPU ON

## Denoise

Default:
`SYQON_PRISM`

Siril command family:
`pyscript <Prism.py> ...`

Fallback:
`SIRIL_NATIVE`

Prism default starting values:
- Mini
- Tile 512
- Overlap 96
- Pad 96
- Modulation 1
- Statistical temporary stretch
- Target 0.25
- GPU ON

## Script discovery

AstroSirilAssistant searches common Siril `siril-scripts` locations.

For a custom location, add the repository root to:

`config/app.yaml`

```yaml
syqon:
  script_roots:
    - 'D:\path\to\siril-scripts'
```

The app does not copy or redistribute SyQon scripts/models.

## Compatibility

Existing projects from v0.6-v0.13 are kept compatible.

- Project already DENOISED: legacy Denoise → Restore → GHS path can continue.
- Project still COLOR_CALIBRATED: opening it in v0.14 migrates the next task to Restoration first.
- Later-stage projects are not rewound.

## Runtime note

SyQon AI calls use a separate 3600-second timeout because the first run or
large images can take substantially longer than normal Siril commands.
