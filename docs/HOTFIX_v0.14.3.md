# v0.14.3 Preview / Cancel / Project UX Update

## Project directory naming
New projects use a prefix:

- `Auto_M31_2026-09-30`
- `Auto_M31_2026-09-30_02`

Legacy folders such as `M31_2026-09-30_Auto` remain readable and are discovered by the collision check.
Final exported filenames remain `M31_final_Auto.*`.

## Duplicate-project dialog
The generic Yes/No/Cancel message box was replaced with explicit actions:

- `기존 프로젝트 열기`
- `새 프로젝트 만들기`
- `취소`

No existing project is overwritten or deleted.

## Parallax preview
Restoration now provides:

- `빠른 미리보기`: same pixel scale, central 1536×1536 crop by default
- `전체 미리보기`: full image
- `승인 후 적용`: requires a matching FULL preview

The quick preview uses a crop rather than downsampling so star profile and sharpening scale remain representative.

## Live log + Cancel
All `run_bg` operations create a cancellation control. Siril execution uses `Popen` with live stdout streaming.

During a running task:
- Progressbar runs
- elapsed time is shown
- `[중단]` becomes active
- Siril/SyQon stdout appears in the detailed log in real time
- cancelling terminates the Siril process tree
- cancelled preview temp files are not reused

The Sequence GUI uses the same cancel policy.
