# v0.14.2 Project Collision UX Hotfix

## Problem

Single Image GUI used a deterministic project folder:

`{TARGET}_{DATE}_Auto`

If the folder already existed, `create_project()` intentionally raised
`FileExistsError` to avoid overwriting data. The UI only surfaced this as a
generic "프로젝트 생성 + 분석 오류", which was confusing during repeated tests.

## New behavior

When the same `{TARGET}_{DATE}_Auto` project already exists, the GUI asks:

- **Yes**: open the existing project
- **No**: create a fresh numbered project
- **Cancel**: do nothing

Fresh copies preserve the `_Auto` suffix:

- `M31_2026-09-30_Auto`
- `M31_2026-09-30_02_Auto`
- `M31_2026-09-30_03_Auto`

No existing project is deleted or overwritten.

## Compatibility

Existing projects and final naming rules are unchanged.
The v0.14.1 Windows BAT launcher hotfix and v0.14.0 SyQon/UI features are preserved.
