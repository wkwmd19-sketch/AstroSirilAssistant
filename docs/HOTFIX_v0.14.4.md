# v0.14.4 — Restoration Full-Run Reliability + Flow Summary

## Why

A real Windows/Siril log showed a 1536×1536 SyQon Parallax quick preview finishing in
about 11 seconds on CUDA, while a 3713×1743 full preview repeatedly stopped after
`Python module is up-to-date` before Parallax emitted its actual processing logs.

## Changes

- Added a persistent two-line flow summary:
  - `현재 단계 :` one-line purpose/explanation
  - `다음 작업 :` stage name only
- Renamed the action card to `현재 단계 설정`.
- Restoration UI now uses:
  - `빠른 미리보기`
  - `전체 처리 + 결과 확인`
  - `결과 승인`
- A successful FULL Restoration preview is now a promotable candidate.
  `결과 승인` copies that exact candidate into the working stage and does **not**
  rerun Parallax/RL.
- Added a SyQon startup watchdog. After Siril reports that its Python module is
  up-to-date, a FULL Parallax run must reach a real Parallax processing marker
  within the configured timeout (default: 90 s) or it is terminated with a clear error.
- Added an even-geometry guard for FULL SyQon input. Odd dimensions are padded only
  on bottom/right using edge replication, then the processed candidate is cropped
  back to the exact original dimensions before preview/approval.
- Existing quick preview, cancellation, live log streaming, legacy project opening,
  and `Auto_` project directory naming remain intact.

## Runtime boundary

The build environment cannot execute the user's installed Siril/SyQon scripts.
The watchdog and candidate-promotion logic are validated structurally/unit-wise;
actual v0.14.4 Parallax FULL runtime still needs the Windows test.
